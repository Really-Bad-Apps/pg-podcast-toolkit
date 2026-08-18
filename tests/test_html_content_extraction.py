"""Tests for HTML-preserving extraction on content:encoded and the
channel-level description/summary/subtitle fields.

bs4's Tag.string recurses into a lone child element (stripping its markup)
and returns None for mixed content; these fields must survive both
(HiveMake ticket 15369e5e follow-up review of v0.4.0).
"""
from pg_podcast_toolkit.podcast import Podcast


def build_feed(channel_xml: str, item_xml: str) -> bytes:
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Example Show</title>
    <link>https://example.com/</link>
    {channel_xml}
    <item>
      <title>Episode 1</title>
      <guid>ep-1</guid>
      {item_xml}
      <enclosure url="https://example.com/ep1.mp3" length="12345" type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""
    return feed.encode('utf-8')


def test_content_encoded_single_child_element_preserves_markup():
    feed = build_feed(
        '<description>d</description>',
        '<content:encoded><p>Show notes</p></content:encoded>',
    )
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.items[0].content_encoded == '<p>Show notes</p>'


def test_content_encoded_multiple_child_elements_preserved():
    feed = build_feed(
        '<description>d</description>',
        '<content:encoded><p>First</p><p>Second</p></content:encoded>',
    )
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.items[0].content_encoded == '<p>First</p><p>Second</p>'


def test_content_encoded_cdata_stored_verbatim():
    feed = build_feed(
        '<description>d</description>',
        '<content:encoded><![CDATA[<p>Full notes</p>]]></content:encoded>',
    )
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.items[0].content_encoded == '<p>Full notes</p>'


def test_content_encoded_missing_is_none():
    feed = build_feed('<description>d</description>', '')
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.items[0].content_encoded is None


def test_channel_description_single_child_element_preserves_markup():
    feed = build_feed('<description><p>Hello</p></description>', '')
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.description == '<p>Hello</p>'


def test_channel_description_mixed_content_not_lost():
    feed = build_feed(
        '<description>Intro <b>bold</b> outro</description>', ''
    )
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.description == 'Intro <b>bold</b> outro'


def test_channel_summary_and_subtitle_mixed_content_not_lost():
    feed = build_feed(
        '<itunes:summary>A <i>great</i> show</itunes:summary>'
        '<itunes:subtitle>Really <b>good</b></itunes:subtitle>',
        '',
    )
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.summary == 'A <i>great</i> show'
    assert podcast.subtitle == 'Really <b>good</b>'


def test_channel_description_plain_text_unchanged():
    feed = build_feed('<description>Just plain text.</description>', '')
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.description == 'Just plain text.'
