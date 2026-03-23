"""Deduplication buffer for relay daemon.

Tracks seen packets by their hash for a configurable TTL window.
Duplicate packets within the TTL are rejected; expired entries are
cleaned up lazily on every call to ``is_duplicate``.
"""

from __future__ import annotations

import hashlib
import time


class DeduplicationBuffer:
    """Rolling deduplication window keyed by SHA-256 of packet bytes.

    Args:
        ttl_seconds: How long (in seconds) to remember a seen packet.
    """

    def __init__(self, ttl_seconds: float = 5.0) -> None:
        self._ttl = ttl_seconds
        # Maps packet_hash -> expiry timestamp (monotonic)
        self._seen: dict[bytes, float] = {}
        self.stats_new: int = 0
        self.stats_duplicate: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_duplicate(self, packet: bytes) -> bool:
        """Return True if *packet* was already seen within the TTL window.

        As a side effect this method:
        - Records *packet* as seen (or refreshes its expiry) if it is new.
        - Performs a lazy cleanup of expired entries.
        - Updates ``stats_new`` / ``stats_duplicate`` counters.
        """
        self._lazy_cleanup()

        key = self._hash(packet)
        now = time.monotonic()

        if key in self._seen and self._seen[key] > now:
            self.stats_duplicate += 1
            return True

        # New or expired: (re-)register the packet.
        self._seen[key] = now + self._ttl
        self.stats_new += 1
        return False

    def cleanup(self) -> None:
        """Remove all entries whose TTL has expired."""
        now = time.monotonic()
        expired = [k for k, exp in self._seen.items() if exp <= now]
        for k in expired:
            del self._seen[k]

    def __len__(self) -> int:
        return len(self._seen)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _lazy_cleanup(self) -> None:
        """Thin wrapper so the hot path stays in ``is_duplicate``."""
        self.cleanup()

    @staticmethod
    def _hash(packet: bytes) -> bytes:
        return hashlib.sha256(packet).digest()
