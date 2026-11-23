"""Transport for the authorized revel8 simulation conversation API."""

from __future__ import annotations

from typing import Any

import httpx


class Revel8ConversationTransport:
    """Make bounded HTTP calls only to the official simulation endpoint."""

    def __init__(self, api_key: str, base_url: str, *, timeout: float = 120.0) -> None:
        """Configure the client without sending network traffic."""
        from urllib.parse import urlsplit

        url = urlsplit(base_url)
        if (
            url.scheme != "https"
            or url.hostname != "target-api.apps.01.cf.eu01.stackit.cloud"
            or url.path.rstrip("/") != "/v1"
            or url.username is not None
            or url.password is not None
            or url.port is not None
            or url.query
            or url.fragment
        ):
            raise ValueError("Only the official revel8 simulation endpoint is permitted")
        if not api_key or timeout < 120:
            raise ValueError("A team key and minimum 120-second timeout are required")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            follow_redirects=False,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def __aenter__(self) -> Revel8ConversationTransport:
        """Enter the asynchronous transport context."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Close the HTTP connection pool."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        key: str | None = None,
    ) -> dict[str, Any]:
        """Send one request without automatic retries and decode JSON."""
        headers = {"Idempotency-Key": key} if key else None
        response = await self._client.request(method, path, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise TypeError("The API returned an unexpected non-object response")
        return data

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Read the current session state."""
        return await self._request("GET", f"sessions/{session_id}")

    async def start(
        self, session_id: str, target_id: str, channel: str, key: str
    ) -> dict[str, Any]:
        """Start one authorized simulation conversation."""
        return await self._request(
            "POST",
            f"sessions/{session_id}/conversations",
            payload={"to": target_id, "channel": channel},
            key=key,
        )

    async def turn(self, conversation_id: str, line: str, key: str) -> dict[str, Any]:
        """Send one utterance in an active simulation conversation."""
        return await self._request(
            "POST", f"conversations/{conversation_id}/turns", payload={"say": line}, key=key
        )

    async def end(self, conversation_id: str, key: str) -> dict[str, Any]:
        """Close the simulation conversation explicitly."""
        return await self._request("POST", f"conversations/{conversation_id}/end", key=key)
