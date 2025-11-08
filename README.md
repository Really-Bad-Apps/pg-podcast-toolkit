# pg-podcast-toolkit

Tools for parsing and managing Podcasting 2.0 RSS feeds with automatic namespace capture and database-ready output.

## Features

- **Podcasting 2.0 Support** - Automatically captures all podcast:* namespace tags without parser updates
- **Database-Ready Output** - Built-in `to_db_record()` methods for PostgreSQL schema alignment
- **Backward Compatible** - Existing code continues to work, new features are opt-in
- **Deterministic IDs** - MD5-based UUID generation for podcasts and episodes
- **GUID Fallback** - Handles episodes with missing GUIDs gracefully
- **Comprehensive Parsing** - Supports RSS 2.0, iTunes extensions, and custom namespaces

## Installation

```bash
pip install pg-podcast-toolkit
```

## Quick Start

### Basic Usage

```python
from pg_podcast_toolkit import Podcast
import requests

# Fetch and parse a podcast feed
response = requests.get('https://example.com/feed.xml')
podcast = Podcast(response.content, feed_url='https://example.com/feed.xml')

# Access podcast metadata
print(podcast.title)
print(podcast.description)
print(podcast.itunes_image)

# Access episodes
for item in podcast.items:
    print(f"{item.title} - {item.itunes_duration}s")
```

### Database Integration (New in v0.2.0)

```python
# Get database-ready podcast record
podcast_record = podcast.to_db_record(
    etag='some-etag',              # Optional HTTP ETag
    last_modified='Wed, 06 Nov',   # Optional Last-Modified header
    last_fetched_at=1234567890     # Optional fetch timestamp
)

# Insert into PostgreSQL
# podcast_record matches schema: id, podcast_guid, title, feed_url,
# image_url, language, itunes_id, etag, last_modified, last_fetched_at,
# created_at, updated_at, extras (JSONB)

# Get database-ready episode records
for item in podcast.items:
    episode_record = item.to_db_record(podcast_id=podcast_record['id'])
    # episode_record matches schema: id, podcast_id, guid, title,
    # description, image_url, publish_date, duration_seconds,
    # episode_number, season_number, episode_type, explicit,
    # enclosure_url, enclosure_type, enclosure_size,
    # created_at, updated_at, extras (JSONB)
```

### Accessing Podcasting 2.0 Namespaces (New in v0.2.0)

```python
# All unknown namespace tags are automatically captured
print(podcast.namespaces)
# {
#   'podcast': {
#     'guid': {'value': '...'},
#     'locked': {'value': 'yes', 'attributes': {'owner': 'email@example.com'}},
#     'funding': {'value': 'Support!', 'attributes': {'url': 'https://...'}},
#     'person': [
#       {'value': 'Host Name', 'attributes': {'role': 'host', 'img': '...'}},
#       ...
#     ]
#   }
# }

# Episode-level namespaces
for item in podcast.items:
    print(item.namespaces)
    # {
    #   'podcast': {
    #     'chapters': {'attributes': {'url': '...', 'type': 'application/json'}},
    #     'transcript': {'attributes': {'url': '...', 'type': 'text/srt'}},
    #     'person': [...],
    #     ...
    #   }
    # }
```

## What's New in v0.2.0

- **Automatic Namespace Capture** - No parser updates needed for new Podcasting 2.0 tags
- **Database-Ready Methods** - `Podcast.to_db_record()` and `Item.to_db_record()`
- **Schema Alignment** - Output matches PostgreSQL schema with UUID primary keys
- **GUID Fallback** - Episodes without GUIDs use `enclosure_url` for ID generation
- **100% Backward Compatible** - All existing attributes and methods unchanged

## Supported Specifications

- RSS 2.0
- iTunes Podcast Extensions
- Podcasting 2.0 Namespace (automatic capture)
- Custom namespace extensions (automatic capture)

## Development Status

This library is actively maintained and production-ready. The v0.2.0 release introduces database integration features while maintaining full backward compatibility.

## License

MIT License

