"""Tests for unknown-namespace tag capture on Podcast and Item.

Standard tags handled by the parser's first pass must NOT be duplicated
into the namespaces dict (previously the skip check was inverted and every
standard tag leaked into DB extras JSON — HiveMake ticket 15369e5e review).
"""
from typing import Optional

import pytest

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


@pytest.mark.parametrize("guid_tag", [
    '<podcast:guid xmlns:podcast="https://podcastindex.org/namespace/1.0">show-guid</podcast:guid>',
    '<p:guid xmlns:p="https://podcastindex.org/namespace/1.0">show-guid</p:guid>',
    '<guid xmlns="https://podcastindex.org/namespace/1.0">show-guid</guid>',
])
def test_podcast_guid_recognized_by_namespace_uri(guid_tag: str) -> None:
    feed = f'<rss><channel><title>Show</title>{guid_tag}</channel></rss>'.encode()
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.to_db_record()['podcast_guid'] == 'show-guid'
    assert podcast.to_dict()['podcast_guid'] == 'show-guid'


@pytest.mark.parametrize("guid_tag", [
    '<podcast:guid xmlns:podcast="https://example.com/unrelated">wrong-guid</podcast:guid>',
    '<guid>wrong-guid</guid>',
    '<item><guid>episode-guid</guid></item>',
])
def test_unrelated_guids_are_not_podcast_guids(guid_tag: str) -> None:
    feed = f'<rss><channel><title>Show</title>{guid_tag}</channel></rss>'.encode()
    podcast = Podcast(feed)

    assert podcast.to_db_record()['podcast_guid'] is None


def test_guid_namespace_rebinding_does_not_override_identity() -> None:
    feed = b'''<rss xmlns:podcast="https://example.com/unrelated">
      <channel><title>Show</title>
        <podcast:guid>wrong-guid</podcast:guid>
        <podcast:guid xmlns:podcast="https://podcastindex.org/namespace/1.0">show-guid</podcast:guid>
        <item><title>Episode</title><guid>ep-1</guid></item>
      </channel>
    </rss>'''
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')
    record = podcast.to_db_record()
    assert record['podcast_guid'] == 'show-guid'
    assert record['id'] == 'f7880620c8c1d31d1b57c3edde9deffa'
    assert podcast.items[0].guid == 'ep-1'
    assert isinstance(podcast.namespaces['podcast']['guid'], list)


@pytest.mark.parametrize("first_value, expected", [
    ('first-guid', 'first-guid'),
    ('', None),
    ('<![CDATA[  first-guid  ]]>', '  first-guid  '),
])
def test_first_guid_wins_across_namespace_aliases(
    first_value: str, expected: Optional[str],
) -> None:
    feed = f'''<rss xmlns:p="https://podcastindex.org/namespace/1.0"
                    xmlns:podcast="https://podcastindex.org/namespace/1.0">
      <channel><title>Show</title>
        <p:guid>{first_value}</p:guid>
        <podcast:guid>second-guid</podcast:guid>
      </channel>
    </rss>'''.encode()
    podcast = Podcast(feed)

    assert podcast.to_db_record()['podcast_guid'] == expected
    assert podcast.to_dict()['podcast_guid'] == expected


def test_namespace_alias_preserves_podcast_and_episode_ids() -> None:
    original = Podcast(FEED, feed_url='https://example.com/feed.xml')
    aliased_feed = FEED.replace(b'xmlns:podcast=', b'xmlns:p=').replace(
        b'podcast:', b'p:')
    aliased = Podcast(aliased_feed, feed_url='https://example.com/feed.xml')

    original_id = original.to_db_record()['id']
    aliased_id = aliased.to_db_record()['id']
    assert aliased_id == original_id
    assert aliased.items[0].to_db_record(aliased_id)['id'] == (
        original.items[0].to_db_record(original_id)['id']
    )
    assert aliased.to_db_record()['podcast_guid'] == original.to_db_record()['podcast_guid']
    assert aliased.namespaces['p']['guid'] == original.namespaces['podcast']['guid']
