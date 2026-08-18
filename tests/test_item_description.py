"""Tests for Item.set_description — must store clean inner HTML, not a
re-serialized <description> node (see HiveMake ticket ed27813f)."""
from pg_podcast_toolkit.podcast import Podcast


def build_feed(description_xml: str) -> bytes:
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Show</title>
    <link>https://example.com/</link>
    <description>A test feed.</description>
    <item>
      <title>Episode 1</title>
      <guid>ep-1</guid>
      {description_xml}
      <enclosure url="https://example.com/ep1.mp3" length="12345" type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""
    return feed.encode('utf-8')


def test_escaped_html_description_has_no_wrapper_and_no_double_escaping():
    feed = build_feed(
        '<description>&lt;p&gt;It&amp;#8217;s a &lt;b&gt;great&lt;/b&gt; show&lt;/p&gt;</description>'
    )
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')
    description = podcast.items[0].description

    assert description == "<p>It&#8217;s a <b>great</b> show</p>"
    assert '<description>' not in description
    assert '&lt;' not in description
    assert '&amp;' not in description


def test_cdata_html_description_is_stored_verbatim():
    feed = build_feed(
        '<description><![CDATA[<p>Hello &#8217;world&#8217;</p>]]></description>'
    )
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.items[0].description == "<p>Hello &#8217;world&#8217;</p>"


def test_plain_text_description():
    feed = build_feed('<description>Just plain text.</description>')
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.items[0].description == 'Just plain text.'


def test_description_with_child_elements_falls_back_to_inner_html():
    feed = build_feed('<description>Intro <b>bold</b> outro</description>')
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.items[0].description == 'Intro <b>bold</b> outro'


def test_missing_description_is_none():
    feed = build_feed('')
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.items[0].description is None


def test_oversized_description_is_replaced_with_placeholder():
    feed = build_feed(f'<description>{"x" * 70000}</description>')
    podcast = Podcast(feed, feed_url='https://example.com/feed.xml')

    assert podcast.items[0].description == 'description overflow, removed'
