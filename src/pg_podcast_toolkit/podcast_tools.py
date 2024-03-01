from lxml import etree
import requests
from typing import Dict
from .media_resource import MediaResource

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


def parse_enclosure_map_from_etree(podcast_etree: etree._ElementTree) -> Dict[str, str]:
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


def parse_enclosure_map_from_etree(podcast_etree: etree._ElementTree) -> Dict[str, MediaResource]:
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

