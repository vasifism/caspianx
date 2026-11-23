"""Structured errors from the simulation HTTP API."""

from __future__ import annotations

from dataclasses import dataclass


RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class TargetAPIError(Exception):
    """Represent a failed Target API request with its HTTP status."""

    status_code: int
    detail: str = "Target API request failed"

    @property
    def retryable(self) -> bool:
        """Report whether the status permits a retry with backoff."""
        return self.status_code in RETRYABLE_STATUS_CODES

    def __str__(self) -> str:
        """Format the HTTP error without including request credentials."""
        return f"Target API HTTP {self.status_code}: {self.detail}"


class SimulationScopeError(ValueError):
    """The requested operation is outside the permitted simulation boundary."""
