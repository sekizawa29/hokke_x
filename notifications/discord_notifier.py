#!/usr/bin/env python3
"""
Shared Discord webhook notifier.
Use this module from any feature that needs Discord notifications.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DiscordNotifyResult:
    ok: bool
    status_code: int
    error: str = ""


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.strip()
        if not self.webhook_url:
            raise ValueError("webhook_url is empty")

    @classmethod
    def from_env(cls, env_name: str = "DISCORD_WEBHOOK_URL") -> "DiscordNotifier":
        value = os.getenv(env_name, "").strip()
        if not value:
            raise ValueError(f"{env_name} が未設定")
        return cls(value)

    def _send_payload(self, payload: dict[str, Any]) -> DiscordNotifyResult:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                # Some edges behind Cloudflare may reject Python's default UA.
                "User-Agent": "hokke-x-notifier/1.0 (+discord-webhook)",
                "Accept": "*/*",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = int(getattr(resp, "status", 0) or 0)
                if status in (200, 204):
                    return DiscordNotifyResult(ok=True, status_code=status)
                return DiscordNotifyResult(ok=False, status_code=status, error=f"unexpected status: {status}")
        except Exception as e:
            return DiscordNotifyResult(ok=False, status_code=0, error=str(e))

    def send(
        self,
        content: str,
        *,
        username: Optional[str] = None,
    ) -> DiscordNotifyResult:
        payload: dict[str, Any] = {"content": content[:1900]}
        if username:
            payload["username"] = username
        return self._send_payload(payload)

    def send_embed(
        self,
        *,
        title: str,
        description: str = "",
        color: int = 0x5865F2,
        fields: Optional[list[dict[str, Any]]] = None,
        username: Optional[str] = None,
    ) -> DiscordNotifyResult:
        embed: dict[str, Any] = {
            "title": title[:256],
            "description": description[:4096],
            "color": int(color),
        }
        if fields:
            embed["fields"] = fields[:25]

        payload: dict[str, Any] = {"embeds": [embed]}
        if username:
            payload["username"] = username
        return self._send_payload(payload)
