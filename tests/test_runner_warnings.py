"""Tests for the fail-summary benign-warning filter.

The runner captures any WARNING/ERROR logs emitted during a check and uses
the first one as the user-visible fail summary when the check itself did not
set ``details``. Benign setup warnings (e.g. missing optional LVS config
variables) must be excluded from that fallback so real failure reasons
remain visible.
"""

from __future__ import annotations

from cf_precheck._warning_filters import (
    BENIGN_WARNING_SUBSTRINGS,
    is_benign_warning,
)


def test_missing_lvs_config_variable_is_benign() -> None:
    assert is_benign_warning(
        "Missing LVS configuration variable EXTRACT_CREATE_SUBCUT"
    )
    assert is_benign_warning(
        "Missing LVS configuration variable LVS_FLATTEN"
    )


def test_real_error_is_not_benign() -> None:
    assert not is_benign_warning(
        "OEB FAILED: could not find LVS configuration file lvs_config.json"
    )
    assert not is_benign_warning("Magic DRC reported 12 errors in layout")
    assert not is_benign_warning("")


def test_benign_substrings_are_plain_strings_not_regex() -> None:
    # Sanity: keep the filter a plain-substring list so it's easy to reason
    # about and impossible to accidentally disable via user-supplied text.
    for needle in BENIGN_WARNING_SUBSTRINGS:
        assert isinstance(needle, str) and needle
        assert not any(c in needle for c in "()[]{}.*+?^$\\|")
