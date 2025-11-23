"""JWT Decoder Filter for AWS Lambda Functions.

This module provides a decorator-based JWT token decoder that extracts JWT
tokens from Authorization headers and exposes the claims through
requestContext.authorizer to maintain compatibility with API Gateway TOKEN
authorizers.

The filter acts like a Java servlet filter but for Lambda functions, providing
a clean separation of concerns between authentication and business logic.
"""

import json
import logging
import functools
import os
import base64
from typing import Callable, Any, Dict, Optional

__all__ = ["token_decoder"]

log = logging.getLogger(__name__)


def _log_jwt_configuration():
    """Log current JWT configuration for debugging."""
    log.debug("=== JWT Configuration Debug ===")
    log.debug("JWKS_HOST: %s", os.getenv("JWKS_HOST", "NOT_SET"))
    log.debug("JWT_ISSUER: %s", os.getenv("JWT_ISSUER", "NOT_SET"))
    log.debug(
        "JWT_ALLOWED_AUDIENCES: %s", os.getenv("JWT_ALLOWED_AUDIENCES", "NOT_SET")
    )
    log.debug("ANONYMOUS_ROLE: %s", os.getenv("ANONYMOUS_ROLE", "NOT_SET"))
    log.debug("Logging level: %s", logging.getLogger().getEffectiveLevel())
    log.debug("===============================")


def token_decoder(
    jwks_url: Optional[str] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
    algorithms: Optional[list[str]] = None,
    anonymous_role: Optional[str] = None,
):
    """
    JWT token decoder decorator for AWS Lambda handlers.

    This filter extracts JWT tokens from the Authorization header, validates
    them, and passes the decoded token as a keyword argument to the handler
    function.

    Args:
        jwks_url: URL to fetch JWKS from (e.g., "https://oauth.local/.well-known/jwks.json")
        audience: Expected audience claim (or list of audiences)
        issuer: Expected issuer claim
        algorithms: List of allowed algorithms (defaults to ["RS256"])
        anonymous_role: Role to assign to anonymous (unauthenticated) requests.
                       If not set and no token is provided, request is rejected.
                       Set via environment variable ANONYMOUS_ROLE or parameter.

    Returns:
        Decorated handler function that processes JWT tokens before execution

    Example:
        # Secured endpoint - requires valid JWT token
        @token_decoder(
            jwks_url="https://your-oauth-server/.well-known/jwks.json",
            audience="test-api",
            issuer="https://oauth.local/",
            algorithms=["RS256"]
        )
        def secured_handler(event, context):
            # Claims available in event['requestContext']['authorizer']
            return {'statusCode': 200, 'body': 'Secured endpoint'}

        # Public endpoint - allows anonymous with 'public' role
        @token_decoder(anonymous_role="public")
        def public_handler(event, context):
            # Works without Authorization header, roles=["public"]
            return {'statusCode': 200, 'body': 'Public endpoint'}
    """

    # Validate configuration at decorator time
    config_anonymous_role = anonymous_role or os.getenv("ANONYMOUS_ROLE")

    # If no anonymous role is configured and no JWKS host, check if we're in test mode
    if not config_anonymous_role and not jwks_url and not os.getenv("JWKS_HOST"):
        # Allow decorator to be applied without config for testing
        # Actual validation will happen at runtime when handler is called
        pass

    def decorator(handler: Callable) -> Callable:
        @functools.wraps(handler)
        def wrapper(event: dict, context: Any) -> dict:
            log.debug("JWT token decoder starting for function: %s", handler.__name__)

            # Log configuration for debugging
            if log.isEnabledFor(logging.DEBUG):
                _log_jwt_configuration()

            log.debug("Event structure: %s", json.dumps(event, default=str))

            # Determine configuration source
            config_jwks_url = (
                jwks_url or f"{os.getenv('JWKS_HOST')}/.well-known/jwks.json"
                if os.getenv("JWKS_HOST")
                else None
            )
            config_issuer = issuer or os.getenv("JWT_ISSUER")
            config_audience = (
                audience or os.getenv("JWT_ALLOWED_AUDIENCES", "").split(",")
                if os.getenv("JWT_ALLOWED_AUDIENCES")
                else []
            )
            config_algorithms = algorithms or ["RS256"]
            config_anonymous_role = anonymous_role or os.getenv("ANONYMOUS_ROLE")
            log.debug("anonymous_role parameter: %s", anonymous_role)
            log.debug("ANONYMOUS_ROLE env: %s", os.getenv("ANONYMOUS_ROLE", ""))
            log.debug("config_anonymous_role: %s", config_anonymous_role)

            # Skip JWT decoding if no JWKS URL is configured
            if not config_jwks_url:
                log.debug("No JWKS URL configured, skipping JWT decoding")
                return handler(event, context)

            try:
                log.debug("Processing JWT token extraction and validation")

                # Check if authorizer already exists (preserve context)
                if event.get("requestContext", {}).get("authorizer"):
                    log.debug("Authorizer already exists, skipping JWT processing")
                    return handler(event, context)

                # Set up a singleton JWTDecoder instance
                if not hasattr(wrapper, "_jwt_decoder"):
                    log.debug("Creating new JWTDecoder instance")
                    log.debug(
                        "JWT config - URL: %s, issuer: %s, aud: %s, alg: %s",
                        config_jwks_url,
                        config_issuer,
                        config_audience,
                        config_algorithms,
                    )
                    wrapper._jwt_decoder = JWTDecoder(
                        jwks_url=config_jwks_url,
                        issuer=config_issuer,
                        allowed_audiences=set(config_audience)
                        if config_audience
                        else None,
                        algorithms=config_algorithms,
                        anonymous_role=config_anonymous_role,
                    )
                else:
                    log.debug("Using existing JWTDecoder instance")
                jwt_decoder = wrapper._jwt_decoder

                log.debug("Decoding JWT token")
                decoded_token = jwt_decoder.decode(event)

                log.debug(
                    "JWT token result: %s",
                    json.dumps(decoded_token, default=str) if decoded_token else "None",
                )
                # Populate requestContext for Lambda handler compatibility
                if "requestContext" not in event:
                    event["requestContext"] = {}
                if "authorizer" not in event["requestContext"]:
                    event["requestContext"]["authorizer"] = {}
                event["requestContext"]["authorizer"] = decoded_token

                return handler(event, context)

            except Exception as e:
                log.error("JWT filter critical error: %s", str(e))
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "Internal server error"}),
                }

        return wrapper

    return decorator


class JWTDecoder:
    def __init__(
        self,
        jwks_url: Optional[str] = None,
        issuer: Optional[str] = None,
        allowed_audiences: Optional[set] = None,
        algorithms: Optional[list] = None,
        anonymous_role: Optional[str] = None,
    ):
        log.debug(
            "Initializing JWTDecoder with jwks_url: %s, issuer: %s, anonymous_role: %s",
            jwks_url,
            issuer,
            anonymous_role,
        )
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.allowed_audiences = allowed_audiences or set()
        self.algorithms = algorithms or ["RS256"]
        self.anonymous_role = anonymous_role

        # Fetch public key only if JWKS URL is provided
        if jwks_url:
            self.public_key = self.fetch_public_key_from_jwks(jwks_url)
            if not self.public_key:
                raise ValueError(
                    f"Failed to fetch public key from JWKS URL: {jwks_url}"
                )
        else:
            self.public_key = None

        log.debug(
            "JWTDecoder initialized with %d allowed audiences, algorithms: %s",
            len(self.allowed_audiences),
            self.algorithms,
        )

    def fetch_public_key_from_jwks(
        self, jwks_url: str, kid: Optional[str] = None
    ) -> Optional[str]:
        """
        Fetch the public key from a JWKS endpoint.

        Args:
            jwks_url: The full JWKS endpoint URL
            kid: Optional key ID to select a specific key

        Returns:
            PEM-formatted public key string, or None if not found
        """
        import requests
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend

        try:
            log.debug("Fetching JWKS from URL: %s", jwks_url)
            resp = requests.get(jwks_url, timeout=5)
            resp.raise_for_status()
            log.debug("JWKS request successful, status: %d", resp.status_code)

            jwks = resp.json()
            keys = jwks.get("keys", [])
            log.debug("Found %d keys in JWKS response", len(keys))

            if not keys:
                log.warning("No keys found in JWKS response")
                return None

            # Select key by kid if provided, else use first key
            key = None
            if kid:
                log.debug("Looking for specific key ID: %s", kid)
                for k in keys:
                    if k.get("kid") == kid:
                        key = k
                        log.debug("Found matching key for kid: %s", kid)
                        break
                if not key:
                    log.warning("Key ID %s not found, using first key", kid)
            if not key:
                key = keys[0]
                log.debug(
                    "Using first available key with kid: %s", key.get("kid", "unknown")
                )
            # Convert JWK to PEM (requires cryptography)

            def b64url_decode(val):
                val += "=" * (-len(val) % 4)
                return base64.urlsafe_b64decode(val)

            n = int.from_bytes(b64url_decode(key["n"]), "big")
            e = int.from_bytes(b64url_decode(key["e"]), "big")
            pubkey = rsa.RSAPublicNumbers(e, n).public_key(default_backend())
            pem = pubkey.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            return pem.decode("utf-8")
        except Exception as e:
            log.error("Failed to fetch public key from JWKS: %s", e)
            return None

    def decode(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Decode the JWT token and return the claims, or anonymous claims if no token."""
        try:
            token = self.parse_token_from_event(event)
            if token:
                return self.decode_token(token)
            elif self.anonymous_role:
                log.debug(
                    "No token found, using anonymous role: %s", self.anonymous_role
                )
                return {"roles": [self.anonymous_role]}
            else:
                log.error("No token found and no anonymous role configured")
                raise ValueError(
                    "Authentication required: no token provided and no anonymous access configured"
                )
        except ValueError as e:
            if self.anonymous_role and "No authorization header" in str(e):
                log.debug("Token parsing failed, using anonymous role: %s", str(e))
                return {"roles": [self.anonymous_role]}
            else:
                raise

    def parse_token_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract the Bearer token from the authorization header."""
        log.debug("Parsing JWT token from event")

        auth_header = (
            event.get("authorizationToken")
            or event.get("headers", {}).get("Authorization")
            or event.get("headers", {}).get("authorization")
        )

        log.debug("Authorization header found: %s", "Yes" if auth_header else "No")

        if not auth_header:
            log.debug("No authorization header found")
            raise ValueError("No authorization header found")

        auth_token_parts = auth_header.split(" ")
        log.debug("Authorization header parts: %d", len(auth_token_parts))

        if (
            len(auth_token_parts) != 2
            or auth_token_parts[0].lower() != "bearer"
            or not auth_token_parts[1]
        ):
            log.error("Invalid authorization header format")
            raise ValueError("Invalid AuthorizationToken.")

        token = auth_token_parts[1]
        log.debug("JWT token extracted successfully, length: %d", len(token))
        return token

    def decode_token(self, token: str) -> Dict[str, Any]:
        """Validate and decode the JWT using the PEM public key."""
        log.debug("Starting JWT token validation and decoding")

        if not self.public_key:
            raise ValueError("No public key available for token validation")

        import jwt
        from jwt import (
            InvalidTokenError,
            ExpiredSignatureError,
            InvalidAudienceError,  # type: ignore
        )

        try:
            # First decode without audience enforcement; we'll validate
            # audience against the configured allowed set derived from
            # config.yaml. This supports multi-audience tokens.
            log.debug("Configuring JWT decode options")
            decode_options = {"verify_aud": False}
            decode_args = {
                "algorithms": self.algorithms,
                "options": decode_options,
                "key": self.public_key,
                "token": token,
            }

            if self.issuer:
                log.debug("Using issuer validation: %s", self.issuer)
                decode_args["issuer"] = self.issuer
            else:
                log.debug("Skipping issuer validation")
                decode_options["verify_iss"] = False

            if self.allowed_audiences:
                log.debug("Allowed audiences configured: %s", self.allowed_audiences)
                # We'll validate audience manually after decoding
                decode_options["verify_aud"] = False
            else:
                log.debug("No audience validation configured")
                decode_options["verify_aud"] = False

            log.debug("Decoding JWT token with PyJWT")
            # Extract token from decode_args as it needs to be the first positional argument
            token_arg = decode_args.pop("token")
            decoded_token = jwt.decode(token_arg, **decode_args)
            log.debug("JWT token decoded successfully")

            token_aud = decoded_token.get("aud")
            log.debug("Token audience claim: %s", token_aud)

            # Normalize token audience to a list for comparison
            token_auds = (
                [token_aud] if isinstance(token_aud, str) else list(token_aud or [])
            )
            token_auds = [str(a).strip() for a in token_auds if str(a).strip()]
            log.debug("Normalized token audiences: %s", token_auds)

            # Validate audience: token must contain at least one allowed aud
            if self.allowed_audiences:
                if not any(a in self.allowed_audiences for a in token_auds):
                    log.error(
                        "Audience validation failed. Required: %s, Found: %s",
                        self.allowed_audiences,
                        token_auds,
                    )
                    raise InvalidAudienceError("Audience not allowed")

            log.debug("All JWT validations passed successfully")
            log.debug("Decoded token claims: %s", list(decoded_token.keys()))
            return decoded_token

        except ExpiredSignatureError:
            log.error("Token has expired")
            raise
        except InvalidTokenError as e:
            log.error("Token validation failed: %s", e)
            raise
