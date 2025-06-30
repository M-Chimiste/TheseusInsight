from __future__ import annotations

from typing import Dict, Any, List
import json
import os
import base64
import hashlib

from ..db import get_cursor


class SettingsRepository:
    """Key-value settings storage."""

    @staticmethod
    def get(key: str) -> str | None:
        with get_cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
            row = cur.fetchone()
            return row["value"] if row else None

    @staticmethod
    def set(key: str, value: str) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO settings (key, value) VALUES (%s,%s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value),
            )

    @staticmethod
    def delete(key: str) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM settings WHERE key = %s", (key,))

    @staticmethod
    def all() -> Dict[str, str]:
        with get_cursor() as cur:
            cur.execute("SELECT key, value FROM settings")
            rows = cur.fetchall()
            return {row["key"]: row["value"] for row in rows}

    # Encryption helpers (mirroring PaperDatabase functionality)
    @staticmethod
    def _encrypt(plaintext: str) -> str:
        """Encrypt a string using XOR encryption with APP_SECRET_KEY."""
        secret = os.getenv("APP_SECRET_KEY", "default_secret").encode()
        key = hashlib.sha256(secret).digest()
        data = plaintext.encode()
        enc = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        return base64.b64encode(enc).decode()

    @staticmethod
    def _decrypt(ciphertext: str) -> str:
        """Decrypt a string encrypted with _encrypt method."""
        secret = os.getenv("APP_SECRET_KEY", "default_secret").encode()
        key = hashlib.sha256(secret).digest()
        data = base64.b64decode(ciphertext.encode())
        dec = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        return dec.decode()

    @staticmethod
    def set_secret_setting(key: str, value: str) -> None:
        """Encrypt and store a sensitive setting value."""
        SettingsRepository.set(key, SettingsRepository._encrypt(value))

    @staticmethod
    def get_secret_setting(key: str) -> str | None:
        """Retrieve and decrypt a sensitive setting value."""
        enc = SettingsRepository.get(key)
        if enc:
            try:
                return SettingsRepository._decrypt(enc)
            except Exception:
                return None
        return None

    # Convenience helpers mirroring old API

    @staticmethod
    def get_email_recipients() -> List[str]:
        val = SettingsRepository.get('email_recipients')
        return json.loads(val) if val else []

    @staticmethod
    def set_email_recipients(recipients: List[str]):
        SettingsRepository.set('email_recipients', json.dumps(recipients))

    @staticmethod
    def get_visualizer_settings() -> Dict[str, Any]:
        val = SettingsRepository.get('visualizer_settings')
        return json.loads(val) if val else {}

    @staticmethod
    def set_visualizer_settings(settings: Dict[str, Any]):
        SettingsRepository.set('visualizer_settings', json.dumps(settings)) 