"""
Security-critical tests covering:

- _SSRFSafeAdapter: DNS rebinding TOCTOU window, multi-address responses,
  IPv6 private addresses, gaierror wrapping
- validate_url: IPv6 literal address blocking
- _is_safe_redirect_url: open-redirect attack vectors
- SERVICE_API_KEY / _VirtualServiceUser: global service-account auth
- download_image: per-hop redirect SSRF validation
"""
import socket
import pytest
import requests
from unittest.mock import patch, MagicMock

from app import db
from app.auth import User, _is_safe_redirect_url, _authenticate_api_key, _VirtualServiceUser
from app.image_utils import validate_url, _SSRFSafeAdapter, is_private_ip


# ===========================================================================
# _SSRFSafeAdapter — DNS rebinding and IP re-validation at send() time
# ===========================================================================

class TestSSRFSafeAdapter:
    """The adapter must re-check resolved IPs at TCP-connect time, independently
    of any earlier validate_url() call, to close the TOCTOU DNS-rebinding window."""

    def _req(self, url):
        r = MagicMock()
        r.url = url
        return r

    def test_blocks_private_ipv4_at_send_time(self):
        """Adapter raises ConnectionError when DNS resolves to a private IPv4 at send()."""
        private = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.100', 80))]
        with patch('app.image_utils.socket.getaddrinfo', return_value=private):
            with pytest.raises(requests.exceptions.ConnectionError, match='SSRF blocked'):
                _SSRFSafeAdapter().send(self._req('http://example.com/image.jpg'))

    def test_dns_rebinding_attack_caught(self):
        """DNS rebinding: hostname looked clean to validate_url() but flips to
        private at send() time. The adapter catches this after the flip."""
        # Simulates the attacker's DNS flipping between the two checks.
        rebind = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1', 80))]
        with patch('app.image_utils.socket.getaddrinfo', return_value=rebind):
            with pytest.raises(requests.exceptions.ConnectionError, match='SSRF blocked'):
                _SSRFSafeAdapter().send(self._req('http://rebind.attacker.example/photo.jpg'))

    def test_any_private_in_multi_address_response_blocks(self):
        """If ANY address in a multi-IP DNS response is private, the request is blocked.
        An attacker may return one legitimate IP to pass early checks while the
        connection later picks the private one."""
        mixed = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 80)),      # public
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.10.10.10', 80)),   # private
        ]
        with patch('app.image_utils.socket.getaddrinfo', return_value=mixed):
            with pytest.raises(requests.exceptions.ConnectionError, match='SSRF blocked'):
                _SSRFSafeAdapter().send(self._req('http://cdn.example.com/img.jpg'))

    def test_gaierror_raises_connection_error_with_message(self):
        """socket.gaierror during re-resolution is wrapped into a ConnectionError
        whose message includes the hostname, so callers can log it meaningfully."""
        with patch('app.image_utils.socket.getaddrinfo', side_effect=socket.gaierror('NXDOMAIN')):
            with pytest.raises(requests.exceptions.ConnectionError, match='DNS resolution failed'):
                _SSRFSafeAdapter().send(self._req('http://vanished.example.com/photo.jpg'))

    def test_public_ip_passes_through_to_super_send(self):
        """All-public DNS response lets super().send() proceed; the adapter is transparent."""
        public = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]
        mock_resp = MagicMock()
        with patch('app.image_utils.socket.getaddrinfo', return_value=public):
            with patch.object(requests.adapters.HTTPAdapter, 'send', return_value=mock_resp) as super_send:
                result = _SSRFSafeAdapter().send(self._req('https://cdn.example.com/img.jpg'))
        assert result is mock_resp
        super_send.assert_called_once()

    def test_blocks_ipv6_private_unique_local(self):
        """fc00::/7 (unique-local / ULA) IPv6 address returned by DNS is blocked."""
        ipv6_ula = [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('fc00::1', 80, 0, 0))]
        with patch('app.image_utils.socket.getaddrinfo', return_value=ipv6_ula):
            with pytest.raises(requests.exceptions.ConnectionError, match='SSRF blocked'):
                _SSRFSafeAdapter().send(self._req('http://ipv6-host.example.com/img.jpg'))

    def test_blocks_ipv6_loopback(self):
        """::1 (IPv6 loopback) returned by DNS is blocked."""
        ipv6_loopback = [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('::1', 80, 0, 0))]
        with patch('app.image_utils.socket.getaddrinfo', return_value=ipv6_loopback):
            with pytest.raises(requests.exceptions.ConnectionError, match='SSRF blocked'):
                _SSRFSafeAdapter().send(self._req('http://loopback-v6.example.com/img.jpg'))

    def test_blocks_ipv6_link_local(self):
        """fe80::/10 (link-local) IPv6 address returned by DNS is blocked."""
        ipv6_ll = [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('fe80::1', 80, 0, 0))]
        with patch('app.image_utils.socket.getaddrinfo', return_value=ipv6_ll):
            with pytest.raises(requests.exceptions.ConnectionError, match='SSRF blocked'):
                _SSRFSafeAdapter().send(self._req('http://link-local-v6.example.com/img.jpg'))

    def test_uses_https_port_443_when_no_explicit_port(self):
        """HTTPS URLs without an explicit port use 443 for the getaddrinfo call."""
        public = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]
        mock_resp = MagicMock()
        with patch('app.image_utils.socket.getaddrinfo', return_value=public) as mock_gai:
            with patch.object(requests.adapters.HTTPAdapter, 'send', return_value=mock_resp):
                _SSRFSafeAdapter().send(self._req('https://secure.example.com/img.jpg'))
        _args, _kwargs = mock_gai.call_args
        assert _args[1] == 443


# ===========================================================================
# validate_url — IPv6 literal addresses
# ===========================================================================

class TestValidateUrlIPv6:
    """validate_url must reject IPv6 private/reserved addresses in URL literals."""

    def test_ipv6_loopback_literal_blocked(self):
        """http://[::1]/ is blocked — IPv6 loopback."""
        valid, _ = validate_url('http://[::1]/image.jpg')
        assert valid is False

    def test_ipv6_link_local_literal_blocked(self):
        """http://[fe80::1]/ is blocked — IPv6 link-local."""
        valid, _ = validate_url('http://[fe80::1]/image.jpg')
        assert valid is False

    def test_ipv6_unique_local_literal_blocked(self):
        """http://[fc00::1]/ is blocked — IPv6 unique-local (ULA)."""
        valid, _ = validate_url('http://[fc00::1]/image.jpg')
        assert valid is False

    def test_ipv6_unspecified_literal_blocked(self):
        """http://[::]/ is blocked — IPv6 unspecified address."""
        valid, _ = validate_url('http://[::]/image.jpg')
        assert valid is False

    def test_ipv4_mapped_loopback_literal_blocked(self):
        """http://[::ffff:127.0.0.1]/ is blocked — IPv4-mapped loopback.
        Python 3.11 correctly identifies this as private/loopback."""
        valid, _ = validate_url('http://[::ffff:127.0.0.1]/image.jpg')
        assert valid is False

    def test_ipv4_mapped_private_literal_blocked(self):
        """http://[::ffff:192.168.1.1]/ is blocked — IPv4-mapped private address."""
        valid, _ = validate_url('http://[::ffff:192.168.1.1]/image.jpg')
        assert valid is False


# ===========================================================================
# _is_safe_redirect_url — open-redirect attack vectors
# ===========================================================================

class TestIsSafeRedirectUrl:
    """_is_safe_redirect_url must accept same-origin paths and reject all
    cross-origin redirect tricks."""

    def test_plain_relative_path_accepted(self, app):
        """A plain relative path on the same host is allowed."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('/recipes') is True

    def test_root_path_accepted(self, app):
        """Root path / is allowed."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('/') is True

    def test_relative_path_with_query_accepted(self, app):
        """A relative path with a query string is allowed."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('/search?q=pasta') is True

    def test_empty_string_rejected(self, app):
        """Empty string is not a safe target."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('') is False

    def test_none_rejected(self, app):
        """None is not a safe target."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url(None) is False

    def test_absolute_external_https_rejected(self, app):
        """Absolute URL to a different host via HTTPS is blocked."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('https://evil.com/steal') is False

    def test_absolute_external_http_rejected(self, app):
        """Absolute URL to a different host via HTTP is blocked."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('http://attacker.example.com/page') is False

    def test_protocol_relative_url_rejected(self, app):
        """Protocol-relative URL //evil.com is blocked.
        urljoin copies the base scheme, making this https://evil.com — different netloc."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('//evil.com/steal') is False

    def test_triple_slash_resolves_to_same_origin(self, app):
        """///evil.com/ resolves to http://localhost/evil.com/ via Python's urljoin
        (RFC 3986: empty authority inherits base netloc), so it is same-origin and
        safe from Flask's perspective. Documents expected behaviour — not a bypass."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('///evil.com/') is True

    def test_javascript_scheme_rejected(self, app):
        """javascript: pseudo-scheme is blocked (scheme not in http/https)."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('javascript:alert(1)') is False

    def test_data_scheme_rejected(self, app):
        """data: scheme is blocked."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('data:text/html,<h1>hi</h1>') is False

    def test_ftp_scheme_rejected(self, app):
        """ftp: scheme is blocked."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('ftp://evil.com/file') is False

    def test_url_with_embedded_userinfo_rejected(self, app):
        """user@evil.com style URL is blocked."""
        with app.test_request_context('/'):
            assert _is_safe_redirect_url('https://user@evil.com/') is False


# ===========================================================================
# SERVICE_API_KEY / _VirtualServiceUser
# ===========================================================================

class TestVirtualServiceUser:
    """_VirtualServiceUser must present as admin with no persistent identity."""

    def test_role_is_admin(self):
        u = _VirtualServiceUser()
        assert u.role == 'admin'

    def test_id_is_none(self):
        """No database row — id must be None so callers don't try a DB lookup."""
        u = _VirtualServiceUser()
        assert u.id is None

    def test_username_is_service_account(self):
        u = _VirtualServiceUser()
        assert u.username == 'service-account'

    def test_to_dict_contains_only_username_and_role(self):
        """to_dict must NOT leak any credential-adjacent fields."""
        d = _VirtualServiceUser().to_dict()
        assert d == {'username': 'service-account', 'role': 'admin'}
        for sensitive in ('password', 'api_key', 'hash', 'token'):
            assert not any(sensitive in k for k in d)


class TestServiceApiKeyAuthentication:
    """_authenticate_api_key and the editor_or_admin decorator must honour the
    global SERVICE_API_KEY environment variable."""

    def test_correct_service_key_returns_virtual_user(self, app):
        with patch('app.auth.SERVICE_API_KEY', 'super-secret-svc-key'):
            with app.test_request_context('/', headers={'X-API-Key': 'super-secret-svc-key'}):
                result = _authenticate_api_key()
        assert isinstance(result, _VirtualServiceUser)

    def test_wrong_service_key_returns_none(self, app):
        """A key that doesn't match SERVICE_API_KEY is not authenticated as service."""
        with patch('app.auth.SERVICE_API_KEY', 'correct-svc-key'):
            with app.test_request_context('/', headers={'X-API-Key': 'wrong-key'}):
                result = _authenticate_api_key()
        assert result is None

    def test_no_service_key_env_var_skips_service_path(self, app):
        """When SERVICE_API_KEY env var is unset, service-key code path is skipped entirely."""
        with patch('app.auth.SERVICE_API_KEY', None):
            with app.test_request_context('/', headers={'X-API-Key': 'any-key-value'}):
                result = _authenticate_api_key()
        assert result is None

    def test_missing_header_returns_none(self, app):
        """No X-API-Key header → _authenticate_api_key returns None immediately."""
        with app.test_request_context('/'):
            result = _authenticate_api_key()
        assert result is None

    def test_service_key_grants_write_access(self, client, app):
        """A valid SERVICE_API_KEY must be accepted by editor-or-admin endpoints."""
        with patch('app.auth.SERVICE_API_KEY', 'svc-write-test-key'):
            resp = client.post(
                '/api/recipes',
                json={
                    'title': 'Service Account Recipe',
                    'instructions': 'Step 1: done.',
                    'difficulty': 'easy',
                },
                headers={'X-API-Key': 'svc-write-test-key'},
            )
        assert resp.status_code == 201

    def test_service_key_cannot_reach_admin_required_endpoints(self, client, app):
        """@admin_required uses @jwt_required() and never calls _authenticate_api_key(),
        so the SERVICE_API_KEY is intentionally locked out of admin-only operations
        (e.g. DELETE).  This documents the design boundary: service keys have
        editor_or_admin scope via API-key path; admin-only routes require a JWT."""
        from app.models import Recipe
        with app.app_context():
            recipe = Recipe(
                title='Boundary Test Recipe',
                instructions='Checking decorator scope.',
                difficulty='easy',
            )
            db.session.add(recipe)
            db.session.commit()
            recipe_id = recipe.id

        with patch('app.auth.SERVICE_API_KEY', 'svc-delete-test-key'):
            resp = client.delete(
                f'/api/recipes/{recipe_id}',
                headers={'X-API-Key': 'svc-delete-test-key'},
            )
        # 401 — @admin_required requires a JWT; API keys cannot satisfy it
        assert resp.status_code == 401

    def test_wrong_service_key_rejected_by_endpoint(self, client, app):
        """An incorrect service key must not grant write access."""
        with patch('app.auth.SERVICE_API_KEY', 'correct-key'):
            resp = client.post(
                '/api/recipes',
                json={
                    'title': 'Sneaky Recipe',
                    'instructions': 'Should fail.',
                    'difficulty': 'easy',
                },
                headers={'X-API-Key': 'wrong-key'},
            )
        # No JWT, no matching API key → 401
        assert resp.status_code == 401

    def test_service_key_comparison_is_constant_time(self, app):
        """SERVICE_API_KEY check uses hmac.compare_digest — verify it is called
        (not a plain == comparison that leaks timing information)."""
        import hmac as hmac_mod
        with patch('app.auth.SERVICE_API_KEY', 'timing-test-key'):
            with patch.object(hmac_mod, 'compare_digest', wraps=hmac_mod.compare_digest) as spy:
                with app.test_request_context('/', headers={'X-API-Key': 'timing-test-key'}):
                    _authenticate_api_key()
        spy.assert_called()


# ===========================================================================
# download_image — SSRF via redirect chain
# ===========================================================================

class TestDownloadImageRedirectSSRF:
    """download_image follows redirects manually; every hop must be SSRF-validated."""

    @patch('app.image_utils.validate_url')
    @patch('app.image_utils.requests.Session')
    def test_redirect_to_private_ip_blocked(self, mock_session_cls, mock_validate_url, app):
        """A 302 redirect whose Location resolves to a private IP must abort the download."""
        from app.image_utils import download_image

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        redir = MagicMock()
        redir.status_code = 302
        redir.headers = {'Location': 'http://192.168.1.100/secret.jpg'}
        mock_session.get.return_value = redir

        # Initial URL passes validation; the redirect target does not.
        mock_validate_url.side_effect = [
            (True, None),
            (False, 'Private IP addresses are not allowed'),
        ]

        with app.app_context():
            rel, abs_path = download_image('https://example.com/image.jpg')

        assert rel is None
        assert abs_path is None

    @patch('app.image_utils.validate_url')
    @patch('app.image_utils.requests.Session')
    def test_redirect_to_internal_domain_blocked(self, mock_session_cls, mock_validate_url, app):
        """A 301 redirect to an .internal hostname must be blocked mid-chain."""
        from app.image_utils import download_image

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        redir = MagicMock()
        redir.status_code = 301
        redir.headers = {'Location': 'http://intranet.internal/data.jpg'}
        mock_session.get.return_value = redir

        mock_validate_url.side_effect = [
            (True, None),
            (False, 'Internal domain names are not allowed'),
        ]

        with app.app_context():
            rel, abs_path = download_image('https://example.com/photo.jpg')

        assert rel is None
        assert abs_path is None

    @patch('app.image_utils.validate_url')
    @patch('app.image_utils.requests.Session')
    def test_redirect_to_cloud_metadata_endpoint_blocked(
        self, mock_session_cls, mock_validate_url, app
    ):
        """Redirect to AWS/GCP metadata endpoint (169.254.169.254) is blocked."""
        from app.image_utils import download_image

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        redir = MagicMock()
        redir.status_code = 302
        redir.headers = {'Location': 'http://169.254.169.254/latest/meta-data/'}
        mock_session.get.return_value = redir

        mock_validate_url.side_effect = [
            (True, None),
            (False, 'Blocked hostname'),
        ]

        with app.app_context():
            rel, abs_path = download_image('https://example.com/img.jpg')

        assert rel is None
        assert abs_path is None

    @patch('app.image_utils.validate_url')
    @patch('app.image_utils.requests.Session')
    def test_each_redirect_hop_is_independently_validated(
        self, mock_session_cls, mock_validate_url, app
    ):
        """validate_url must be called once per redirect hop, not just for the first URL.
        This verifies the per-hop SSRF guard is in the loop, not only before it."""
        from app.image_utils import download_image

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        hop1 = MagicMock()
        hop1.status_code = 302
        hop1.headers = {'Location': 'https://cdn2.example.com/img.jpg'}

        hop2 = MagicMock()
        hop2.status_code = 302
        hop2.headers = {'Location': 'http://10.0.0.1/steal.jpg'}  # private IP

        mock_session.get.side_effect = [hop1, hop2]

        mock_validate_url.side_effect = [
            (True, None),   # initial URL
            (True, None),   # first hop
            (False, 'Private IP addresses are not allowed'),  # second hop — blocked
        ]

        with app.app_context():
            rel, abs_path = download_image('https://example.com/start.jpg')

        assert rel is None
        assert abs_path is None
        # Exactly 3 validate_url calls: initial + 2 hops
        assert mock_validate_url.call_count == 3
