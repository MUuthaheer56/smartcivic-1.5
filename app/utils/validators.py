import re
from PIL import Image
from config import SLA_HOURS

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^\d{10}$")

def validate_email(email):
    if not email or not EMAIL_REGEX.match(email):
        return False, "Invalid email format"
    return True, None

def validate_phone(phone):
    if not phone or not PHONE_REGEX.match(phone):
        return False, "Phone must be exactly 10 digits"
    return True, None

def validate_password(password):
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long"
    return True, None

def validate_category(category):
    if category not in SLA_HOURS:
        return False, f"Category must be one of: {', '.join(SLA_HOURS.keys())}"
    return True, None

def validate_location(lat, lng):
    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return False, "Coordinates must be numbers"
        
    # Bengaluru coordinates bounds
    if not (12.8 <= lat <= 13.2):
        return False, "Latitude must be within Bengaluru bounds (12.8 to 13.2)"
    if not (77.4 <= lng <= 77.8):
        return False, "Longitude must be within Bengaluru bounds (77.4 to 77.8)"
        
    return True, None

def validate_description(description):
    if not description or len(description) < 10 or len(description) > 500:
        return False, "Description must be between 10 and 500 characters"
    return True, None

def validate_image(file_storage):
    """
    Validate image file size, magic bytes (mimetype), and integrity using Pillow.
    """
    if not file_storage:
        return False, "No file uploaded"
        
    # Check file size (max 10MB)
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    
    if size > 10 * 1024 * 1024:
         return False, "Image size exceeds maximum limit of 10MB"
         
    # Read first 12 bytes to check magic bytes
    header = file_storage.read(12)
    file_storage.seek(0)
    
    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = header.startswith(b"\xff\xd8\xff")
    is_webp = len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    
    if not (is_png or is_jpeg or is_webp):
        return False, "Invalid image format. Allowed: PNG, JPEG, JPG, WEBP"
        
    # Verify image integrity using Pillow
    try:
        img = Image.open(file_storage)
        img.verify()
        file_storage.seek(0)
    except Exception:
        file_storage.seek(0)
        return False, "Corrupted image file structure"
        
    return True, None
