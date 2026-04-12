import pytest
from app.image_utils import validate_url

def test_validate_url_valid():
    # Valid public URL
    is_valid, msg = validate_url("https://images.unsplash.com/photo-123")
    assert is_valid is True

def test_validate_url_private_ip():
    # Private IP check
    is_valid, msg = validate_url("http://192.168.1.1/test.jpg")
    assert is_valid is False
    assert "private" in msg.lower()

def test_validate_url_localhost():
    # Localhost check
    is_valid, msg = validate_url("http://localhost:8080/test.jpg")
    assert is_valid is False
    assert "private ip" in msg.lower() or "blocked hostname" in msg.lower()

def test_validate_url_invalid_scheme():
    # Invalid scheme (ftp)
    is_valid, msg = validate_url("ftp://example.com/test.jpg")
    assert is_valid is False
    assert "scheme" in msg.lower()

def test_validate_url_malformed():
    # Malformed URL
    is_valid, msg = validate_url("not-a-url")
    assert is_valid is False
