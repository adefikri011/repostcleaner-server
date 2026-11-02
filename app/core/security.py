import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type

from app.core.config import get_settings

password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    secret = get_settings().session_secret.get_secret_value().encode("utf-8")
    return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()


def create_csrf_token(session_token: str) -> str:
    secret = get_settings().session_secret.get_secret_value().encode("utf-8")
    message = b"csrf:" + session_token.encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_csrf_token(session_token: str, csrf_token: str) -> bool:
    return hmac.compare_digest(create_csrf_token(session_token), csrf_token)


def hash_login_fingerprint(email: str, client_host: str) -> str:
    secret = get_settings().session_secret.get_secret_value().encode("utf-8")
    fingerprint = f"{email}\x00{client_host}".encode("utf-8")
    return hmac.new(secret, fingerprint, hashlib.sha256).hexdigest()
