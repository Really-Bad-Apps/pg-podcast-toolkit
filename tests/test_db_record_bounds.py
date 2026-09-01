"""Tests for the plausibility bounds Item.to_db_record applies to publisher ints.

Publishers mash the keyboard into <itunes:episode> and friends on items they
don't feel like numbering. Values like 445544554455 are not episode numbers,
and every consumer shouldn't have to re-derive that independently.
See hive ticket 784e03a5.
"""
import logging

import pytest

from pg_podcast_toolkit.item import (
    MAX_DURATION_SECONDS,
    MAX_ENCLOSURE_BYTES,
    MAX_EPISODE_NUMBER,
    MAX_SEASON_NUMBER,
    bounded_int,
)
from pg_podcast_toolkit.podcast import Podcast


FEED_TEMPLATE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Example Show</title>
    <link>https://example.com/</link>
    <description>A test feed.</description>
    <item>
      <title>Episode</title>
      <guid>ep-1</guid>
      <enclosure url="https://example.com/ep1.mp3" length="12345" type="audio/mpeg" />
      %s
    </item>
  </channel>
</rss>
"""


def build_record(item_tags: str) -> dict:
    """Parse a one-item feed carrying item_tags and return its db record."""
    feed = FEED_TEMPLATE % item_tags.encode('utf-8')
    podcast = Podcast(feed, feed_url='https://example.com/rss')
    return podcast.items[0].to_db_record(podcast_id='pod-1')


def test_plausible_values_survive():
    record = build_record(
        '<itunes:episode>42</itunes:episode>'
        '<itunes:season>3</itunes:season>'
        '<itunes:duration>01:02:03</itunes:duration>'
    )
    assert record['episode_number'] == 42
    assert record['season_number'] == 3
    assert record['duration_seconds'] == 3723


def test_keyboard_mash_episode_is_dropped():
    # The value that zeroed out a real 445-episode podcast downstream.
    record = build_record('<itunes:episode>445544554455</itunes:episode>')
    assert record['episode_number'] is None


# Every 7+ digit <itunes:episode> in anchor.fm/s/ad3c2ba4/podcast/rss is
# keyboard-mash. Only the four above the bound are actually rejected; see
# test_mash_below_the_bound_is_admitted for the eleven that are not, and why.

@pytest.mark.parametrize('value', [
    '10999999999', '445544554455', '45454545454', '4848484848',
])
def test_observed_garbage_above_the_bound_is_dropped(value):
    record = build_record(f'<itunes:episode>{value}</itunes:episode>')
    assert record['episode_number'] is None


@pytest.mark.parametrize('value', [
    '484848484', '494949494', '499499499', '474747474',
    '49494949', '4999999', '4555555', '4455555',
    '123456789', '454546789', '45678910',
])
def test_mash_below_the_bound_is_admitted(value):
    """Documents a deliberate limitation, not desired behaviour.

    These are known keyboard-mash from the feed in ticket 784e03a5, and a
    magnitude bound cannot reject them: 494949494 is indistinguishable in
    size from Anchor's legitimate 156556622, and 45678910 from a YYYYMMDD.
    Rejecting them would mean discarding real episode numbers, which is the
    regression ticket 4f862bc7 was filed about.

    What matters is that none of them can overflow an INT4 column, so the
    incident that started this class of bug cannot recur through them. They
    are wrong episode numbers, not destructive ones.

    If this test starts failing, someone has narrowed the bound — check
    4f862bc7 before assuming that is an improvement.
    """
    record = build_record(f'<itunes:episode>{value}</itunes:episode>')
    assert record['episode_number'] == int(value)
    assert record['episode_number'] < 2 ** 31 - 1


def test_garbage_season_is_dropped():
    record = build_record('<itunes:season>4848484848</itunes:season>')
    assert record['season_number'] is None


def test_non_numeric_episode_is_dropped():
    record = build_record('<itunes:episode>pilot</itunes:episode>')
    assert record['episode_number'] is None


def test_absent_tags_yield_none():
    record = build_record('')
    assert record['episode_number'] is None
    assert record['season_number'] is None
    assert record['duration_seconds'] is None


def test_implausible_duration_is_dropped():
    record = build_record('<itunes:duration>999999999</itunes:duration>')
    assert record['duration_seconds'] is None


def test_missing_duration_sentinel_becomes_none():
    # parse_hms returns -1 for a zero duration; the db record must not carry it.
    record = build_record('<itunes:duration>0</itunes:duration>')
    assert record['duration_seconds'] is None


def test_missing_duration_sentinel_is_not_warned_about(caplog):
    # A zero duration is a routine feed condition, not an implausible value.
    # Warning per item would flood the log on a large feed.
    with caplog.at_level(logging.WARNING):
        build_record('<itunes:duration>0</itunes:duration>')
    assert not any('itunes:duration' in message for message in caplog.messages)


def test_whitespace_only_value_is_absent_not_garbage(caplog):
    with caplog.at_level(logging.WARNING):
        record = build_record('<itunes:episode>   </itunes:episode>')
    assert record['episode_number'] is None
    assert not any('itunes:episode' in message for message in caplog.messages)


def test_padded_value_still_parses():
    record = build_record('<itunes:episode>\n      42\n    </itunes:episode>')
    assert record['episode_number'] == 42


def test_dropped_value_is_logged(caplog):
    with caplog.at_level(logging.WARNING):
        build_record('<itunes:episode>445544554455</itunes:episode>')
    assert any('445544554455' in message for message in caplog.messages)
    assert any('https://example.com/rss' in message for message in caplog.messages)


def test_bounds_are_inclusive():
    assert bounded_int(str(MAX_EPISODE_NUMBER), MAX_EPISODE_NUMBER, 'itunes:episode') == MAX_EPISODE_NUMBER
    assert bounded_int(str(MAX_EPISODE_NUMBER + 1), MAX_EPISODE_NUMBER, 'itunes:episode') is None
    assert bounded_int(str(MAX_SEASON_NUMBER), MAX_SEASON_NUMBER, 'itunes:season') == MAX_SEASON_NUMBER
    assert bounded_int(str(MAX_DURATION_SECONDS), MAX_DURATION_SECONDS, 'itunes:duration') == MAX_DURATION_SECONDS


def test_zero_episode_is_not_confused_with_absent():
    # 0 is in range, so it parses; only absence and implausibility give None.
    assert bounded_int('0', MAX_EPISODE_NUMBER, 'itunes:episode') == 0
    assert bounded_int('', MAX_EPISODE_NUMBER, 'itunes:episode') is None
    assert bounded_int(None, MAX_EPISODE_NUMBER, 'itunes:episode') is None


def test_negative_values_are_dropped():
    assert bounded_int('-1', MAX_EPISODE_NUMBER, 'itunes:episode') is None


# --- Legitimate publisher numbering schemes (hive ticket 4f862bc7) -----------
#
# An earlier MAX_EPISODE_NUMBER of 999999 discarded every one of these in
# production. They are deliberate schemes, not keyboard-mash, and each one is
# pinned here so the bound cannot silently narrow back underneath them.

@pytest.mark.parametrize('value, scheme', [
    ('10000001', 'PodPlay offset range, first of a contiguous run'),
    ('10000033', 'PodPlay offset range, last of a contiguous run'),
    ('20260821', 'Megaphone YYYYMMDD'),
    ('20260901', 'Megaphone YYYYMMDD'),
    ('20250429', 'NBC News YYYYMMDD'),
    ('20260409', 'NBC News YYYYMMDD'),
    ('2026040110', 'NBC News YYYYMMDD + hour'),
    ('2026040123', 'NBC News YYYYMMDD + hour, largest legitimate observed'),
    ('202605001', 'NBC News YYYYMM + sequence'),
    ('2026050107', 'NBC News YYYYMM + sequence'),
    ('2603039', 'NBC News YYMMDD-ish'),
    ('156556622', 'Anchor, platform-internal id shape'),
])
def test_real_publisher_numbering_survives(value, scheme):
    record = build_record(f'<itunes:episode>{value}</itunes:episode>')
    assert record['episode_number'] == int(value), scheme


def test_mash_still_separable_from_legitimate_numbering():
    # The bound has to sit between the largest real value and the smallest
    # mash value. If someone widens it past 4848484848 the original bug is back.
    assert 2026040123 <= MAX_EPISODE_NUMBER < 4848484848


# --- enclosure_size (hive ticket dc0e9231) ----------------------------------

def build_record_with_enclosure(length: str) -> dict:
    feed = FEED_TEMPLATE.replace(
        b'length="12345"', f'length="{length}"'.encode('utf-8')) % b''
    podcast = Podcast(feed, feed_url='https://example.com/rss')
    return podcast.items[0].to_db_record(podcast_id='pod-1')


def test_plausible_enclosure_size_survives():
    assert build_record_with_enclosure('52428800')['enclosure_size'] == 52428800


def test_implausible_enclosure_size_is_dropped():
    assert build_record_with_enclosure('4455445544554455445')['enclosure_size'] is None


def test_non_numeric_enclosure_size_is_dropped():
    # Note the drop happens upstream of bounded_int: set_enclosure's bare
    # except already nulls a non-numeric length="", so this asserts the end
    # state only and would pass with the to_db_record bound removed. The
    # bound's own handling of non-numeric input is pinned directly below;
    # unlike itunes:episode, a non-numeric enclosure length is dropped
    # without a warning log because bounded_int never sees it.
    assert build_record_with_enclosure('unknown')['enclosure_size'] is None
    assert bounded_int('unknown', MAX_ENCLOSURE_BYTES, 'enclosure length') is None


def test_enclosure_bound_is_inclusive():
    assert bounded_int(str(MAX_ENCLOSURE_BYTES), MAX_ENCLOSURE_BYTES, 'enclosure length') == MAX_ENCLOSURE_BYTES
    assert bounded_int(str(MAX_ENCLOSURE_BYTES + 1), MAX_ENCLOSURE_BYTES, 'enclosure length') is None


def test_large_video_enclosure_survives():
    # A long-form 4K video episode can legitimately run tens of GiB. The
    # ceiling exists to reject byte counts no publisher meant, not to have
    # an opinion about file size — see 4f862bc7 for what the tighter kind
    # of bound cost us.
    forty_gib = str(40 * 1024 ** 3)
    assert build_record_with_enclosure(forty_gib)['enclosure_size'] == int(forty_gib)


def test_enclosure_bound_still_rejects_reported_garbage():
    # The 19-digit value from dc0e9231 stays well above the ceiling.
    assert 4455445544554455445 > MAX_ENCLOSURE_BYTES
