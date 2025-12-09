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
    log.debug(
        "TOKEN_VALIDATOR_LAMBDA_ARN: %s",
        os.getenv("TOKEN_VALIDATOR_LAMBDA_ARN", "NOT_SET"),
    )
    log.debug("Logging level: %s", logging.getLogger().getEffectiveLevel())
    log.debug("===============================")


class LambdaTokenValidator:
    """Validates tokens by invoking an AWS Lambda TOKEN authorizer."""

    def __init__(self, lambda_arn: str):
        """
        Initialize Lambda token validator.

        Args:
            lambda_arn: ARN or name of the Lambda authorizer function
        """
        self.lambda_arn = lambda_arn
        try:
            import boto3

            self.lambda_client = boto3.client("lambda")
            log.debug("Lambda client initialized for validator: %s", lambda_arn)
        except ImportError:
            log.error("boto3 not available for Lambda token validation")
            raise ImportError("boto3 is required for Lambda token validation")

    def validate(
        self, token: str, method_arn: str = "arn:aws:execute-api:*:*:*"
    ) -> Dict[str, Any]:
        """
        Invoke AWS Lambda TOKEN authorizer.

        Args:
            token: JWT token (without "Bearer " prefix)
            method_arn: Method ARN for resource-based policies

        Returns:
            Claims dict (extracted from context field)

        Raises:
            ValueError: If validation fails
        """
        log.debug("Invoking Lambda authorizer: %s", self.lambda_arn)

        payload = {
            "type": "TOKEN",
            "authorizationToken": f"Bearer {token}",
            "methodArn": method_arn,
        }

        try:
            response = self.lambda_client.invoke(
                FunctionName=self.lambda_arn,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )

            result = json.loads(response["Payload"].read())
            log.debug("Lambda authorizer response received")

            # Check for Lambda errors
            if "FunctionError" in response:
                error_msg = result.get("errorMessage", "Unknown error")
                log.error("Lambda authorizer error: %s", error_msg)
                raise ValueError(f"Token validation failed: {error_msg}")

            # Extract context (claims) from authorizer response
            # AWS API Gateway places the 'context' object into
            # requestContext.authorizer
            context = result.get("context", {})
            if not context:
                log.warning("Authorizer returned no context/claims")
                raise ValueError("Authorizer returned no context/claims")

            log.debug("Token validated successfully, claims extracted from context")
            return context

        except Exception as e:
            log.error("Lambda authorizer invocation failed: %s", e)
            raise ValueError(f"Token validation failed: {str(e)}")


def token_decoder(
    jwks_url: Optional[str] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
    algorithms: Optional[list[str]] = None,
    anonymous_role: Optional[str] = None,
    lambda_validator_arn: Optional[str] = None,
):
    """
    JWT token decoder decorator for AWS Lambda handlers.

    This filter extracts JWT tokens from the Authorization header, validates
    them using JWKS, Lambda authorizer, or falls back to anonymous access.

    Validation priority:
    1. Check if requestContext.authorizer exists (gateway validated)
    2. Try Lambda validation if TOKEN_VALIDATOR_LAMBDA_ARN is set
    3. Try JWKS validation if JWKS_HOST is set
    4. Fall back to anonymous role if ANONYMOUS_ROLE is set
    5. Reject with error

    Args:
        jwks_url: URL to fetch JWKS from
        audience: Expected audience claim (or list of audiences)
        issuer: Expected issuer claim
        algorithms: List of allowed algorithms (defaults to ["RS256"])
        anonymous_role: Role to assign to anonymous requests.
                       Set via ANONYMOUS_ROLE environment variable.
        lambda_validator_arn: ARN of Lambda TOKEN authorizer function.
                             Set via TOKEN_VALIDATOR_LAMBDA_ARN env var.

    Returns:
        Decorated handler function that processes JWT tokens

    Example:
        # JWKS validation
        @token_decoder(
            jwks_url="https://oauth.local/.well-known/jwks.json",
            audience="test-api",
            issuer="https://oauth.local/",
        )
        def handler(event, context):
            return {'statusCode': 200, 'body': 'Secured'}

        # Lambda authorizer validation
        @token_decoder()  # Uses TOKEN_VALIDATOR_LAMBDA_ARN env var
        def handler(event, context):
            return {'statusCode': 200, 'body': 'Secured'}

        # Public endpoint
        @token_decoder(anonymous_role="public")
        def handler(event, context):
            return {'statusCode': 200, 'body': 'Public'}
    """

    # Validate configuration at decorator time
    config_anonymous_role = anonymous_role or os.getenv("ANONYMOUS_ROLE")
    config_lambda_arn = lambda_validator_arn or os.getenv("TOKEN_VALIDATOR_LAMBDA_ARN")

    # If no config provided, allow for runtime configuration
    if (
        not config_anonymous_role
        and not jwks_url
        and not os.getenv("JWKS_HOST")
        and not config_lambda_arn
    ):
        pass

    def decorator(handler: Callable) -> Callable:
        @functools.wraps(handler)
        def wrapper(event: dict, context: Any) -> dict:
            log.debug(
                "JWT token decoder starting for function: %s",
                handler.__name__,
            )

            # Log configuration for debugging
            if log.isEnabledFor(logging.DEBUG):
                _log_jwt_configuration()

            log.debug("Event structure: %s", json.dumps(event, default=str))

            # Check if authorizer already exists (gateway validated)
            if event.get("requestContext", {}).get("authorizer"):
                log.debug("Authorizer already exists, skipping JWT processing")
                return handler(event, context)

            # Determine configuration sources
            config_lambda_arn = lambda_validator_arn or os.getenv(
                "TOKEN_VALIDATOR_LAMBDA_ARN"
            )
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
            log.debug("config_lambda_arn: %s", config_lambda_arn)

            # Skip all validation if no method configured
            if not config_lambda_arn and not config_jwks_url:
                log.debug("No validation method configured")
                if config_anonymous_role:
                    log.debug("Using anonymous role: %s", config_anonymous_role)
                    if "requestContext" not in event:
                        event["requestContext"] = {}
                    event["requestContext"]["authorizer"] = {
                        "roles": [config_anonymous_role]
                    }
                return handler(event, context)

            try:
                log.debug("Processing JWT token extraction and validation")

                # Set up validation instances
                if not hasattr(wrapper, "_jwt_decoder"):
                    log.debug("Creating validator instances")

                    # Lambda validator takes priority
                    if config_lambda_arn:
                        log.debug(
                            "Configuring Lambda validator: %s",
                            config_lambda_arn,
                        )
                        wrapper._lambda_validator = LambdaTokenValidator(
                            config_lambda_arn
                        )
                    else:
                        wrapper._lambda_validator = None

                    # JWKS validator as fallback
                    if config_jwks_url:
                        log.debug(
                            "Configuring JWKS validator: %s",
                            config_jwks_url,
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
                        wrapper._jwt_decoder = None

                    wrapper._anonymous_role = config_anonymous_role

                log.debug("Parsing token from event")
                token = None
                try:
                    # Extract token
                    auth_header = (
                        event.get("authorizationToken")
                        or event.get("headers", {}).get("Authorization")
                        or event.get("headers", {}).get("authorization")
                    )

                    if auth_header:
                        auth_parts = auth_header.split(" ")
                        if len(auth_parts) == 2 and auth_parts[0].lower() == "bearer":
                            token = auth_parts[1]
                            log.debug("Token extracted, length: %d", len(token))
                except Exception:
                    log.debug("Token extraction failed")

                decoded_token = None

                # Try Lambda validator first
                if token and wrapper._lambda_validator:
                    try:
                        log.debug("Attempting Lambda validation")
                        decoded_token = wrapper._lambda_validator.validate(token)
                        log.debug("Lambda validation successful")
                    except Exception as e:
                        log.warning("Lambda validation failed: %s", e)
                        # Fall through to JWKS

                # Try JWKS validator if Lambda failed or unavailable
                if token and not decoded_token and wrapper._jwt_decoder:
                    try:
                        log.debug("Attempting JWKS validation")
                        decoded_token = wrapper._jwt_decoder.decode_token(token)
                        log.debug("JWKS validation successful")
                    except Exception as e:
                        log.warning("JWKS validation failed: %s", e)

                # Fall back to anonymous if configured
                if not decoded_token:
                    if wrapper._anonymous_role:
                        log.debug(
                            "Using anonymous role: %s",
                            wrapper._anonymous_role,
                        )
                        decoded_token = {"roles": [wrapper._anonymous_role]}
                    else:
                        log.error("No valid token and no anonymous access")
                        return {
                            "statusCode": 401,
                            "headers": {"Content-Type": "application/json"},
                            "body": json.dumps({"error": "Unauthorized"}),
                        }

                log.debug(
                    "JWT token result: %s",
                    json.dumps(decoded_token, default=str) if decoded_token else "None",
                )

                # Populate requestContext
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
