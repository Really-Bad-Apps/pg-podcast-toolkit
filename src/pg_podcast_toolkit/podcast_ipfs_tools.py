import asyncio
import logging
import json
from typing import List

from lxml import etree
import aioipfs
from aioipfs import AsyncIPFS as IPFSClient

from .media_resource import MediaResource
from .podcast_tools import find_content_item_by_guid


async def _add_file_to_ipfs(ipfs_client: 'IPFSClient', media_resource: 'MediaResource') -> 'MediaResource':
    """
    Asynchronously adds a file to IPFS using the given IPFS client and updates the media resource with the IPFS hash, file size, and name.

    This internal routine handles the interaction with an IPFS node to store media content. Upon successful addition of the file to IPFS,
    it updates the provided media resource object with the hash, length, and name as reported by IPFS. These details are essential for
    later retrieval and reference of the media file in the IPFS network.

    Parameters:
    - ipfs_client (IPFSClient): An instance of the IPFS client used for communicating with an IPFS node.
    - media_resource (MediaResource): The media resource object containing the local path of the file to be added to IPFS. This object
                                      will be updated with the IPFS hash, file size, and name.

    Returns:
    - MediaResource: The updated media resource object now containing the IPFS hash, file size, and name.

    Raises:
    - The function can raise exceptions related to the IPFS client operations, which should be handled by the caller.

    """
    async for added_file in ipfs_client.add(media_resource.local_path):
        media_resource.hash_ipfs = added_file['Hash']
        media_resource.length = added_file['Size']
        media_resource.file_name = added_file['Name']

    return MediaResource


async def _pin_cid_to_ipfs(ipfs_client: IPFSClient, cid: str):
    """
    Asynchronously pins a CID (Content Identifier) to an IPFS node to ensure its persistence.

    This function iterates over the result of pinning a CID to an IPFS node, effectively requesting
    the IPFS node to keep the content associated with the CID in its local storage indefinitely. This is
    a common practice to ensure that content does not get garbage collected and remains accessible
    over IPFS network.

    Parameters:
    - ipfs_client (IPFSClient): An instance of the IPFS client connected to a specific IPFS node.
    - cid (str): The Content Identifier (CID) of the content to be pinned on the IPFS node.

    Note:
    This function logs an informational message for each CID that is successfully pinned,
    indicating the action has been completed. If the function encounters any issues during
    the pinning process, those should be handled by the caller or within the IPFS client implementation.
    """
    async for pinned in ipfs_client.pin.add(cid, progress=False):
        logging.debug(f"Added {cid} to IPFS pinset")


async def _add_files_to_ipfs(ipfs_gateway: str, lst_media_resources: List[MediaResource]) -> List[MediaResource]:
    """
    Asynchronously adds and pins a list of media resources to an IPFS node specified by the IPFS gateway.

    This function iterates over a list of media resources, adding each to the IPFS network via the specified
    IPFS gateway and then pinning it to ensure its persistence. Each media resource must have a local path
    set; otherwise, an error is logged. The function concludes by closing the connection to the IPFS client.

    Parameters:
    - ipfs_gateway (str): The multiaddress string of the IPFS gateway to connect to.
    - lst_media_resources (List[MediaResource]): A list of media resource objects to be added and pinned
      on IPFS. Each media resource should have a 'local_path' attribute set to the local filesystem path
      of the file to be added.

    Returns:
    - List[MediaResource]: The same list of media resources, now with IPFS hash ('hash_ipfs') and possibly
      other relevant attributes updated to reflect their status on the IPFS network.

    Note:
    This function requires that the 'MediaResource' objects in the list have a 'local_path' attribute set.
    If a 'local_path' is not set for any of the media resources, an error is logged, and the process for that
    specific resource is skipped.
    """
    client = aioipfs.AsyncIPFS(maddr=ipfs_gateway)

    logging.debug(f"Adding {len(lst_media_resources)} files to IPFS")
    for media_resource in lst_media_resources:
        # Ensure the media resource has a local path set
        if media_resource.local_path:
            await _add_file_to_ipfs(client, media_resource)
        else:
            logging.error(f"MediaResource for {media_resource.file_name} does not have a local path set.")

    logging.debug(f"Pinning {len(lst_media_resources)} files to IPFS")
    for media_resource in lst_media_resources:
        # Ensure the media resource has a local path set
        if media_resource.local_path:
            await _pin_cid_to_ipfs(client, media_resource.hash_ipfs)
        else:
            logging.error(f"MediaResource for {media_resource.hash_ipfs} does not have a local path set.")


    await client.close()
    return lst_media_resources


def add_ipfs_alt_enclosures_to_podcast(podcast_etree: etree._ElementTree, lst_media_resource: List[MediaResource]) -> etree._ElementTree:
    """
    Adds alternate enclosures to podcast items using media resources provided.

    This function iterates over each item in the provided podcast RSS feed and attempts to add an
    <podcast:alternateEnclosure> sub-element with attributes derived from the corresponding media resource.
    It requires the podcast namespace to be present in the feed; otherwise, it will raise an exception.
    The function adds or updates the alternate enclosure for items with a matching GUID found in the list
    of media resources.

    Parameters:
    - podcast_etree (etree._ElementTree): The podcast RSS feed represented as an ElementTree object.
    - lst_media_resource (List[MediaResource]): A list of media resources containing the data needed to
      construct the alternate enclosure elements. Each media resource should have attributes like
      hash_ipfs, media_type, and file_name.

    Returns:
    - etree._ElementTree: The modified podcast RSS feed ElementTree object with added or updated
      alternate enclosures for items.

    Raises:
    - Exception: If the podcast namespace is not found in the RSS feed, indicating that the feed does not
      support Podcasting 2.0 specifications necessary for alternate enclosures.

    Example:
    Assuming you have an ElementTree object `podcast_etree` representing your podcast RSS feed and a list
    `media_resources` containing media resources with IPFS hashes, media types, and filenames, you can add
    alternate enclosures as follows:
    ```python
    updated_podcast_etree = add_ipfs_alt_enclosures_to_podcast(podcast_etree, media_resources)
    ```

    Note:
    The function checks for the presence of a GUID for each item in the feed and skips items without one.
    It also checks if an item already has an <podcast:alternateEnclosure> to avoid duplicates, using the existing
    enclosure if present. The media resource is identified by matching the item's GUID with the media resource's GUID.
    """
    # Assuming we want to add a <podcast:alternateEnclosure> to <item>
    # find the podcast namespace
    namespace_map = podcast_etree.getroot().nsmap
    
    # there is no easy way to add a new namespace to the etree, so we need to check if the podcast namespace is present
    # and bail if it's not.
    if 'podcast' not in namespace_map:
        raise Exception("Podcast namespace not found in RSS feed. We need a podcasting 2.0 feed to add alternate enclosures.")
    
    podcast_ns = namespace_map['podcast']

    # Find all item elements in the RSS feed
    items = podcast_etree.findall('.//item')

    # Loop through each item and add a new sub-element
    for item in items:
        guid = item.find('guid').text if item.find('guid') is not None else None

        # skip elements without a guid
        if not guid:
            logging.warning("add_ipfs_alt_enclosures_to_podcast: Skipping item without guid")
            continue

        # find the content item with the matching guid
        media_resource = find_content_item_by_guid(guid, lst_media_resource)

        # skip missing content items
        if not media_resource or not media_resource.hash_ipfs:
            logging.error(f"Skipping item without media resource for guid {guid}")
            continue

        logging.debug(f"Adding alternate enclosure for {media_resource.hash_ipfs}")

        # Construct the namespaced tag for alternateEnclosure
        alt_enclosure_tag = f"{{{podcast_ns}}}alternateEnclosure"

        # Check if an alternateEnclosure already exists
        existing_alt_enclosure = item.find(alt_enclosure_tag)
        if existing_alt_enclosure is None:
            # If it does not exist, create it
            alt_enclosure_element = etree.SubElement(item, alt_enclosure_tag)
        else:
            # If it exists, use the existing element
            alt_enclosure_element = existing_alt_enclosure

        alt_enclosure_element.set("type", media_resource.media_type)
        alt_enclosure_element.set("length", media_resource.length)
        
        # create the podcast source element
        podcast_source_elt = etree.SubElement(alt_enclosure_element, f"{{{podcast_ns}}}source")
        podcast_source_elt.set("uri", "ipfs://" + media_resource.hash_ipfs + "?filename=" + media_resource.file_name)

    return podcast_etree


def add_files_to_ipfs(lst_media_resources: List[MediaResource], ipfs_gateway: str = '/ip4/127.0.0.1/tcp/5001') -> List[MediaResource]:
    """
    Uploads a list of media resources to IPFS and pins them.

    This function takes a list of media resources, each represented by a MediaResource object, and uploads them to
    an IPFS node specified by the ipfs_gateway parameter. It uses an asynchronous helper function to perform the
    upload and pinning tasks. The function waits for the asynchronous tasks to complete and returns a list of media
    resources with updated IPFS hash, size, and name attributes reflecting the uploaded content.

    Parameters:
    - lst_media_resources (List[MediaResource]): A list of MediaResource objects representing the media files to be
      uploaded. Each MediaResource should at least have a `local_path` attribute pointing to the file's location on
      the local filesystem.
    - ipfs_gateway (str, optional): The address of the IPFS node to which the files will be uploaded. Defaults to
      '/ip4/127.0.0.1/tcp/5001', which is the default address for a locally running IPFS node.

    Returns:
    - List[MediaResource]: The same list of media resources passed in, but updated to include the IPFS hash (`hash_ipfs`),
      size (`length`), and possibly updated filename (`file_name`) for each uploaded file.

    Example:
    Assuming you have a list `media_resources` containing MediaResource objects with `local_path` defined, you can
    upload and pin them to IPFS as follows:
    ```python
    updated_media_resources = add_files_to_ipfs(media_resources, '/ip4/127.0.0.1/tcp/5001')
    ```
    """
    # upload all content to IPFS
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_add_files_to_ipfs(ipfs_gateway, lst_media_resources))
