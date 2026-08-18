# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup, Tag
from datetime import datetime, date
import email.utils
from time import mktime
import time
import hashlib
import json
from .item import Item, tag_html_content, tag_text
import logging

class InvalidPodcastFeed(ValueError):
    pass

class Podcast():
    """Parses an xml rss feed

    RSS Specs http://cyber.law.harvard.edu/rss/rss.html

    More RSS Specs http://www.rssboard.org/rss-specification

    iTunes Podcast Specs http://www.apple.com/itunes/podcasts/specs.html


    The cloud element aka RSS Cloud is not supported as it has been superseded by the superior PubSubHubbub protocal

    Args:
        feed_content (str): An rss string

    Note:
        All attributes with empty or nonexistent element will have a value of None

        Attributes are generally strings or lists of strings, because we want to record the literal value of elements.

    Attributes:
        feed_content (str): The actual xml of the feed
        soup (None): Only used during parsing; released (set to None) once
            __init__ completes so retained Podcast objects don't pin the
            parse tree in memory
        copyright (str): The feed's copyright
        items (item): Item objects
        description (str): The feed's description
        image_url (str): Feed image url
        itunes_author_name (str): The podcast's author name for iTunes
        itunes_block (bool): Does the podcast block itunes
        itunes_categories (list): List of strings of itunes categories
        itunes_complete (str): Is this podcast done and complete
        itunes_explicit (str): Is this item explicit. Should only be "yes" and "clean."
        itunes_image (str): URL to itunes image
        itunes_new_feed_url (str): The new url of this podcast
        language (str): Language of feed
        last_build_date (str): Last build date of this feed
        link (str): URL to homepage
        published_date (str): Date feed was published
        owner_name (str): Name of feed owner
        owner_email (str): Email of feed owner
        subtitle (str): The feed subtitle
        title (str): The feed title
        date_time (datetime): When published
    """

    def __init__(self, feed_content, feed_url=None):
        self.feed_content = feed_content
        self.feed_url = feed_url
        self.items = []
        self.itunes_categories = []

        # Captures tags from unknown namespaces (e.g., podcast:*, custom extensions)
        self.namespaces = {}

        # Initialize attributes as they might not be populated
        self.copyright = None
        self.description = None
        self.image_url = None
        self.image_link = None
        self.itunes_author_name = None
        self.itunes_block = False
        self.image_width = None
        self.itunes_complete = None
        self.itunes_explicit = None
        self.itunes_image = None
        self.itunes_new_feed_url = None
        self.language = None
        self.last_build_date = None
        self.link = None
        self.published_date = None
        self.summary = None
        self.owner_name = None
        self.owner_email = None
        self.subtitle = None
        self.title = None
        self.type = None
        self.date_time = None
        self.itunes_type = None

        self.set_soup()
        tag_methods = {
            (None, 'copyright'): self.set_copyright,
            (None, 'description'): self.set_description,
            (None, 'image'): self.set_image,
            (None, 'language'): self.set_language,
            (None, 'lastBuildDate'): self.set_last_build_date,
            (None, 'link'): self.set_link,
            (None, 'pubDate'): self.set_published_date,
            (None, 'title'): self.set_title,
            (None, 'item'): self.add_item,
            ('itunes', 'author'): self.set_itunes_author_name,
            ('itunes', 'type'): self.set_itunes_type,
            ('itunes', 'block'): self.set_itunes_block,
            ('itunes', 'category'): self.add_itunes_category,
            ('itunes', 'complete'): self.set_itunes_complete,
            ('itunes', 'explicit'): self.set_itunes_explicit,
            ('itunes', 'image'): self.set_itunes_image,
            ('itunes', 'new-feed-url'): self.set_itunes_new_feed_url,
            ('itunes', 'owner'): self.set_owner,
            ('itunes', 'subtitle'): self.set_subtitle,
            ('itunes', 'summary'): self.set_summary,
        }
        many_tag_methods = set([ (None, 'item'), ('itunes', 'category')])
        # Snapshot before the pop-loop below empties tag_methods; the second
        # pass needs the full set to know which tags were standard ones.
        known_tags = set(tag_methods)

        try:
            channel = self.soup.rss.channel
            channel_items = channel.children
        except AttributeError as ae:
            raise InvalidPodcastFeed(f"Invalid Podcast Feed error: {ae}")

        # Populate attributes based on feed content
        for c in channel_items:
            if not isinstance(c, Tag):
                continue
            try:
                # Pop method to skip duplicated tag on invalid feeds
                tag_tuple = (c.prefix, c.name)
                if tag_tuple in many_tag_methods:
                    tag_method = tag_methods[tag_tuple]
                else:
                    tag_method = tag_methods.pop(tag_tuple)
            except (AttributeError, KeyError):
                continue

            tag_method(c)

        # Second pass: collect unknown namespace tags
        for c in channel.children:
            if not isinstance(c, Tag):
                continue
            tag_tuple = (c.prefix, c.name)
            # Skip standard tags handled (or handleable) by the first pass
            if tag_tuple in known_tags:
                continue
            self._capture_unknown_tag(c)

        if not self.items:
            for item in self.soup.find_all('item'):
                self.add_item(item)

        # Parsing is done; drop the tree so retained Podcast/Item objects
        # don't pin the whole parsed document in memory.
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
        else:
            try:
                self.date_time = date.fromtimestamp(self.time_published)
            except ValueError:
                self.date_time = None

    def to_dict(self):
        podcast_dict = {}
        podcast_dict['copyright'] = getattr(self, 'copyright', None)
        podcast_dict['description'] = getattr(self, 'description', None)
        podcast_dict['image_url'] = getattr(self, 'image_url', None)
        podcast_dict['image_link'] = getattr(self, 'image_link', None)
        items_list = getattr(self, 'items', None)
        if items_list is None:
            podcast_dict['items'] = None
        else:
            podcast_dict['items'] = []
            for item in items_list:
                podcast_dict['items'].append(item.to_dict())
        podcast_dict['itunes_author_name'] = getattr(self, 'itunes_author_name', None)
        podcast_dict['itunes_block'] = getattr(self, 'itunes_block', None)
        podcast_dict['itunes_categories'] = getattr(self, 'itunes_categories', None)
        podcast_dict['itunes_complete'] = getattr(self, 'itunes_complete', None)
        podcast_dict['itunes_explicit'] = getattr(self, 'itunes_explicit', None)
        podcast_dict['itunes_image'] = getattr(self, 'itunes_image', None)
        podcast_dict['itunes_new_feed_url'] = getattr(self, 'itunes_new_feed_url', None)
        podcast_dict['language'] = getattr(self, 'language', None)
        podcast_dict['last_build_date'] = getattr(self, 'last_build_date', None)
        podcast_dict['link'] = getattr(self, 'link', None)
        podcast_dict['published_date'] = getattr(self, 'published_date', None)
        podcast_dict['owner_name'] = getattr(self, 'owner_name', None)
        podcast_dict['owner_email'] = getattr(self, 'owner_email', None)
        podcast_dict['subtitle'] = getattr(self, 'subtitle', None)
        podcast_dict['title'] = getattr(self, 'title', None)
        podcast_dict['type'] = getattr(self, 'type', None)

        # DB-column fields (populated on Podcast objects restored from a database row)
        podcast_dict['id'] = getattr(self, 'id', None)
        podcast_dict['podcast_guid'] = getattr(self, 'podcast_guid', None)
        podcast_dict['itunes_id'] = getattr(self, 'itunes_id', None)
        podcast_dict['feed_url'] = getattr(self, 'feed_url', None)
        podcast_dict['etag'] = getattr(self, 'etag', None)
        podcast_dict['last_modified'] = getattr(self, 'last_modified', None)
        podcast_dict['last_fetched_at'] = getattr(self, 'last_fetched_at', None)
        podcast_dict['created_at'] = getattr(self, 'created_at', None)
        podcast_dict['updated_at'] = getattr(self, 'updated_at', None)
        podcast_dict['extras'] = getattr(self, 'extras', None)
        return podcast_dict

    def to_db_record(self, etag=None, last_modified=None, last_fetched_at=None):
        """
        Returns a dict structured for database insertion matching schema.sql.

        Args:
            etag: HTTP ETag header (optional, for efficient polling)
            last_modified: HTTP Last-Modified header (optional, for conditional requests)
            last_fetched_at: Unix timestamp of fetch time (optional, defaults to current time)

        Returns dict with keys matching database schema:
        - id: 32-char lowercase MD5 hex string of feed_url (hexdigest, NOT a hyphenated UUID)
        - podcast_guid: UUID string from podcast:guid if present
        - title: Podcast title
        - feed_url: RSS feed URL
        - image_url: Podcast image (prefers itunes_image, falls back to image_url)
        - language: Podcast language
        - itunes_id: iTunes podcast ID (if extractable from feed)
        - etag: HTTP ETag for efficient polling
        - last_modified: HTTP Last-Modified header
        - last_fetched_at: Unix timestamp of last fetch
        - created_at: Unix timestamp (current time)
        - updated_at: Unix timestamp (current time)
        - extras: JSONB dict containing all other metadata and namespaces
        """
        # Generate deterministic ID from MD5 hex of feed_url
        if self.feed_url:
            podcast_id = hashlib.md5(self.feed_url.encode('utf-8')).hexdigest()
        else:
            podcast_id = None

        # Extract podcast_guid from namespaces if present
        podcast_guid = None
        if 'podcast' in self.namespaces and 'guid' in self.namespaces['podcast']:
            guid_data = self.namespaces['podcast']['guid']
            if isinstance(guid_data, dict):
                podcast_guid = guid_data.get('value')
            else:
                podcast_guid = guid_data

        # Extract iTunes ID if available (would need to be parsed from feed_url or other source)
        itunes_id = None

        # Prefer itunes_image over standard image_url
        image_url = self.itunes_image if self.itunes_image else self.image_url

        # Build extras dict with all other metadata
        extras = {
            'description': self.description,
            'copyright': self.copyright,
            'subtitle': self.subtitle,
            'summary': self.summary,
            'link': self.link,
            'last_build_date': self.last_build_date,
            'published_date': self.published_date,
            'owner_name': self.owner_name,
            'owner_email': self.owner_email,
            'itunes_author_name': self.itunes_author_name,
            'itunes_categories': self.itunes_categories,
            'itunes_explicit': self.itunes_explicit,
            'itunes_complete': self.itunes_complete,
            'itunes_type': self.itunes_type,
            'itunes_block': self.itunes_block,
            'itunes_new_feed_url': self.itunes_new_feed_url,
            'image_link': self.image_link,
            'type': self.type,
            'namespaces': self.namespaces
        }

        current_time = int(time.time())

        return {
            'id': podcast_id,
            'podcast_guid': podcast_guid,
            'title': self.title,
            'feed_url': self.feed_url,
            'image_url': image_url,
            'language': self.language,
            'itunes_id': itunes_id,
            'etag': etag,
            'last_modified': last_modified,
            'last_fetched_at': last_fetched_at if last_fetched_at is not None else current_time,
            'created_at': current_time,
            'updated_at': current_time,
            'extras': json.dumps(extras)
        }

    def set_soup(self):
        """Sets soup"""
        if not isinstance(self.feed_content, bytes):
            raise TypeError(
                "feed_content must be bytes, not string. "
                "Use response.content (not response.text) when fetching feeds."
            )

        if self.feed_content.startswith(b'<?xml'):
            self.soup = BeautifulSoup(self.feed_content, features="lxml-xml")
        else:
            c = self.feed_content
            try:
                recovered_content = c[c.index(b'<?xml'):]
                self.soup = BeautifulSoup(recovered_content, features="lxml-xml")
            except:
                self.soup = BeautifulSoup(self.feed_content, features="lxml-xml")


    def add_item(self, tag):
        try:
            item = Item(tag, feed_url=self.feed_url)
        except Exception as e:
            logging.exception("error parsing item")
            return

        self.items.append(item)

    def set_copyright(self, tag):
        """Parses copyright and set value"""
        try:
            self.copyright = tag_text(tag)
        except AttributeError:
            self.copyright = None

    def set_description(self, tag):
        """Parses description, preserving HTML content, and sets value"""
        try:
            self.description = tag_html_content(tag)
        except AttributeError:
            self.description = None

    def set_image(self, tag):
        """Parses image element and set values"""
        try:
            self.image_url = tag_text(tag.find('url', recursive=False))
        except AttributeError:
            self.image_url = None

    def set_itunes_author_name(self, tag):
        """Parses author name from itunes tags and sets value"""
        try:
            self.itunes_author_name = tag_text(tag)
        except AttributeError:
            self.itunes_author_name = None

    def set_itunes_type(self, tag):
        """Parses the type of show and sets value"""
        try:
            self.itunes_type = tag_text(tag)
        except AttributeError:
            self.itunes_type = None

    def set_itunes_block(self, tag):
        """Check and see if podcast is blocked from iTunes and sets value"""
        block = tag_text(tag)
        if block is None:
            block = ""
        else:
            block = block.lower()
        if block == "yes":
            self.itunes_block = True
        else:
            self.itunes_block = False

    def add_itunes_category(self, tag):
        """Parses and add itunes category"""
        category_text = tag.get('text')
        self.itunes_categories.append(category_text)

    def set_itunes_complete(self, tag):
        """Parses complete from itunes tags and sets value"""
        value = tag_text(tag)
        if value is not None:
            value = value.lower()
        self.itunes_complete = value

    def set_itunes_explicit(self, tag):
        """Parses explicit from itunes tags and sets value"""
        value = tag_text(tag)
        if value is not None:
            value = value.lower()
        self.itunes_explicit = value

    def set_itunes_image(self, tag):
        """Parses itunes images and set url as value"""
        try:
            self.itunes_image = tag.get('href')
        except AttributeError:
            self.itunes_image = None

    def set_itunes_new_feed_url(self, tag):
        """Parses new feed url from itunes tags and sets value"""
        try:
            self.itunes_new_feed_url = tag_text(tag)
        except AttributeError:
            self.itunes_new_feed_url = None

    def set_language(self, tag):
        """Parses feed language and set value"""
        try:
            self.language = tag_text(tag)
        except AttributeError:
            self.language = None

    def set_last_build_date(self, tag):
        """Parses last build date and set value"""
        try:
            self.last_build_date = tag_text(tag)
        except AttributeError:
            self.last_build_date = None

    def set_link(self, tag):
        """Parses link to homepage and set value"""
        try:
            self.link = tag_text(tag)
        except AttributeError:
            self.link = None

    def set_published_date(self, tag):
        """Parses published date and set value"""
        try:
            self.published_date = tag_text(tag)
        except AttributeError:
            self.published_date = None

    def set_owner(self, tag):
        """Parses owner name and email then sets value"""
        try:
            self.owner_name = tag_text(tag.find('itunes:name', recursive=False))
        except AttributeError:
            self.owner_name = None
        try:
            self.owner_email = tag_text(tag.find('itunes:email', recursive=False))
        except AttributeError:
            self.owner_email = None

    def set_subtitle(self, tag):
        """Parses subtitle, preserving HTML content, and sets value"""
        try:
            self.subtitle = tag_html_content(tag)
        except AttributeError:
            self.subtitle = None

    def set_summary(self, tag):
        """Parses summary, preserving HTML content, and sets value"""
        try:
            self.summary = tag_html_content(tag)
        except AttributeError:
            self.summary = None

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

    def set_title(self, tag):
        """Parses title and set value"""
        try:
            self.title = tag_text(tag)
        except AttributeError:
            self.title = None
