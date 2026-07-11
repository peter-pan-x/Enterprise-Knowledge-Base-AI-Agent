import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings
from app.schemas.auth import UserProfile

DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "app.db"


@dataclass(frozen=True)
class CurrentUser:
    id: str
    username: str
    role: str

    def profile(self) -> UserProfile:
        return UserProfile(id=self.id, username=self.username, role=self.role)


def initialize_auth_storage() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'admin')),
                created_at TEXT NOT NULL
            )
            """
        )
        if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None:
            _insert_user(connection, settings.initial_admin_username, settings.initial_admin_password, "admin")
            _insert_user(connection, settings.initial_user_username, settings.initial_user_password, "user")


def authenticate(username: str, password: str) -> CurrentUser | None:
    with _connection() as connection:
        row = connection.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None or not _verify_password(password, row["password_hash"]):
        return None
    return CurrentUser(id=row["id"], username=row["username"], role=row["role"])


def issue_token(user: CurrentUser) -> str:
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "exp": int((datetime.now(UTC) + timedelta(hours=settings.auth_token_hours)).timestamp()),
    }
    encoded = _base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_base64url(signature)}"


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录", headers={"WWW-Authenticate": "Bearer"})
    try:
        encoded, received_signature = authorization.removeprefix("Bearer ").split(".", 1)
        expected_signature = _base64url(
            hmac.new(settings.auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(received_signature, expected_signature):
            raise ValueError("invalid signature")
        payload = json.loads(_base64url_decode(encoded))
        if int(payload["exp"]) < int(datetime.now(UTC).timestamp()):
            raise ValueError("expired")
        return CurrentUser(id=str(payload["sub"]), username=str(payload["username"]), role=str(payload["role"]))
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效", headers={"WWW-Authenticate": "Bearer"})


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _insert_user(connection: sqlite3.Connection, username: str, password: str, role: str) -> None:
    connection.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (uuid4().hex, username, _hash_password(password), role, datetime.now(UTC).isoformat()),
    )


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"{_base64url(salt)}${_base64url(digest)}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        encoded_salt, encoded_digest = stored.split("$", 1)
        salt = _base64url_decode(encoded_salt)
        expected = _base64url_decode(encoded_digest)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return hmac.compare_digest(actual, expected)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
