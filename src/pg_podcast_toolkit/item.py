from datetime import datetime, date
from typing import Optional
import email.utils
from time import mktime
from bs4 import Tag
import hashlib
import time
import json
import logging


def tag_text(tag: Optional[Tag]) -> Optional[str]:
    """Return a tag's text via bs4's Tag.string, detached as a plain str.

    Tag.string is None when the tag holds multiple children (though bs4
    recurses into a lone child element). It returns a NavigableString whose
    parent reference keeps the whole parsed document alive; str() copies just
    the text so the tree can be GC'd. Accepts None so callers can pass
    tag.find(...) results straight through.
    """
    if tag is None:
        return None
    value = tag.string
    if value is None:
        return None
    return str(value)


def tag_html_content(tag: Tag) -> Optional[str]:
    """Return a tag's content preserving any inner HTML markup, detached.

    Uses the tag's single text/CDATA node when that is all it holds. Falls
    back to the serialized inner HTML when the tag contains child elements
    (Tag.string would recurse into a lone child and strip its markup) or
    multiple text nodes. Returns None for an empty tag.
    """
    if tag.find(True, recursive=False) is not None:
        return tag.decode_contents()
    value = tag_text(tag)
    if value is None and tag.contents:
        # Multiple text/CDATA nodes that Tag.string won't join
        value = tag.decode_contents()
    return value


# parse time formats in hh:mm:ss strings into actual seconds
def parse_hms(hms):

    if hms is None:
        return -1

    # if it's a a floating point number, convert it to an integer.
    try:
        hms = int(float(hms))
    except:
        pass

    if isinstance(hms, int):
        # unless it's a 0, which doesn't make sense, so return -1
        if hms == 0:
            return -1
        else:
            return hms

    colon_count = hms.count(':')
    seconds = -1

    if colon_count == 0:
        return int(hms)
    elif colon_count == 1:
        parts = hms.split(':')
        seconds = int(parts[0]) * 60
        seconds += int(parts[1])
    elif colon_count == 2:
        # handle hh:mm:ss
        parts = hms.split(":")
        seconds = int(parts[0]) * 3600
        seconds += int(parts[1]) * 60
        seconds += int(parts[2])
    elif colon_count == 3:
        parts = hms.split(":")
        seconds = int(parts[1]) * 3600
        seconds += int(parts[2]) * 60
        seconds += int(parts[3])

    return seconds

class Item(object):
    """Parses an xml rss feed

    RSS Specs http://cyber.law.harvard.edu/rss/rss.html
    iTunes Podcast Specs http://www.apple.com/itunes/podcasts/specs.html

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object representing a rss item

    Note:
        All attributes with empty or nonexistent element will have a value of None

        The soup argument is only used during parsing; self.soup is released
        (set to None) once __init__ completes so retained Item objects don't
        pin the feed's parse tree in memory.

    Attributes:
        author (str): The author of the item
        description (str): Description of the item.
        enclosure_url (str): URL of enclosure
        enclosure_type (str): File MIME type
        enclosure_length (int): File size in bytes
        guid (str): globally unique identifier
        itunes_author_name (str): Author name given to iTunes
        itunes_episode_type (srt): Itunes episode type
        itunes_episode (int): Episode number in season
        itunes_season (int): Podcast season
        itunes_block (bool): It this Item blocked from itunes
        itunes_duration (str): Duration of enclosure
        itunes_explicit (str): Is this item explicit. Should only be yes or clean.
        itunes_image (str): URL of item cover art
        itunes_order (str): Override published_date order
        itunes_subtitle (str): The item subtitle
        itunes_summary (str): The summary of the item
        content_encoded(str): The encoded content of the item
        published_date (str): Date item was published
        title (str): The title of item.
        date_time (datetime): When published
    """

    def __init__(self, soup, feed_url = None):
        self.soup = soup
        self.feed_url = feed_url

        # Captures tags from unknown namespaces (e.g., podcast:*, custom extensions)
        self.namespaces = {}

        # Initialize attributes as they might not be populated
        self.author = None
        self.description = None
        self.enclosure_url = None
        self.enclosure_type = None
        self.enclosure_length = None
        self.content_encoded = None
        self.guid = None
        self.episode_id = None
        self.itunes_author_name = None
        self.itunes_episode_type = None
        self.itunes_block = False
        self.itunes_duration = None
        self.itunes_season = None
        self.itunes_episode = None
        self.itunes_explicit = None
        self.itunes_image = None
        self.itunes_order = None
        self.itunes_subtitle = None
        self.itunes_summary = None
        self.published_date = None
        self.title = None
        self.date_time = None

        tag_methods = {
            (None, 'title'): self.set_title,
            (None, 'author'): self.set_author,
            (None, 'description'): self.set_description,
            (None, 'guid'): self.set_guid,
            (None, 'pubDate'): self.set_published_date,
            (None, 'enclosure'): self.set_enclosure,
            ('content', 'encoded'): self.set_content_encoded,
            ('itunes', 'author'): self.set_itunes_author_name,
            ('itunes', 'episode'): self.set_itunes_episode,
            ('itunes', 'episodeType'): self.set_itunes_episode_type,
            ('itunes', 'block'): self.set_itunes_block,
            ('itunes', 'season'): self.set_itunes_season,
            ('itunes', 'duration'): self.set_itunes_duration,
            ('itunes', 'explicit'): self.set_itunes_explicit,
            ('itunes', 'image'): self.set_itunes_image,
            ('itunes', 'order'): self.set_itunes_order,
            ('itunes', 'subtitle'): self.set_itunes_subtitle,
            ('itunes', 'summary'): self.set_itunes_summary,
        }
        # Snapshot before the pop-loop below empties tag_methods; the second
        # pass needs the full set to know which tags were standard ones.
        known_tags = set(tag_methods)

        # Populate attributes based on feed content
        for c in self.soup.children:
            if not isinstance(c, Tag):
                continue
            try:
                # Pop method to skip duplicated tag on invalid feeds
                tag_method = tag_methods.pop((c.prefix, c.name))
            except (AttributeError, KeyError):
                continue

            tag_method(c)

        # Second pass: collect unknown namespace tags
        for c in self.soup.children:
            if not isinstance(c, Tag):
                continue
            tag_tuple = (c.prefix, c.name)
            # Skip standard tags handled (or handleable) by the first pass
            if tag_tuple in known_tags:
                continue
            self._capture_unknown_tag(c)

        # Parsing is done; drop the tag so a retained Item doesn't pin the
        # whole parsed document in memory via its parent references.
        self.soup = None

        self.set_time_published()
        self.set_dates_published()

    def set_time_published(self):
        if self.published_date is None:
            self.time_published = None
            return
        try:
            time_tuple = email.utils.parsedate_tz(self.published_date)
            self.time_published = email.utils.mktime_tz(time_tuple)
        except (TypeError, ValueError, IndexError):
            self.time_published = None

    def set_dates_published(self):
        if self.time_published is None:
            self.date_time = None
            return
        try:
            time_tuple = email.utils.parsedate(self.published_date)
            self.date_time = date.fromtimestamp(self.time_published)
        except ValueError:
            self.date_time = None


    def get_checksum(self):
        """
        Generates a unique MD5 checksum for an episode.  If any of the episode data changes, the checksum returned
        will be different.

        Returns: An md5 checksum

        """
        dct_episode = self.to_dict()
        raw = str()
        for data in dct_episode.values():
            if data:
                raw += str(data)

        guid_md5 = hashlib.md5(raw.encode()).hexdigest()
        return guid_md5


    def to_dict(self):
        item = {}
        item['author'] = self.author
        item['enclosure_url'] = self.enclosure_url
        item['enclosure_type'] = self.enclosure_type
        item['enclosure_length'] = self.enclosure_length
        item['enclosure_type'] = self.enclosure_type
        item['guid'] = self.guid
        item['episode_id'] = self.episode_id
        item['itunes_author_name'] = self.itunes_author_name
        item['itunes_block'] = self.itunes_block
        item['itunes_duration'] = self.itunes_duration
        item['itunes_explicit'] = self.itunes_explicit
        item['itunes_episode'] = self.itunes_episode
        item['itunes_season'] = self.itunes_season
        item['itunes_episode_type'] = self.itunes_episode_type
        item['itunes_image'] = self.itunes_image
        item['itunes_order'] = self.itunes_order
        item['itunes_subtitle'] = self.itunes_subtitle
        item['itunes_summary'] = self.itunes_summary
        item['content_encoded'] = self.content_encoded
        item['description'] = self.description
        item['published_date'] = self.published_date
        item['title'] = self.title
        return item

    def to_db_record(self, podcast_id):
        """
        Returns a dict structured for database insertion matching schema.sql episodes table.

        Args:
            podcast_id: 32-char MD5 hex ID of the parent podcast (required for deterministic episode ID generation)

        Returns dict with keys matching episodes database schema:
        - id: 32-char lowercase MD5 hex string of podcast_id || guid (hexdigest, NOT a hyphenated UUID)
        - podcast_id: 32-char MD5 hex ID of parent podcast
        - guid: Episode GUID
        - title: Episode title
        - description: Episode description
        - image_url: Episode-specific artwork
        - publish_date: Unix timestamp of publication
        - duration_seconds: Episode duration in seconds
        - episode_number: Episode number
        - season_number: Season number
        - episode_type: Episode type (full, trailer, bonus)
        - explicit: Boolean explicit content flag
        - enclosure_url: Media file URL
        - enclosure_type: Media MIME type
        - enclosure_size: Media file size in bytes
        - created_at: Unix timestamp (current time)
        - updated_at: Unix timestamp (current time)
        - extras: JSONB dict containing all other metadata and namespaces
        """
        # Generate deterministic episode ID from MD5 hex of (podcast_id || guid)
        # Fallback to enclosure_url if guid is missing
        if podcast_id:
            guid_value = self.guid if self.guid else self.enclosure_url
            if guid_value:
                combined = f"{podcast_id}{guid_value}"
                episode_id = hashlib.md5(combined.encode('utf-8')).hexdigest()
            else:
                episode_id = None
        else:
            episode_id = None

        # Convert itunes_explicit to boolean
        explicit = None
        if self.itunes_explicit:
            explicit = self.itunes_explicit.lower() in ('yes', 'true', '1')

        # Extract episode_number and season_number from itunes tags
        episode_number = None
        if self.itunes_episode:
            try:
                episode_number = int(self.itunes_episode)
            except (ValueError, TypeError):
                pass

        season_number = None
        if self.itunes_season:
            try:
                season_number = int(self.itunes_season)
            except (ValueError, TypeError):
                pass

        # Build extras dict with all other metadata
        extras = {
            'author': self.author,
            'content_encoded': self.content_encoded,
            'episode_id': self.episode_id,
            'itunes_author_name': self.itunes_author_name,
            'itunes_order': self.itunes_order,
            'itunes_subtitle': self.itunes_subtitle,
            'itunes_summary': self.itunes_summary,
            'itunes_block': self.itunes_block,
            'published_date_string': self.published_date,
            'namespaces': self.namespaces
        }

        current_time = int(time.time())

        return {
            'id': episode_id,
            'podcast_id': podcast_id,
            'guid': self.guid,
            'title': self.title,
            'description': self.description,
            'image_url': self.itunes_image,
            'publish_date': self.time_published,
            'duration_seconds': self.itunes_duration,
            'episode_number': episode_number,
            'season_number': season_number,
            'episode_type': self.itunes_episode_type,
            'explicit': explicit,
            'enclosure_url': self.enclosure_url,
            'enclosure_type': self.enclosure_type,
            'enclosure_size': self.enclosure_length,
            'created_at': current_time,
            'updated_at': current_time,
            'extras': json.dumps(extras)
        }

    def set_rss_element(self):
        """Set each of the basic rss elements."""
        self.set_enclosure()

    def set_author(self, tag):
        """Parses author and set value."""
        try:
            self.author = tag_text(tag)
        except AttributeError:
            self.author = None

    def set_description(self, tag):
        """Parses description, preserves HTML content, and checks size."""
        try:
            description_content = tag_html_content(tag)
            if description_content is None:
                description_content = ''
            max_bytes = 65536  # Maximum allowed bytes for the description
            
            # Check the byte length of the description content
            if len(description_content.encode('utf-8')) > max_bytes:
                # If the description exceeds the limit, replace it with a placeholder
                logging.info(f"Episode description exceeds maximum length, removing content from parent feed at {self.feed_url}")
                self.description = "description overflow, removed"
            else:
                # If within the limit, use the description as is
                self.description = description_content
                
        except AttributeError:
            self.description = None

    def set_content_encoded(self, tag):
        """Parses content_encoded, preserving HTML content, and sets value."""
        try:
            self.content_encoded = tag_html_content(tag)
        except AttributeError:
            self.content_encoded = None

    def set_enclosure(self, tag):
        """Parses enclosure_url, enclosure_type then set values."""
        try:
            self.enclosure_url = tag['url']
        except:
            self.enclosure_url = None
        try:
            self.enclosure_type = tag['type']
        except:
            self.enclosure_type = None
        try:
            self.enclosure_length = tag['length']
            self.enclosure_length = int(self.enclosure_length)
        except:
            self.enclosure_length = None

    def set_guid(self, tag):
        """Parses guid and set value"""
        try:
            self.guid = tag_text(tag)
        except AttributeError:
            self.guid = None

    def set_published_date(self, tag):
        """Parses published date and set value."""
        try:
            self.published_date = tag_text(tag)
        except AttributeError:
            self.published_date = None

    def set_title(self, tag):
        """Parses title and set value."""
        try:
            self.title = tag_text(tag)
        except AttributeError:
            self.title = None

    def set_itunes_author_name(self, tag):
        """Parses author name from itunes tags and sets value"""
        try:
            self.itunes_author_name = tag_text(tag)
        except AttributeError:
            self.itunes_author_name = None

    def set_itunes_episode(self, tag):
        """Parses the episode number and sets value"""
        try:
            self.itunes_episode = tag_text(tag)
        except AttributeError:
            self.itunes_episode = None

    def set_itunes_season(self, tag):
        """Parses the episode season and sets value"""
        try:
            self.itunes_season = tag_text(tag)
        except AttributeError:
            self.itunes_season = None

    def set_itunes_episode_type(self, tag):
        """Parses the episode type and sets value"""
        try:
            self.itunes_episode_type = tag_text(tag)
        except AttributeError:
            self.itunes_episode_type = None

    def set_itunes_block(self, tag):
        """Check and see if item is blocked from iTunes and sets value"""
        block = tag_text(tag)
        if block is None:
            block = ""
        else:
            block = block.lower()
        if block == "yes":
            self.itunes_block = True
        else:
            self.itunes_block = False

    def set_itunes_duration(self, tag):
        """Parses duration from itunes tags and sets value"""
        value = tag_text(tag)
        try:
            self.itunes_duration = parse_hms(value)
        except Exception:
            logging.warning(f"Error parsing itunes duration {value}")
            self.itunes_duration = None

    def set_itunes_explicit(self, tag):
        """Parses explicit from itunes item tags and sets value"""
        value = tag_text(tag)
        if value is not None:
            value = value.lower()
        self.itunes_explicit = value

    def set_itunes_image(self, tag):
        """Parses itunes item images and set url as value"""
        try:
            self.itunes_image = tag.get('href')
        except AttributeError:
            self.itunes_image = None

    def set_itunes_order(self, tag):
        """Parses episode order and set url as value"""
        value = tag_text(tag)
        if value is not None:
            value = value.lower()
        self.itunes_order = value

    def set_itunes_subtitle(self, tag):
        """Parses subtitle from itunes tags and sets value"""
        try:
            self.itunes_subtitle = tag_text(tag)
        except AttributeError:
            self.itunes_subtitle = None

    def set_itunes_summary(self, tag):
        """Parses summary from itunes tags and sets value"""
        try:
            self.itunes_summary = tag_text(tag)
        except AttributeError:
            self.itunes_summary = None

    def _capture_unknown_tag(self, tag):
        """Captures tags from unknown namespaces into self.namespaces dict"""
        namespace = tag.prefix if tag.prefix else 'default'
        tag_name = tag.name

        if namespace not in self.namespaces:
            self.namespaces[namespace] = {}

        # Extract tag value and attributes
        tag_data = {}

        # Get tag attributes
        if tag.attrs:
            tag_data['attributes'] = dict(tag.attrs)

        # Get tag text content
        value = tag_text(tag)
        if value:
            tag_data['value'] = value
        elif tag.get_text(strip=True):
            tag_data['value'] = tag.get_text(strip=True)

        # Handle multiple tags with same name (convert to list)
        if tag_name in self.namespaces[namespace]:
            existing = self.namespaces[namespace][tag_name]
            if isinstance(existing, list):
                existing.append(tag_data)
            else:
                self.namespaces[namespace][tag_name] = [existing, tag_data]
        else:
            self.namespaces[namespace][tag_name] = tag_data
