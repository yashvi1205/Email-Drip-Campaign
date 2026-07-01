import hashlib
import hmac
import os
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PASSWORD_ITERATIONS = 600_000
API_KEY_PREFIX_BYTES = 8
API_KEY_SECRET_BYTES = 32


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str, int]:
    salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return password_hash.hex(), salt.hex(), PASSWORD_ITERATIONS


def _verify_password(
    password: str,
    expected_hash: str,
    salt_hex: str,
    iterations: int,
) -> bool:
    actual_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    ).hex()
    return hmac.compare_digest(actual_hash, expected_hash)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CreatedApiKey:
    id: str
    name: str
    key: str
    prefix: str
    created_at: str


@dataclass(frozen=True)
class ApiKeyRecord:
    id: str
    name: str
    prefix: str
    created_at: str
    last_used_at: str | None
    revoked_at: str | None


class AuthStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def initialize(self, admin_username: str, admin_password: str | None) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS admins (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    iterations INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    prefix TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    revoked_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash
                    ON api_keys (key_hash);
                CREATE INDEX IF NOT EXISTS idx_api_keys_revoked_at
                    ON api_keys (revoked_at);
                """
            )

            if admin_password is not None:
                row = connection.execute(
                    "SELECT username FROM admins WHERE username = ?",
                    (admin_username,),
                ).fetchone()

                password_hash, salt, iterations = _hash_password(admin_password)
                now = _utc_now()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO admins (
                            username, password_hash, salt, iterations,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (admin_username, password_hash, salt, iterations, now, now),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE admins
                        SET password_hash = ?, salt = ?, iterations = ?, updated_at = ?
                        WHERE username = ?
                        """,
                        (password_hash, salt, iterations, now, admin_username),
                    )

        os.chmod(self.db_path, 0o600)

    def has_admin(self) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT 1 FROM admins LIMIT 1").fetchone()
            return row is not None

    def authenticate_admin(self, username: str, password: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT password_hash, salt, iterations
                FROM admins
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

        if row is None:
            return False

        return _verify_password(
            password,
            row["password_hash"],
            row["salt"],
            row["iterations"],
        )

    def create_api_key(self, name: str) -> CreatedApiKey:
        key_id = str(uuid.uuid4())
        prefix = secrets.token_urlsafe(API_KEY_PREFIX_BYTES)
        secret = secrets.token_urlsafe(API_KEY_SECRET_BYTES)
        key = f"cdx_{prefix}_{secret}"
        created_at = _utc_now()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO api_keys (id, name, key_hash, prefix, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key_id, name, hash_api_key(key), prefix, created_at),
            )

        return CreatedApiKey(
            id=key_id,
            name=name,
            key=key,
            prefix=prefix,
            created_at=created_at,
        )

    def list_api_keys(self) -> list[ApiKeyRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, prefix, created_at, last_used_at, revoked_at
                FROM api_keys
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [self._record_from_row(row) for row in rows]

    def revoke_api_key(self, key_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE api_keys
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE id = ?
                """,
                (_utc_now(), key_id),
            )
            return cursor.rowcount > 0

    def authenticate_api_key(self, api_key: str | None) -> bool:
        if not api_key:
            return False

        key_hash = hash_api_key(api_key)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT key_hash
                FROM api_keys
                WHERE key_hash = ? AND revoked_at IS NULL
                """,
                (key_hash,),
            ).fetchone()

            if row is None:
                return False

            if not hmac.compare_digest(row["key_hash"], key_hash):
                return False

            connection.execute(
                """
                UPDATE api_keys
                SET last_used_at = ?
                WHERE key_hash = ?
                """,
                (_utc_now(), key_hash),
            )
            return True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> ApiKeyRecord:
        return ApiKeyRecord(
            id=row["id"],
            name=row["name"],
            prefix=row["prefix"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
            revoked_at=row["revoked_at"],
        )
