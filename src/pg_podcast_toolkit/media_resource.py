from dataclasses import dataclass, field
from typing import Optional
import json

@dataclass
class MediaResource:
    """
    MediaResource represents a media file associated with a content item, focusing on the essential
    attributes of the media itself rather than the full spectrum of item metadata. It is designed
    to encapsulate the details of media content, such as audio or video files, for easy management
    and reference within applications dealing with media distribution, especially in contexts like
    RSS feeds or content management systems.
    
    Attributes:
        guid (Optional[str]): The globally unique identifier for the media file, typically used to identify the media file within a podcast feed or similar content distribution system.
        hash_ipfs (Optional[str]): The IPFS hash of the media file, providing a unique identifier within the IPFS network.
        length (Optional[int]): The size of the media file in bytes.
        file_name (Optional[str]): The name of the media file.
        media_type (Optional[str]): The type of media, such as 'audio/mpeg' or 'video/mp4'.
        local_path (Optional[str]): The local filesystem path to the media file.
        url (Optional[str]): The URL where the media file can be accessed, assuming that every media resource must be identifiable by a URL at minimum.
    """
    guid: Optional[str] = None
    hash_ipfs: Optional[str] = None
    length: Optional[int] = None
    file_name: Optional[str] = None
    media_type: Optional[str] = None
    local_path: Optional[str] = None
    url: Optional[str] = None

    def __str__(self):
        return json.dumps(self.__dict__, indent=4, sort_keys=True)
