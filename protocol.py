"""Shared config for the caura-memclaw dashboard surfaces."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MemclawConfig:
    """Everything a caller needs to reach the shared caura-memclaw tenant."""

    api_url: str
    api_key: str
    tenant_id: str
    fleet_id: str

    @property
    def mcp_url(self) -> str:
        return f"{self.api_url.rstrip('/')}/mcp/"

    @property
    def headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "X-Tenant-ID": self.tenant_id}

    @classmethod
    def from_env(cls) -> "MemclawConfig":
        return cls(
            api_url=os.environ.get("MEMCLAW_API_URL", "https://memclaw.net"),
            api_key=os.environ.get("MEMCLAW_API_KEY", ""),
            tenant_id=os.environ.get("MEMCLAW_TENANT_ID", ""),
            fleet_id=os.environ.get("MEMCLAW_FLEET_ID", "chorus"),
        )

    def require(self) -> None:
        missing = [
            name
            for name, val in (
                ("MEMCLAW_API_KEY", self.api_key),
                ("MEMCLAW_TENANT_ID", self.tenant_id),
            )
            if not val
        ]
        if missing:
            raise RuntimeError(
                f"caura-memclaw config missing: {', '.join(missing)}. "
                "Set them in .env or the shell."
            )
