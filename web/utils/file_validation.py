"""
File upload validation utilities for security
"""
import os
from pathlib import Path
from PIL import Image
from web.exceptions import FileUploadError, ValidationError
import logging

logger = logging.getLogger(__name__)

# Allowed file types by category
ALLOWED_IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'}
ALLOWED_VIDEO_TYPES = {'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo', 'video/webm', 'video/x-matroska'}
ALLOWED_AUDIO_TYPES = {'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg'}

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a'}

# File size limits (in bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 1024 * 1024 * 1024  # 1 GB
MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_THUMBNAIL_SIZE = 10 * 1024 * 1024  # 10 MB


def get_file_mime_type(file_path):
    """Get MIME type from file extension"""
    ext = Path(file_path).suffix.lower()
    mime_map = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.m4a': 'audio/mp4'
    }
    return mime_map.get(ext, 'application/octet-stream')


def validate_image_file(file, max_size=MAX_IMAGE_SIZE):
    """
    Validate an image file upload
    
    Args:
        file: FileStorage object from Flask
        max_size: Maximum file size in bytes
    
    Returns:
        dict: {'valid': True/False, 'error': str if invalid}
    
    Raises:
        FileUploadError: If file is invalid
    """
    if not file or not file.filename:
        raise FileUploadError("No file provided")
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > max_size:
        raise FileUploadError(f"File too large. Maximum size: {max_size / (1024*1024):.1f} MB")
    
    if file_size == 0:
        raise FileUploadError("File is empty")
    
    # Check extension
    filename = file.filename.lower()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise FileUploadError(f"Invalid image format. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")
    
    # Verify it's actually an image by trying to open it
    try:
        file.seek(0)
        img = Image.open(file)
        img.verify()  # Verify it's a valid image
        file.seek(0)  # Reset for actual use
        
        # Additional check: ensure it's a recognized format
        if img.format not in ['PNG', 'JPEG', 'GIF', 'WEBP']:
            raise FileUploadError(f"Unsupported image format: {img.format}")
    except Exception as e:
        raise FileUploadError(f"File is not a valid image: {str(e)}")
    
    return {'valid': True, 'size': file_size, 'format': img.format}


def validate_audio_file(file, max_size=MAX_AUDIO_SIZE):
    """
    Validate an audio file upload (basic validation - size and extension)
    
    Args:
        file: FileStorage object from Flask
        max_size: Maximum file size in bytes
    
    Returns:
        dict: {'valid': True/False, 'error': str if invalid}
    
    Raises:
        FileUploadError: If file is invalid
    """
    validate_file_size(file, max_size)
    
    # Check extension
    filename = file.filename.lower()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise FileUploadError(f"Invalid audio format. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}")
    
    return {'valid': True}

def validate_video_file(file, max_size=MAX_VIDEO_SIZE):
    """
    Validate a video file upload
    
    Args:
        file: FileStorage object from Flask
        max_size: Maximum file size in bytes
    
    Returns:
        dict: {'valid': True/False, 'error': str if invalid}
    
    Raises:
        FileUploadError: If file is invalid
    """
    if not file or not file.filename:
        raise FileUploadError("No file provided")
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > max_size:
        raise FileUploadError(f"File too large. Maximum size: {max_size / (1024*1024*1024):.1f} GB")
    
    if file_size == 0:
        raise FileUploadError("File is empty")
    
    # Check extension
    filename = file.filename.lower()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise FileUploadError(f"Invalid video format. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}")
    
    # Basic magic bytes check for common video formats
    file.seek(0)
    header = file.read(12)
    file.seek(0)
    
    # Check for common video file signatures
    is_video = False
    if header.startswith(b'\x00\x00\x00\x18ftyp') or header.startswith(b'\x00\x00\x00\x20ftyp'):  # MP4
        is_video = True
    elif header.startswith(b'RIFF') and b'AVI ' in header[:12]:  # AVI
        is_video = True
    elif header.startswith(b'\x1a\x45\xdf\xa3'):  # Matroska (MKV/WebM)
        is_video = True
    elif header[4:8] == b'ftyp':  # QuickTime/MOV
        is_video = True
    
    if not is_video:
        logger.warning(f"Video file magic bytes check failed for {filename}")
        # Don't reject - extension check is primary, magic bytes are secondary
    
    return {'valid': True, 'size': file_size}


def validate_file_size(file, max_size):
    """Validate file size"""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > max_size:
        raise FileUploadError(f"File too large. Maximum: {max_size / (1024*1024):.1f} MB")
    
    if size == 0:
        raise FileUploadError("File is empty")
    
    return True


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal and other attacks
    
    Args:
        filename: Original filename
    
    Returns:
        str: Sanitized filename
    """
    # Remove path components
    filename = Path(filename).name
    
    # Remove dangerous characters
    dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename

