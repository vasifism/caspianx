"""Provide a send-capable asynchronous client for the revel8 sandbox API.

Unlike the read-only ``integrations.target_api`` client, this client performs the
POST operations an attack needs: sessions, messages, landing pages, conversations,
and assets. It adds idempotency keys, rate-limit pacing, and retries on transient
failures. All requests target the sandbox base URL only.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import httpx

_RETRY = {429, 502, 503, 504}


class APIError(RuntimeError):
    """Represent a non-success response from the sandbox API."""

    def __init__(self, status: int, body: Any) -> None:
        """Store the status code and response body.

        Args:
            status: HTTP status code, or ``0`` for a transport error.
            body: Decoded body or error text.

        """
        self.status = status
        self.body = body
        super().__init__(f"API {status}: {body}")


class AttackClient:
    """Send and read simulation traffic with pacing and retries."""

    def __init__(self, base_url: str, team_key: str, timeout: float = 120.0) -> None:
        """Create the client bound to a base URL and team key.

        Args:
            base_url: API base URL, including the ``/v1`` path segment.
            team_key: The team's bearer token.
            timeout: Per-request timeout in seconds.

        """
        # Trailing slash + relative paths so base_url's /v1 is preserved by httpx.
        self.base_url = base_url.rstrip("/") + "/"
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {team_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        self._last_request = 0.0
        self._min_interval = 1.05

    async def _pace(self) -> None:
        """Sleep as needed to keep requests under the per-minute limit."""
        wait = self._min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            await asyncio.sleep(wait)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        headers: dict | None = None,
        max_retries: int = 4,
    ) -> Any:
        """Perform a paced, retrying request and return the decoded body.

        Args:
            method: HTTP method.
            path: API-relative path (leading slashes are stripped).
            json: Optional JSON request body.
            headers: Optional extra headers.
            max_retries: Maximum retries on transient failures.

        Returns:
            The decoded JSON body, or an empty dict for an empty response.

        Raises:
            APIError: On a non-success status or exhausted transport retries.

        """
        path = path.lstrip("/")  # relative to base_url (which ends in /v1/)
        attempt = 0
        while True:
            await self._pace()
            self._last_request = time.monotonic()
            try:
                response = await self._http.request(method, path, json=json, headers=headers)
            except httpx.TransportError as error:
                if attempt >= max_retries:
                    raise APIError(0, f"transport error: {error}")
                await asyncio.sleep(min(2**attempt, 8))
                attempt += 1
                continue

            if response.status_code < 300:
                return response.json() if response.content else {}

            try:
                body: Any = response.json()
            except ValueError:
                body = response.text

            if response.status_code in _RETRY and attempt < max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else min(2**attempt, 8)
                await asyncio.sleep(delay)
                attempt += 1
                continue

            raise APIError(response.status_code, body)

    @staticmethod
    def _idem() -> dict[str, str]:
        """Return a fresh idempotency-key header.

        Returns:
            A header mapping with a unique ``Idempotency-Key``.

        """
        return {"Idempotency-Key": uuid.uuid4().hex}

    async def list_scenarios(self) -> Any:
        """Return the list of scenarios."""
        return await self._request("GET", "/scenarios")

    async def list_channels(self) -> Any:
        """Return the list of available channels."""
        return await self._request("GET", "/channels")

    async def start_session(self, scenario_id: str) -> dict:
        """Start a session in a scenario.

        Args:
            scenario_id: The scenario to open a session in.

        Returns:
            The created session record.

        """
        return await self._request("POST", "/sessions", json={"scenario_id": scenario_id})

    async def get_session(self, sid: str) -> dict:
        """Return one session's current state.

        Args:
            sid: The session id.

        Returns:
            The session record.

        """
        return await self._request("GET", f"/sessions/{sid}")

    async def get_events(self, sid: str) -> list[dict]:
        """Return all events recorded for a session.

        Args:
            sid: The session id.

        Returns:
            The list of event records.

        """
        return (await self._request("GET", f"/sessions/{sid}/events")).get("events", [])

    async def end_session(self, sid: str) -> Any:
        """End a session.

        Args:
            sid: The session id.

        Returns:
            The server acknowledgement.

        """
        return await self._request("POST", f"/sessions/{sid}/end")

    async def send_message(
        self,
        sid: str,
        *,
        to: str,
        channel: str,
        body: str,
        from_: dict | None = None,
        subject: str | None = None,
        attachments: list | None = None,
        sent_at: str | None = None,
    ) -> dict:
        """Send one message and return the reaction.

        Args:
            sid: The session id.
            to: Target id.
            channel: Message channel.
            body: Message body (text or HTML).
            from_: Optional sender name/address claim.
            subject: Optional subject line.
            attachments: Optional asset ids or declared attachments.
            sent_at: Optional story-time timestamp.

        Returns:
            The response, including ``events``.

        """
        payload: dict[str, Any] = {"to": to, "channel": channel, "body": body}
        if from_:
            payload["from"] = from_
        if subject is not None:
            payload["subject"] = subject
        if attachments:
            payload["attachments"] = attachments
        if sent_at:
            payload["sent_at"] = sent_at
        return await self._request(
            "POST", f"/sessions/{sid}/messages", json=payload, headers=self._idem()
        )

    async def register_page(
        self,
        sid: str,
        *,
        url: str,
        title: str,
        fields: list[str] | None = None,
        html: str | None = None,
        text: str | None = None,
        images: list[str] | None = None,
    ) -> dict:
        """Register a landing page for the session.

        Args:
            sid: The session id.
            url: The lookalike URL the page is served at.
            title: The page title.
            fields: Field names the page asks for.
            html: Optional self-contained HTML.
            text: Optional plain text when no HTML is given.
            images: Optional asset ids used on the page.

        Returns:
            The created page record.

        """
        payload: dict[str, Any] = {"url": url, "title": title}
        if fields:
            payload["fields"] = fields
        if html:
            payload["html"] = html
        if text:
            payload["text"] = text
        if images:
            payload["images"] = images
        return await self._request("POST", f"/sessions/{sid}/pages", json=payload)

    async def start_conversation(
        self,
        sid: str,
        *,
        to: str,
        channel: str,
        from_: dict | None = None,
        sent_at: str | None = None,
    ) -> dict:
        """Start a live conversation.

        Args:
            sid: The session id.
            to: Target id.
            channel: A live channel.
            from_: Optional sender claim.
            sent_at: Optional story-time timestamp.

        Returns:
            The conversation record, including the first persona line.

        """
        payload: dict[str, Any] = {"to": to, "channel": channel}
        if from_:
            payload["from"] = from_
        if sent_at:
            payload["sent_at"] = sent_at
        return await self._request(
            "POST", f"/sessions/{sid}/conversations", json=payload, headers=self._idem()
        )

    async def send_turn(
        self, cid: str, say: str, attachments: list | None = None, sent_at: str | None = None
    ) -> dict:
        """Send one line in a conversation.

        Args:
            cid: The conversation id.
            say: What the agent says.
            attachments: Optional attachments shown during the turn.
            sent_at: Optional story-time timestamp.

        Returns:
            The response, including the persona's reply and any events.

        """
        payload: dict[str, Any] = {"say": say}
        if attachments:
            payload["attachments"] = attachments
        if sent_at:
            payload["sent_at"] = sent_at
        return await self._request(
            "POST", f"/conversations/{cid}/turns", json=payload, headers=self._idem()
        )

    async def end_conversation(self, cid: str) -> Any:
        """End a conversation.

        Args:
            cid: The conversation id.

        Returns:
            The server acknowledgement.

        """
        return await self._request("POST", f"/conversations/{cid}/end")

    async def upload_asset(self, path: str) -> dict:
        """Upload an image or PDF asset.

        Args:
            path: Local filesystem path to the asset.

        Returns:
            The created asset record.

        Raises:
            APIError: On a non-success status.

        """
        with open(path, "rb") as handle:
            files = {"file": (path.split("/")[-1], handle)}
            response = await self._http.post("assets", files=files, headers={"Content-Type": ""})
        if response.status_code >= 300:
            raise APIError(response.status_code, response.text)
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._http.aclose()
