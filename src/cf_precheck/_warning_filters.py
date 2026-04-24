"""Classifiers for the captured-warning fallback used by runner.py.

Lives in its own tiny module so unit tests can import the classifier without
pulling in the full check stack (which transitively imports pya/KLayout and
only works inside the precheck Docker image).
"""

from __future__ import annotations


# Warnings emitted during setup that must stay visible in the log but must
# NOT become the one-line FAIL summary for a check. Each entry is a plain
# substring match against the captured log message.
#
# Example: "Missing LVS configuration variable EXTRACT_CREATE_SUBCUT" fires
# for almost every user project whose lvs_config.*.json doesn't populate the
# optional LVS optimisation keys, and it always fires before the real OEB
# or LVS failure reason. Without this filter the real error gets masked.
BENIGN_WARNING_SUBSTRINGS: tuple[str, ...] = (
    "Missing LVS configuration variable ",
)


def is_benign_warning(message: str) -> bool:
    """Return True if a captured WARNING shouldn't be surfaced as fail detail."""
    return any(needle in message for needle in BENIGN_WARNING_SUBSTRINGS)
