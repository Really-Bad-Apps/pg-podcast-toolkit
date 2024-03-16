from lxml import etree
import requests
import logging
import os
from typing import Dict, List, Optional

from .media_resource import MediaResource


def find_content_item_by_guid(guid: str, lst_media_resources: List[MediaResource]) -> Optional[MediaResource]:
    """
    Searches for a media resource in a list of media resources by GUID.

    This function iterates through a given list of media resources, looking for a media resource with a GUID that matches
    the provided `guid` parameter. If a matching media resource is found, it is returned; otherwise, `None` is returned,
    indicating that no matching media resource was found in the list.

    Parameters:
    - guid (str): The globally unique identifier (GUID) of the media resource to search for.
    - lst_media_resources (List[MediaResource]): A list of MediaResource objects to search through. Each MediaResource
      object in the list should have a `guid` attribute.

    Returns:
    - MediaResource or None: Returns the MediaResource object that matches the provided GUID if found; otherwise, returns
      None.
    """
    for media_resource in lst_media_resources:
        if media_resource.guid == guid:
            return media_resource
        
    return None


def download_media(media_resource_map: Dict[str, MediaResource], destination_dir: str) -> List[MediaResource]:
    """
    Downloads media files from a given map of GUIDs to MediaResource instances and updates each MediaResource with the local path where the file was saved. This function returns a list of the updated MediaResource instances.

    Args:
        media_resource_map (Dict[str, MediaResource]): A dictionary mapping GUIDs of podcast episodes to their corresponding MediaResource instances. Each MediaResource must contain a valid URL to the media file.
        destination_dir (str): The directory where media files will be saved. The directory will be created if it does not exist.

    Returns:
        List[MediaResource]: A list of MediaResource instances that have been updated with the local path of the downloaded media files. This allows for easy access to the downloaded content and its metadata.
    """
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    lst_media_resources = []
    for guid, media_resource in media_resource_map.items():
        # Download the file from the media resource's URL into the specified directory
        try:
            response = requests.get(media_resource.url)
            response.raise_for_status()  # To ensure we catch HTTP errors

            # Extract filename from MediaResource or use GUID if not available
            filename = media_resource.file_name if media_resource.file_name else f"{guid}.mp3"
            file_path = os.path.join(destination_dir, filename)

            with open(file_path, 'wb') as file:
                file.write(response.content)

            # Update MediaResource with the local path
            media_resource.local_path = file_path
            lst_media_resources.append(media_resource)
            logging.info(f"Downloaded {media_resource.url} to {file_path}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading {media_resource.url}: {e}")

    return lst_media_resources            


def load_podcast_from_url_into_etree(url: str) -> etree.ElementTree:
    """
    Fetches a podcast RSS XML from a given URL and parses it into an lxml ElementTree object.

    Args:
        url (str): The URL of the RSS file to be fetched and loaded.

    Returns:
        etree.ElementTree: An ElementTree object representing the loaded podcast RSS XML.
    """
    # Attempt to fetch the content from the URL
    response = requests.get(url)
    response.raise_for_status()  # Raises an HTTPError if the response was unsuccessful

    # Parse the XML content
    element = etree.fromstring(response.content)

    # Convert the _Element to an ElementTree
    return etree.ElementTree(element)


def load_podcast_file_into_etree(file_path: str) -> etree.ElementTree:
    """
    Loads a podcast XML file from a given file path into an lxml ElementTree object.
    
    Args:
        file_path (str): The path to the XML file to be loaded.
        
    Returns:
        etree.ElementTree: An ElementTree object representing the loaded podcast XML.
    """
    with open(file_path, 'r') as f:
        return etree.parse(f)
    

def load_podcast_str_into_etree(podcast_str: str) -> etree.ElementTree:
    """
    Parses a podcast XML string into an lxml ElementTree object.
    
    Args:
        podcast_str (str): The podcast XML string to be parsed.
        
    Returns:
        etree.ElementTree: An ElementTree object representing the parsed podcast XML.
    """
    return etree.fromstring(podcast_str)


def retreive_podcast_xml(url: str) -> str:
    """
    Retrieves the XML content of a podcast from a specified URL.
    
    Args:
        url (str): The URL from which to fetch the podcast XML.
        
    Returns:
        str: The XML content of the podcast as a string.
    """
    response = requests.get(url)
    response.raise_for_status()  # Raises an HTTPError if the response was an unsuccessful status code
    return response.text


def extract_enclosures(podcast_etree: etree._ElementTree) -> Dict[str, str]:
    """
    Parses a podcast XML loaded as an lxml ElementTree object to extract a mapping of episode GUIDs to enclosure URLs.
    
    Args:
        podcast_etree (etree._ElementTree): The podcast XML loaded as an lxml ElementTree object.
        
    Returns:
        Dict[str, str]: A dictionary mapping GUIDs of podcast episodes to their corresponding enclosure URLs.
    """
    enclosure_map = {}
    for item in podcast_etree.iter('item'):
        guid = item.find('guid').text if item.find('guid') is not None else None
        enclosure = item.find('enclosure')
        if guid and enclosure is not None:
            enclosure_map[guid] = enclosure.attrib.get('url')
    return enclosure_map


def extract_enclosures(podcast_etree: etree._ElementTree) -> Dict[str, MediaResource]:
    """
    Parses a podcast XML loaded as an lxml ElementTree object to extract a mapping of episode GUIDs to MediaResource instances.
    
    Args:
        podcast_etree (etree._ElementTree): The podcast XML loaded as an lxml ElementTree object.
        
    Returns:
        Dict[str, MediaResource]: A dictionary mapping GUIDs of podcast episodes to their corresponding MediaResource instances.
    """
    enclosure_map = {}
    for item in podcast_etree.iterfind('.//item'):
        guid = item.find('./guid').text if item.find('./guid') is not None else None
        enclosure = item.find('./enclosure')
        if guid and enclosure is not None:
            url = enclosure.attrib.get('url')
            length = int(enclosure.attrib.get('length', 0)) if enclosure.attrib.get('length') else None
            media_type = enclosure.attrib.get('type', None)
            # Example placeholders, adjust as needed
            hash_ipfs, file_name, local_path = None, None, None
            media_resource = MediaResource(
                guid=guid,
                url=url,
                length=length,
                media_type=media_type,
                hash_ipfs=hash_ipfs,
                file_name=file_name,
                local_path=local_path,
            )
            enclosure_map[guid] = media_resource

    return enclosure_map

