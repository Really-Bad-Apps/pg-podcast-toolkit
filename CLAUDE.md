# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python library for parsing and managing Podcasting 2.0 RSS feeds. It provides tools for parsing podcast feeds, extracting metadata, handling media resources, and working with IPFS for decentralized podcast hosting.

## Package Structure

```
src/pg_podcast_toolkit/
├── __init__.py          # Exports Podcast and Item classes
├── podcast.py           # Main Podcast class for parsing RSS feeds
├── item.py              # Item class for individual podcast episodes
├── media_resource.py    # MediaResource class for enclosures/media files
├── podcast_tools.py     # Utility functions for downloading media
└── podcast_ipfs_tools.py # IPFS integration utilities
```

## Development Environment

**Virtual Environment Setup:**
```bash
# Create virtual environment (if not exists)
python -m venv .

# Activate virtual environment
source bin/activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

**IMPORTANT**: Always activate the virtual environment before running Python commands:
```bash
source bin/activate && python <script>
```

## Building and Publishing

**Build the package:**
```bash
source bin/activate
python -m build
```

**Publish to PyPI:**
```bash
./build-publish.sh
```

The build-publish.sh script handles:
1. Cleaning previous builds (`rm dist/*`)
2. Building the package (`python -m build`)
3. Uploading to PyPI (`python -m twine upload dist/*`)

**Note**: Requires PyPI credentials configured in `~/.pypirc` or environment variables.

## Architecture

### Core Classes

**Podcast (podcast.py)**
- Parses RSS/XML podcast feeds using BeautifulSoup
- Extracts feed-level metadata (title, description, iTunes tags, etc.)
- Contains list of Item objects representing episodes
- Main entry point: `Podcast(feed_content, feed_url=None)`

**Item (item.py)**
- Represents a single podcast episode
- Parses episode-level metadata (title, description, enclosure, etc.)
- Handles iTunes-specific tags and Podcasting 2.0 extensions
- Includes `parse_hms()` utility for converting time formats (hh:mm:ss) to seconds

**MediaResource (media_resource.py)**
- Represents media files (enclosures) associated with episodes
- Handles media metadata (URL, type, size, etc.)

### Key Features

**RSS Parsing**
- Supports standard RSS 2.0 specification
- iTunes podcast extensions
- Podcasting 2.0 namespace extensions
- Uses BeautifulSoup with lxml parser for XML processing

**IPFS Integration (podcast_ipfs_tools.py)**
- Tools for uploading podcast content to IPFS
- Manages IPFS URLs and content addressing
- Supports decentralized podcast distribution

**Media Management (podcast_tools.py)**
- `find_content_item_by_guid()` - Search media resources by GUID
- `download_media()` - Download media files from URLs
- Type hints used throughout for better IDE support

## Package Configuration

**pyproject.toml**
- Modern PEP 517/518 configuration
- Build system: hatchling
- Explicit package discovery: `packages = ["src/pg_podcast_toolkit"]`
- Dependencies: beautifulsoup4, requests, lxml, aioipfs

**Version Management**
- Version is specified in `pyproject.toml` under `[project]` section
- Update version before publishing to PyPI

## Code Conventions

This project follows the conventions defined in the global CLAUDE.md:
- No lambda expressions (use loops for readability)
- Type hints for all function parameters and return types
- Methods should be under 50 lines when possible
- Unix timestamps (not datetime objects) for time storage
- Imports at top of file, organized appropriately
