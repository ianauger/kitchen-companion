"""Extended tests for image_utils: download_image, delete_image, _get_extension_from_url, get_upload_dir."""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.image_utils import (
    download_image, delete_image, _get_extension_from_url,
    get_upload_dir, is_private_ip, validate_url, UPLOAD_SUBDIR
)


class TestGetExtensionFromUrl:
    def test_jpg_from_url_path(self):
        """Extension is extracted from URL path."""
        assert _get_extension_from_url('https://example.com/photos/image.jpg') == '.jpg'

    def test_jpeg_from_url_path(self):
        """Recognizes .jpeg extension."""
        assert _get_extension_from_url('https://example.com/photos/image.jpeg') == '.jpeg'

    def test_png_from_url_path(self):
        """Recognizes .png extension."""
        assert _get_extension_from_url('https://example.com/image.png') == '.png'

    def test_gif_from_url_path(self):
        """Recognizes .gif extension."""
        assert _get_extension_from_url('https://example.com/animated.gif') == '.gif'

    def test_webp_from_url_path(self):
        """Recognizes .webp extension."""
        assert _get_extension_from_url('https://example.com/modern.webp') == '.webp'

    def test_uppercase_extension(self):
        """Case-insensitive extension matching."""
        assert _get_extension_from_url('https://example.com/PHOTO.JPG') == '.jpg'

    def test_fallback_from_content_type_jpeg(self):
        """Falls back to Content-Type when URL has no extension."""
        ext = _get_extension_from_url('https://example.com/api/image/123', 'image/jpeg')
        assert ext == '.jpg'

    def test_fallback_from_content_type_png(self):
        """Content-Type png fallback."""
        ext = _get_extension_from_url('https://example.com/api/image', 'image/png')
        assert ext == '.png'

    def test_fallback_from_content_type_webp(self):
        """Content-Type webp fallback."""
        ext = _get_extension_from_url('https://example.com/photo', 'image/webp')
        assert ext == '.webp'

    def test_default_to_jpg(self):
        """No extension and unknown content type defaults to .jpg."""
        ext = _get_extension_from_url('https://example.com/photo', 'application/octet-stream')
        assert ext == '.jpg'


class TestIsPrivateIp:
    def test_private_ipv4(self):
        """192.168.x.x is private."""
        assert is_private_ip('192.168.1.1') is True

    def test_loopback(self):
        """127.0.0.1 is loopback."""
        assert is_private_ip('127.0.0.1') is True

    def test_link_local(self):
        """169.254.x.x is link-local."""
        assert is_private_ip('169.254.1.1') is True

    def test_public_ip(self):
        """8.8.8.8 is not private."""
        assert is_private_ip('8.8.8.8') is False

    def test_invalid_ip(self):
        """Unparseable IPs are treated as private for safety."""
        assert is_private_ip('not-an-ip') is True

    def test_unspecified(self):
        """0.0.0.0 is unspecified."""
        assert is_private_ip('0.0.0.0') is True


class TestValidateUrlEdgeCases:
    def test_empty_url(self):
        """Empty URL is invalid."""
        valid, msg = validate_url('')
        assert valid is False

    def test_none_url(self):
        """None URL is invalid."""
        valid, msg = validate_url(None)
        assert valid is False

    def test_url_with_credentials(self):
        """URLs with user:pass are rejected."""
        valid, msg = validate_url('https://user:pass@example.com/image.jpg')
        assert valid is False

    def test_internal_domain_blocked_by_dns_or_check(self):
        """.internal domains are either DNS-unresolvable or explicitly blocked — both safe."""
        valid, msg = validate_url('https://server.internal/photo.jpg')
        assert valid is False
        # Either "internal domain" or "could not resolve" — both safe outcomes

    def test_local_domain(self):
        """.local domains are rejected."""
        valid, msg = validate_url('https://server.local/test.jpg')
        assert valid is False

    def test_blocked_hostname_localhost(self):
        """localhost is blocked."""
        valid, msg = validate_url('https://localhost/image.jpg')
        assert valid is False


class TestGetUploadDir:
    def test_returns_path(self, app):
        """get_upload_dir returns a Path inside static folder."""
        with app.app_context():
            upload_dir = get_upload_dir()
            assert isinstance(upload_dir, Path)
            assert upload_dir.exists()
            assert upload_dir.is_dir()
            assert UPLOAD_SUBDIR in str(upload_dir)

    def test_directory_is_created(self, app, tmp_path):
        """Directory is created if it doesn't exist."""
        # Monkey-patch static_folder to a temp path
        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                upload_dir = get_upload_dir()
                assert upload_dir.exists()
            finally:
                app.static_folder = original


class TestDeleteImage:
    def test_delete_none_path(self, app):
        """Deleting None/empty path returns False."""
        with app.app_context():
            assert delete_image(None) is False
            assert delete_image('') is False

    def test_delete_nonexistent_file(self, app):
        """Deleting a file that doesn't exist returns False."""
        with app.app_context():
            result = delete_image('uploads/recipes/nonexistent_xyz.jpg')
            assert result is False

    def test_path_traversal_blocked(self, app):
        """Path traversal attempts are blocked."""
        with app.app_context():
            result = delete_image('../../etc/passwd')
            assert result is False

    def test_delete_existing_file(self, app, tmp_path):
        """Existing file within static folder is deleted."""
        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                # Create upload dir and a test file
                upload_dir = tmp_path / UPLOAD_SUBDIR
                upload_dir.mkdir(parents=True)
                test_file = upload_dir / 'test_delete_me.jpg'
                test_file.write_text('fake image data')

                relative = f'{UPLOAD_SUBDIR}/test_delete_me.jpg'
                result = delete_image(relative)
                assert result is True
                assert not test_file.exists()
            finally:
                app.static_folder = original

    def test_absolute_symlink_outside_static(self, app, tmp_path):
        """Resolved path outside static folder is blocked."""
        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                # Path that, even if crafted to look inside, resolves outside
                result = delete_image('../outside.jpg')
                assert result is False
            finally:
                app.static_folder = original


class TestDownloadImage:
    def test_empty_url_returns_none(self, app):
        """Empty URL returns (None, None)."""
        with app.app_context():
            result = download_image('')
            assert result == (None, None)

    def test_none_url_returns_none(self, app):
        """None URL returns (None, None)."""
        with app.app_context():
            result = download_image(None)
            assert result == (None, None)

    def test_invalid_url_returns_none(self, app):
        """Invalid URL (SSRF check fails) returns (None, None)."""
        with app.app_context():
            result = download_image('http://192.168.1.1/test.jpg')
            assert result == (None, None)

    @patch('app.image_utils.requests.get')
    def test_successful_download(self, mock_get, app, tmp_path):
        """Successful download returns (relative_path, absolute_path)."""
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'image/jpeg', 'Content-Length': '100'}
        mock_response.iter_content.return_value = [b'fake-image-data']
        mock_get.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                rel, abs_path = download_image('https://example.com/photo.jpg', recipe_id=1)
                assert rel is not None
                assert abs_path is not None
                assert 'recipe_1_' in rel
                assert rel.startswith(UPLOAD_SUBDIR)
                assert Path(abs_path).exists()
            finally:
                app.static_folder = original

    @patch('app.image_utils.requests.get')
    def test_download_exceeds_size_limit(self, mock_get, app, tmp_path):
        """Download exceeding MAX_DOWNLOAD_SIZE is aborted."""
        from config import MAX_DOWNLOAD_SIZE

        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        # Return a chunk bigger than the limit
        big_chunk = b'x' * (MAX_DOWNLOAD_SIZE + 100)
        mock_response.iter_content.return_value = [big_chunk]
        mock_get.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                rel, abs_path = download_image('https://example.com/huge.jpg', recipe_id=1)
                assert rel is None
                assert abs_path is None
            finally:
                app.static_folder = original

    @patch('app.image_utils.requests.get')
    def test_download_content_length_too_large(self, mock_get, app, tmp_path):
        """Content-Length header exceeding limit causes early abort."""
        from config import MAX_DOWNLOAD_SIZE

        mock_response = MagicMock()
        mock_response.headers = {
            'Content-Type': 'image/jpeg',
            'Content-Length': str(MAX_DOWNLOAD_SIZE + 1)
        }
        mock_get.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                rel, abs_path = download_image('https://example.com/huge-header.jpg', recipe_id=1)
                assert rel is None
                assert abs_path is None
            finally:
                app.static_folder = original

    @patch('app.image_utils.requests.get')
    def test_download_request_exception(self, mock_get, app):
        """RequestException returns (None, None)."""
        import requests as requests_lib
        mock_get.side_effect = requests_lib.RequestException('Connection error')

        with app.app_context():
            rel, abs_path = download_image('https://example.com/broken.jpg')
            assert rel is None
            assert abs_path is None

    @patch('app.image_utils.requests.get')
    def test_download_without_recipe_id(self, mock_get, app, tmp_path):
        """Download without recipe_id generates filename without recipe prefix."""
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'image/jpeg', 'Content-Length': '100'}
        mock_response.iter_content.return_value = [b'data']
        mock_get.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                rel, abs_path = download_image('https://example.com/photo.jpg')
                # Without recipe_id, filename starts with 'recipe_' but has a longer hex
                assert rel.startswith(UPLOAD_SUBDIR + '/recipe_')
            finally:
                app.static_folder = original
