"""Image handling utilities for Kitchen Companion."""
import os
import uuid
import requests
import socket
import ipaddress
from pathlib import Path
from urllib.parse import urlparse
from flask import current_app
from config import MAX_DOWNLOAD_SIZE, DOWNLOAD_TIMEOUT, DOWNLOAD_CHUNK_SIZE


# Directory where recipe images are stored (relative to app/static)
UPLOAD_SUBDIR = 'uploads/recipes'


def get_upload_dir():
    """Get the absolute path to the recipe image upload directory.
    
    Creates the directory if it doesn't exist.
    
    Returns:
        Path: Absolute path to the upload directory
    """
    upload_dir = Path(current_app.static_folder) / UPLOAD_SUBDIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def is_private_ip(ip_str):
    """Check if an IP address is private/internal.
    
    Args:
        ip_str: IP address string
    
    Returns:
        bool: True if the IP is private
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        # Check for private, loopback, link-local, multicast, and reserved ranges
        return (
            ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_multicast or
            ip.is_reserved or
            ip.is_unspecified
        )
    except ValueError:
        return True  # Treat unparseable as private to be safe


def validate_url(url):
    """Validate a URL for SSRF prevention.
    
    Performs the following checks:
    1. URL scheme must be http or https
    2. Hostname resolves to a non-private IP
    3. No credentials in URL
    
    Args:
        url: The URL to validate
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not url:
        return False, "URL is empty"
    
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"
    
    # Check scheme
    if parsed.scheme not in ('http', 'https'):
        return False, f"Invalid URL scheme: {parsed.scheme}"
    
    # Check for credentials in URL (user:pass@host)
    if parsed.username or parsed.password:
        return False, "URLs with credentials are not allowed"
    
    # Get hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"
    
    # Check for IP address literals
    try:
        # If it's already an IP, check if it's private
        ip = ipaddress.ip_address(hostname)
        if is_private_ip(str(ip)):
            return False, "Private IP addresses are not allowed"
    except ValueError:
        # It's a hostname, resolve it
        pass
    
    # Resolve hostname to IP(s)
    try:
        # Get all addresses for the hostname
        addr_info = socket.getaddrinfo(hostname, None)
        for info in addr_info:
            ip_str = info[4][0]
            if is_private_ip(ip_str):
                return False, f"Hostname resolves to private IP: {ip_str}"
    except socket.gaierror:
        return False, "Could not resolve hostname"
    except Exception as e:
        return False, f"Error resolving hostname: {str(e)}"
    
    # Check for common SSRF bypass techniques
    blocked_hosts = [
        'localhost',
        '127.0.0.1',
        '0.0.0.0',
        '::1',
        '[::1]',
        'metadata.google.internal',
        '169.254.169.254',  # AWS/Cloud metadata
    ]
    
    hostname_lower = hostname.lower()
    for blocked in blocked_hosts:
        if hostname_lower == blocked or hostname_lower.endswith('.' + blocked):
            return False, "Blocked hostname"
    
    # Check for internal domain patterns
    if hostname_lower.endswith('.internal') or hostname_lower.endswith('.local'):
        return False, "Internal domain names are not allowed"
    
    return True, None


def download_image(image_url, recipe_id=None):
    """Download an image from a URL and save it locally.
    
    Args:
        image_url: The URL of the image to download
        recipe_id: Optional recipe ID to include in the filename
    
    Returns:
        tuple: (local_relative_path, absolute_path) or (None, None) on failure
        
    The local_relative_path is suitable for use in url_for('static', filename=...)
    The absolute_path is the full filesystem path
    """
    if not image_url:
        return None, None
    
    # Validate URL before downloading (SSRF prevention)
    is_valid, error_msg = validate_url(image_url)
    if not is_valid:
        current_app.logger.warning(f'URL validation failed for {image_url}: {error_msg}')
        return None, None
    
    try:
        response = requests.get(
            image_url, 
            timeout=DOWNLOAD_TIMEOUT, 
            stream=True,
            allow_redirects=True,
            headers={
                'User-Agent': 'Kitchen-Companion/1.0'
            }
        )
        response.raise_for_status()
        
        # Check content length if available
        content_length = response.headers.get('Content-Length')
        if content_length:
            if int(content_length) > MAX_DOWNLOAD_SIZE:
                current_app.logger.warning(f'Image too large: {content_length} bytes')
                return None, None
        
        # Determine file extension from URL or Content-Type
        content_type = response.headers.get('Content-Type', '')
        ext = _get_extension_from_url(image_url, content_type)
        
        # Generate a unique filename
        if recipe_id:
            filename = f'recipe_{recipe_id}_{uuid.uuid4().hex[:8]}{ext}'
        else:
            filename = f'recipe_{uuid.uuid4().hex[:12]}{ext}'
        
        # Save to upload directory
        upload_dir = get_upload_dir()
        absolute_path = upload_dir / filename
        relative_path = f'{UPLOAD_SUBDIR}/{filename}'
        
        # Download with size limit
        downloaded_size = 0
        with open(absolute_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                downloaded_size += len(chunk)
                if downloaded_size > MAX_DOWNLOAD_SIZE:
                    current_app.logger.warning(f'Image download exceeded max size')
                    # Clean up partial file
                    f.close()
                    absolute_path.unlink(missing_ok=True)
                    return None, None
                f.write(chunk)
        
        current_app.logger.info(f'Downloaded image from {image_url} -> {relative_path}')
        return relative_path, str(absolute_path)
        
    except requests.RequestException as e:
        current_app.logger.warning(f'Failed to download image from {image_url}: {e}')
        return None, None
    except IOError as e:
        current_app.logger.warning(f'Failed to save image from {image_url}: {e}')
        return None, None


def _get_extension_from_url(url, content_type=''):
    """Determine file extension from URL path and content type.
    
    Args:
        url: The image URL
        content_type: The Content-Type header from the response
    
    Returns:
        str: File extension including the dot (e.g., '.jpg')
    """
    # Try to get extension from URL first
    parsed = urlparse(url)
    path = parsed.path
    
    # Common image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
    
    # Check if the URL path ends with an image extension
    path_lower = path.lower()
    for ext in image_extensions:
        if path_lower.endswith(ext):
            return ext
    
    # Fall back to content type
    content_type = content_type.lower()
    mime_map = {
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/bmp': '.bmp',
        'image/svg+xml': '.svg',
    }
    
    for mime, ext in mime_map.items():
        if mime in content_type:
            return ext
    
    # Default to .jpg
    return '.jpg'


def delete_image(image_path):
    """Delete a locally stored image file.
    
    Args:
        image_path: The relative path stored in the database (e.g., 'uploads/recipes/recipe_1_xxx.jpg')
    
    Returns:
        bool: True if file was deleted, False otherwise
    """
    if not image_path:
        return False
    
    try:
        absolute_path = Path(current_app.static_folder) / image_path
        
        # Security: Ensure the resolved path is within the static folder
        resolved_path = absolute_path.resolve()
        resolved_static = Path(current_app.static_folder).resolve()
        if not str(resolved_path).startswith(str(resolved_static)):
            current_app.logger.warning(f'Blocked path escape attempt: {image_path}')
            return False
        
        if absolute_path.exists():
            absolute_path.unlink()
            current_app.logger.info(f'Deleted image: {image_path}')
            return True
    except Exception as e:
        current_app.logger.warning(f'Failed to delete image {image_path}: {e}')
    
    return False
