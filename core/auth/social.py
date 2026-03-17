"""
Direct OAuth token verification for Google and Apple.
No dependency on allauth — verifies tokens directly against provider APIs.
"""

import logging

import jwt
import requests as http_requests
from django.conf import settings
from django.core.cache import cache
from rest_framework import serializers

logger = logging.getLogger(__name__)

_DP_AUTH = getattr(settings, "DP_AUTH", {})

# ── Google ──────────────────────────────────────────────────────────

# Google's public key certificates endpoint
_GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


def verify_google_token(id_token_str):
    """
    Verify a Google ID token and return (uid, email, name, picture).
    Raises serializers.ValidationError on failure.
    """
    client_id = _DP_AUTH.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise serializers.ValidationError("Google Sign-In is not configured on this server.")

    try:
        # Use google-auth library if available, otherwise fall back to PyJWT
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token as google_id_token
            idinfo = google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                client_id,
            )
        except ImportError:
            # Fallback: manual JWT verification with Google's JWKS
            idinfo = _verify_google_jwt_manual(id_token_str)

        # Validate issuer
        if idinfo.get("iss") not in _GOOGLE_ISSUERS:
            raise serializers.ValidationError("Invalid Google token issuer.")

        # Require verified email
        if not idinfo.get("email_verified", False):
            raise serializers.ValidationError("Google email is not verified.")

        uid = idinfo["sub"]
        email = idinfo["email"]
        name = idinfo.get("name", "")
        picture = idinfo.get("picture", "")

        return uid, email, name, picture

    except serializers.ValidationError:
        raise
    except Exception as e:
        logger.warning("Google token verification failed: %s", e)
        raise serializers.ValidationError("Invalid Google token.")


def _verify_google_jwt_manual(id_token_str):
    """Verify Google ID token using PyJWT + Google's JWKS endpoint."""
    jwks = _get_cached_jwks("google", _GOOGLE_CERTS_URL)
    header = jwt.get_unverified_header(id_token_str)
    kid = header.get("kid")

    key = _find_jwk(jwks, kid)
    if not key:
        # Key rotation — clear cache and retry once
        jwks = _get_cached_jwks("google", _GOOGLE_CERTS_URL, force_refresh=True)
        key = _find_jwk(jwks, kid)
        if not key:
            raise serializers.ValidationError("Google signing key not found.")

    client_id = _DP_AUTH.get("GOOGLE_CLIENT_ID", "")
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
    return jwt.decode(
        id_token_str,
        public_key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=list(_GOOGLE_ISSUERS),
    )


# ── Apple ───────────────────────────────────────────────────────────

_APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_ISSUER = "https://appleid.apple.com"


def verify_apple_token(id_token_str):
    """
    Verify an Apple ID token and return (uid, email).
    Raises serializers.ValidationError on failure.

    Apple may omit email from JWT claims on subsequent logins.
    Caller must handle the case where email is empty by looking up
    an existing SocialAccount.
    """
    client_id = _DP_AUTH.get("APPLE_CLIENT_ID", "")
    if not client_id:
        raise serializers.ValidationError("Apple Sign-In is not configured on this server.")

    try:
        jwks = _get_cached_jwks("apple", _APPLE_JWKS_URL)
        header = jwt.get_unverified_header(id_token_str)
        kid = header.get("kid")

        key = _find_jwk(jwks, kid)
        if not key:
            # Key rotation — clear cache and retry once
            jwks = _get_cached_jwks("apple", _APPLE_JWKS_URL, force_refresh=True)
            key = _find_jwk(jwks, kid)
            if not key:
                raise serializers.ValidationError("Apple signing key not found.")

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        claims = jwt.decode(
            id_token_str,
            public_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=_APPLE_ISSUER,
        )

        uid = claims["sub"]
        email = claims.get("email", "")

        return uid, email

    except serializers.ValidationError:
        raise
    except Exception as e:
        logger.warning("Apple token verification failed: %s", e)
        raise serializers.ValidationError("Invalid Apple token.")


# ── Shared JWKS helpers ─────────────────────────────────────────────


def _get_cached_jwks(provider, url, force_refresh=False):
    """Fetch and cache a provider's JWKS (JSON Web Key Set)."""
    cache_key = f"oauth_jwks:{provider}"

    if not force_refresh:
        cached = cache.get(cache_key)
        if cached:
            return cached

    try:
        resp = http_requests.get(url, timeout=5)
        resp.raise_for_status()
        jwks = resp.json()
        cache.set(cache_key, jwks, timeout=3600)  # 1 hour
        return jwks
    except http_requests.RequestException as e:
        logger.error("Failed to fetch JWKS from %s: %s", url, e)
        raise serializers.ValidationError(
            f"{provider.capitalize()} authentication unavailable."
        )


def _find_jwk(jwks, kid):
    """Find a JWK by key ID in a JWKS document."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None
