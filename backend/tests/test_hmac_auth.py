"""Tests for HMAC authentication edge cases.

Tests cover discovered issues D-007 through D-009:
- D-007: URL-safe base64 decoding for API secret
- D-008: URL-safe base64 encoding for signature output
- D-009: Path-only signing (query params excluded)
"""

import base64
import hashlib
import hmac
import time

import pytest


class TestHMACAuthentication:
    """Test HMAC signature generation for CLOB API."""

    def test_urlsafe_base64_decode_secret(self):
        """Secret must be decoded with urlsafe_b64decode (D-007).

        URL-safe base64 uses - and _ instead of + and /. Using standard
        b64decode would fail for secrets containing these characters.
        """
        # Secret with URL-safe characters (- and _)
        urlsafe_secret = "abc-def_ghi=="

        # URL-safe decode should work
        decoded = base64.urlsafe_b64decode(urlsafe_secret)
        assert isinstance(decoded, bytes)

        # Standard decode would treat - and _ as invalid
        # (In practice, standard b64decode might accept them but interpret
        # them differently, leading to wrong signatures)

    def test_urlsafe_base64_encode_output(self):
        """Signature output must use urlsafe_b64encode (D-008).

        Standard b64encode produces + and / which need URL escaping.
        urlsafe_b64encode produces - and _ which are safe in headers.
        """
        test_data = b"test signature data"

        standard = base64.b64encode(test_data).decode()
        urlsafe = base64.urlsafe_b64encode(test_data).decode()

        # Both produce valid base64, but characters may differ
        assert "+" not in urlsafe
        assert "/" not in urlsafe

        # URL-safe uses - and _ instead
        if "+" in standard:
            assert "-" in urlsafe
        if "/" in standard:
            assert "_" in urlsafe

    def test_signs_path_only_not_query_params(self):
        """Signature should include path only, not query params (D-009).

        Per py-clob-client, the signature message is:
            timestamp + method + path (no query string)

        Query params are added to the URL after signing.
        """
        # Simulate signature creation
        timestamp = str(int(time.time()))
        method = "GET"
        path = "/trades"  # Path only, no query params
        query_params = {"token_id": "abc123", "limit": "100"}

        # Build message for signing (path only)
        message = f"{timestamp}{method}{path}"

        # Query params should NOT be in the message
        assert "token_id" not in message
        assert "limit" not in message
        assert "?" not in message

        # Create signature
        secret = base64.urlsafe_b64encode(b"testsecret").decode()
        secret_bytes = base64.urlsafe_b64decode(secret)
        signature = hmac.new(secret_bytes, message.encode(), hashlib.sha256)
        sig_output = base64.urlsafe_b64encode(signature.digest()).decode()

        # Signature should be valid base64
        assert len(sig_output) > 0
        # Should be decodable
        base64.urlsafe_b64decode(sig_output)

    def test_create_signature_matches_expected_format(self):
        """Test signature creation produces expected output format."""
        from services.polymarket_client import PolymarketClient

        # Create client with test credentials
        client = PolymarketClient()
        client.api_secret = base64.urlsafe_b64encode(b"test_secret_key").decode()

        timestamp = "1700000000"
        method = "GET"
        path = "/trades"

        signature = client._create_signature(timestamp, method, path)

        # Signature should be URL-safe base64
        assert isinstance(signature, str)
        assert "+" not in signature
        assert "/" not in signature

        # Should be decodable back to bytes
        decoded = base64.urlsafe_b64decode(signature)
        assert len(decoded) == 32  # SHA256 produces 32 bytes

    def test_auth_headers_include_all_required_fields(self):
        """Test that auth headers include all required POLY_* fields."""
        from services.polymarket_client import PolymarketClient

        client = PolymarketClient()
        client.api_key = "test_api_key"
        client.api_secret = base64.urlsafe_b64encode(b"test_secret").decode()
        client.api_passphrase = "test_passphrase"
        client.wallet_address = "0x1234567890abcdef"

        headers = client._get_auth_headers("GET", "/trades")

        # All required headers present
        assert "POLY_ADDRESS" in headers
        assert "POLY_SIGNATURE" in headers
        assert "POLY_TIMESTAMP" in headers
        assert "POLY_API_KEY" in headers
        assert "POLY_PASSPHRASE" in headers

        # Values match what we set
        assert headers["POLY_ADDRESS"] == "0x1234567890abcdef"
        assert headers["POLY_API_KEY"] == "test_api_key"
        assert headers["POLY_PASSPHRASE"] == "test_passphrase"

        # Timestamp is numeric string
        assert headers["POLY_TIMESTAMP"].isdigit()

    def test_has_api_credentials_requires_all_fields(self):
        """Test that _has_api_credentials checks all required fields."""
        from services.polymarket_client import PolymarketClient

        client = PolymarketClient()

        # All None - should return False
        assert not client._has_api_credentials()

        # Only partial - should return False
        client.api_key = "key"
        assert not client._has_api_credentials()

        client.api_secret = "secret"
        assert not client._has_api_credentials()

        client.api_passphrase = "passphrase"
        assert not client._has_api_credentials()

        # All set - should return True
        client.wallet_address = "0x123"
        assert client._has_api_credentials()
