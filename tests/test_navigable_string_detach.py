"""Tests that parsed values are plain str, not bs4.NavigableString.

A NavigableString keeps a parent reference into the BeautifulSoup parse
tree, so a single retained one pins the entire parsed document in memory
(HiveMake ticket 15369e5e, follow-up to ed27813f).
"""
import gc
import weakref

from bs4 import NavigableString

from pg_podcast_toolkit.podcast import Podcast


FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Example Show</title>
    <link>https://example.com/</link>
    <description>A test feed.</description>
    <language>en-us</language>
    <copyright>2026 Example</copyright>
    <lastBuildDate>Sun, 19 Apr 2026 00:00:00 GMT</lastBuildDate>
    <pubDate>Sun, 19 Apr 2026 00:00:00 GMT</pubDate>
    <image>
      <url>https://example.com/rss-cover.jpg</url>
    </image>
    <itunes:author>Jane Doe</itunes:author>
    <itunes:type>episodic</itunes:type>
    <itunes:subtitle>A subtitle</itunes:subtitle>
    <itunes:summary>A summary</itunes:summary>
    <itunes:explicit>no</itunes:explicit>
    <itunes:complete>no</itunes:complete>
    <itunes:new-feed-url>https://example.com/new-feed.xml</itunes:new-feed-url>
    <itunes:image href="https://example.com/cover.jpg" />
    <itunes:category text="Technology" />
    <itunes:owner>
      <itunes:name>Jane Doe</itunes:name>
      <itunes:email>jane@example.com</itunes:email>
    </itunes:owner>
    <podcast:guid>9f8e7d6c-0000-0000-0000-000000000001</podcast:guid>
    <item>
      <title>Episode 1</title>
      <author>jane@example.com</author>
      <description><![CDATA[<p>Show notes</p>]]></description>
      <guid>ep-1</guid>
      <pubDate>Sun, 19 Apr 2026 00:00:00 GMT</pubDate>
      <enclosure url="https://example.com/ep1.mp3" length="12345" type="audio/mpeg" />
      <content:encoded><![CDATA[<p>Full HTML show notes</p>]]></content:encoded>
      <itunes:author>Jane Doe</itunes:author>
      <itunes:episode>1</itunes:episode>
      <itunes:season>2</itunes:season>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:duration>10:00</itunes:duration>
      <itunes:explicit>No</itunes:explicit>
      <itunes:subtitle>Episode subtitle</itunes:subtitle>
      <itunes:summary>Episode summary</itunes:summary>
      <podcast:season>2</podcast:season>
      <podcast:transcript url="https://example.com/t.txt" type="text/plain" />
    </item>
  </channel>
</rss>
""".encode('utf-8')


def assert_no_navigable_strings(value, path: str) -> None:
    """Recursively assert no NavigableString hides in value."""
    assert not isinstance(value, NavigableString), \
        f"{path} is a NavigableString, pinning the parse tree"
    if isinstance(value, dict):
        for key, child in value.items():
            assert_no_navigable_strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            assert_no_navigable_strings(child, f"{path}[{i}]")


def test_no_navigable_strings_retained_on_podcast_or_items():
    podcast = Podcast(FEED, feed_url='https://example.com/feed.xml')

    for name, value in vars(podcast).items():
        if name in ('soup', 'items'):
            continue
        assert_no_navigable_strings(value, f"podcast.{name}")

    assert len(podcast.items) == 1
    for item in podcast.items:
        for name, value in vars(item).items():
            if name == 'soup':
                continue
            assert_no_navigable_strings(value, f"item.{name}")


def test_content_encoded_is_plain_str():
    podcast = Podcast(FEED, feed_url='https://example.com/feed.xml')
    content = podcast.items[0].content_encoded

    assert content == '<p>Full HTML show notes</p>'
    assert type(content) is str


def test_parse_tree_released_while_podcast_and_items_alive(monkeypatch):
    """After __init__, the BeautifulSoup document must be garbage-collectable
    even while the Podcast and its Items are still retained."""
    captured = {}
    original_set_soup = Podcast.set_soup

    def capturing_set_soup(self) -> None:
        original_set_soup(self)
        captured['soup_ref'] = weakref.ref(self.soup)

    monkeypatch.setattr(Podcast, 'set_soup', capturing_set_soup)

    podcast = Podcast(FEED, feed_url='https://example.com/feed.xml')
    gc.collect()

    assert podcast.soup is None
    assert podcast.items[0].soup is None
    assert captured['soup_ref']() is None, \
        "parse tree still alive: something retained a reference into it"
    # The parsed data is still intact and usable.
    assert podcast.to_dict()['title'] == 'Example Show'
    assert podcast.items[0].to_dict()['title'] == 'Episode 1'
