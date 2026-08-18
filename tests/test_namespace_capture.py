"""Tests for unknown-namespace tag capture on Podcast and Item.

Standard tags handled by the parser's first pass must NOT be duplicated
into the namespaces dict (previously the skip check was inverted and every
standard tag leaked into DB extras JSON — HiveMake ticket 15369e5e review).
"""
from pg_podcast_toolkit.podcast import Podcast


FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Example Show</title>
    <link>https://example.com/</link>
    <description>A test feed.</description>
    <language>en-us</language>
    <pubDate>Sun, 19 Apr 2026 00:00:00 GMT</pubDate>
    <itunes:author>Jane Doe</itunes:author>
    <itunes:category text="Technology" />
    <podcast:guid>9f8e7d6c-0000-0000-0000-000000000001</podcast:guid>
    <podcast:locked>no</podcast:locked>
    <item>
      <title>Episode 1</title>
      <description>Notes</description>
      <guid>ep-1</guid>
      <pubDate>Sun, 19 Apr 2026 00:00:00 GMT</pubDate>
      <enclosure url="https://example.com/ep1.mp3" length="12345" type="audio/mpeg" />
      <itunes:duration>10:00</itunes:duration>
      <podcast:transcript url="https://example.com/t.txt" type="text/plain" />
      <podcast:season>2</podcast:season>
    </item>
  </channel>
</rss>
""".encode('utf-8')


def test_standard_channel_tags_not_captured_into_namespaces():
    podcast = Podcast(FEED, feed_url='https://example.com/feed.xml')

    assert 'default' not in podcast.namespaces
    assert 'itunes' not in podcast.namespaces


def test_unknown_channel_tags_are_captured():
    podcast = Podcast(FEED, feed_url='https://example.com/feed.xml')

    captured = podcast.namespaces['podcast']
    assert captured['guid']['value'] == '9f8e7d6c-0000-0000-0000-000000000001'
    assert captured['locked']['value'] == 'no'


def test_standard_item_tags_not_captured_into_namespaces():
    item = Podcast(FEED, feed_url='https://example.com/feed.xml').items[0]

    assert 'default' not in item.namespaces
    assert 'itunes' not in item.namespaces


def test_unknown_item_tags_are_captured():
    item = Podcast(FEED, feed_url='https://example.com/feed.xml').items[0]

    captured = item.namespaces['podcast']
    assert captured['season']['value'] == '2'
    assert captured['transcript']['attributes'] == {
        'url': 'https://example.com/t.txt',
        'type': 'text/plain',
    }
