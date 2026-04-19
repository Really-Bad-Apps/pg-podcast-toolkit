"""Tests for Podcast.to_dict() on parser-built and DB-loaded objects."""
import pytest

from pg_podcast_toolkit.podcast import Podcast


MINIMAL_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Example Show</title>
    <link>https://example.com/</link>
    <description>A test feed.</description>
    <language>en-us</language>
    <copyright>2026 Example</copyright>
    <itunes:author>Jane Doe</itunes:author>
    <itunes:explicit>no</itunes:explicit>
    <itunes:complete>no</itunes:complete>
    <itunes:image href="https://example.com/cover.jpg" />
    <itunes:category text="Technology" />
    <itunes:owner>
      <itunes:name>Jane Doe</itunes:name>
      <itunes:email>jane@example.com</itunes:email>
    </itunes:owner>
    <item>
      <title>Episode 1</title>
      <guid>ep-1</guid>
      <enclosure url="https://example.com/ep1.mp3" length="12345" type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""


DB_FIELDS = [
    'id', 'podcast_guid', 'itunes_id', 'feed_url', 'etag',
    'last_modified', 'last_fetched_at', 'created_at', 'updated_at', 'extras',
]


def test_parser_path_populates_fields_and_db_fields_default_none():
    podcast = Podcast(MINIMAL_FEED, feed_url='https://example.com/feed.xml')
    result = podcast.to_dict()

    # Parser-populated fields
    assert result['title'] == 'Example Show'
    assert result['description'] == 'A test feed.'
    assert result['language'] == 'en-us'
    assert result['copyright'] == '2026 Example'
    assert result['link'] == 'https://example.com/'
    assert result['itunes_author_name'] == 'Jane Doe'
    assert result['itunes_explicit'] == 'no'
    assert result['itunes_complete'] == 'no'
    assert result['itunes_image'] == 'https://example.com/cover.jpg'
    assert result['itunes_categories'] == ['Technology']
    assert result['owner_name'] == 'Jane Doe'
    assert result['owner_email'] == 'jane@example.com'
    assert result['itunes_block'] is False
    assert isinstance(result['items'], list) and len(result['items']) == 1

    # DB fields default to None for parser-built Podcasts
    # (feed_url is an exception — it is set on the parser object)
    assert result['feed_url'] == 'https://example.com/feed.xml'
    for key in ('id', 'podcast_guid', 'itunes_id', 'etag',
                'last_modified', 'last_fetched_at', 'created_at',
                'updated_at', 'extras'):
        assert result[key] is None, f"{key} should be None on parser-built Podcast"


def test_parser_path_no_duplicate_keys_and_itunes_complete_correct():
    podcast = Podcast(MINIMAL_FEED)
    result = podcast.to_dict()

    # If itunes_complete were still mapped to self.image_width it would be None;
    # we want the parsed value.
    assert result['itunes_complete'] == 'no'

    # Ensure every DB field key is present exactly once.
    for key in DB_FIELDS:
        assert key in result


def test_db_loaded_path_does_not_raise_and_returns_db_fields():
    """A Podcast built via object.__new__ (as pguru-podcast-db does) must
    round-trip through to_dict() without crashing, and DB column values
    attached to the instance must appear in the resulting dict."""
    podcast = object.__new__(Podcast)
    podcast.id = 'abc123'
    podcast.podcast_guid = '9f8e7d6c-0000-0000-0000-000000000001'
    podcast.itunes_id = 42
    podcast.feed_url = 'https://example.com/feed.xml'
    podcast.title = 'DB Loaded Show'
    podcast.language = 'en'
    podcast.image_url = 'https://example.com/cover.jpg'
    podcast.etag = 'W/"abc"'
    podcast.last_modified = 'Sun, 19 Apr 2026 00:00:00 GMT'
    podcast.last_fetched_at = 1_700_000_000
    podcast.created_at = 1_699_000_000
    podcast.updated_at = 1_700_000_000
    podcast.extras = {'subtitle': 'From DB', 'namespaces': {'podcast': {}}}

    result = podcast.to_dict()

    assert result['id'] == 'abc123'
    assert result['podcast_guid'] == '9f8e7d6c-0000-0000-0000-000000000001'
    assert result['itunes_id'] == 42
    assert result['feed_url'] == 'https://example.com/feed.xml'
    assert result['title'] == 'DB Loaded Show'
    assert result['language'] == 'en'
    assert result['image_url'] == 'https://example.com/cover.jpg'
    assert result['etag'] == 'W/"abc"'
    assert result['last_modified'] == 'Sun, 19 Apr 2026 00:00:00 GMT'
    assert result['last_fetched_at'] == 1_700_000_000
    assert result['created_at'] == 1_699_000_000
    assert result['updated_at'] == 1_700_000_000
    assert result['extras'] == {'subtitle': 'From DB', 'namespaces': {'podcast': {}}}

    # Fields the consumer did not restore come back as None, not AttributeError.
    assert result['description'] is None
    assert result['copyright'] is None
    assert result['subtitle'] is None
    assert result['owner_name'] is None
    assert result['owner_email'] is None
    assert result['itunes_categories'] is None
    assert result['itunes_complete'] is None
    assert result['itunes_block'] is None
    assert result['items'] is None
