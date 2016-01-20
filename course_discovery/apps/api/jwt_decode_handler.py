"""
Custom JWT decoding function for django_rest_framework jwt package.

Adds logging to facilitate debugging of InvalidTokenErrors.  Also
requires "exp" and "iat" claims to be present - the base package
doesn't expose settings to enforce this.
"""
import logging

import jwt
from rest_framework_jwt.settings import api_settings

logger = logging.getLogger(__name__)


def decode(token):
    """
    Ensure InvalidTokenErrors are logged for diagnostic purposes, before
    failing authentication.

    Args:
        token (str): JSON web token (JWT) to be decoded.
    """

    options = {
        'verify_exp': api_settings.JWT_VERIFY_EXPIRATION,
        'require_exp': True,
        'require_iat': True,
    }

    try:
        return jwt.decode(
            token,
            api_settings.JWT_SECRET_KEY,
            api_settings.JWT_VERIFY,
            options=options,
            leeway=api_settings.JWT_LEEWAY,
            audience=api_settings.JWT_AUDIENCE,
            issuer=api_settings.JWT_ISSUER,
            algorithms=[api_settings.JWT_ALGORITHM]
        )
    except jwt.InvalidTokenError:
        logger.exception('JWT decode failed!')
        raise
