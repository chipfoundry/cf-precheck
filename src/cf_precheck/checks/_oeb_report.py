"""Parse cvc.oeb.report into a structured dict for UI consumption.

The backend OEB scripts (see cf_precheck/be_checks/run_oeb_check and
cf_precheck/be_checks/run_openframe_check) emit a human-readable report with
two distinct formats:

caravel / caravan (padring-adjusted gpio, user index, analog index):

    " gpio/user/analog |   in   |   out  | analog |  oeb min/sim/max  | configuration"
    "  35 / 35 /  28   |    10 |    20 |        | vssd1/vssd1/vssd1 | USER_STD_OUTPUT 2 warnings/errors"

openframe (raw gpio index, configuration bit string, resolved mode):

    " gpio |   in   |   out  | analog |  oeb min/sim/max  | Configuration (dm[2:0] vtrip slow analog[pol,sel,en] ib input_dis holdover)"
    "  35  |    10 |    20 |        | vssd1/vssd1/vssd1 | 01100000000 -> USER_STD_OUTPUT 2 warnings/errors"

Both formats end with either

    "No warnings or errors detected"

or

    "*** Detected the following warnings and/or errors: ***"
    "GPIO 35: ERROR: user input connection to user output gpio - undriven"
    "GPIO 36: Warning: user output fixed at vssd1"
    ...

The parser is intentionally permissive: unknown lines are skipped, and any
failure returns a dict with a ``parse_error`` key so the UI can still show a
warning without losing the overall check status.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional


CARAVEL_HEADER_PREFIX = "gpio/user/analog"
OPENFRAME_HEADER_PREFIX = "gpio |"
OPENFRAME_HEADER_MARKER = "Configuration (dm[2:0]"

_CARAVEL_ROW_RE = re.compile(
    r"""^\s*
        (?P<gpio>\d+)\s*/\s*
        (?P<user>\d+)\s*/\s*
        (?P<analog>\d+|)\s*\|\s*
        (?P<in>\S*)\s*\|\s*
        (?P<out>\S*)\s*\|\s*
        (?P<analog_count>\S*)\s*\|\s*
        (?P<oeb_min>\S*)\s*/\s*(?P<oeb_sim>\S*)\s*/\s*(?P<oeb_max>\S*)\s*\|\s*
        (?P<tail>.*)$
    """,
    re.VERBOSE,
)

_OPENFRAME_ROW_RE = re.compile(
    r"""^\s*
        (?P<gpio>\d+)\s*\|\s*
        (?P<in>\S*)\s*\|\s*
        (?P<out>\S*)\s*\|\s*
        (?P<analog_count>\S*)\s*\|\s*
        (?P<oeb_min>\S*)\s*/\s*(?P<oeb_sim>\S*)\s*/\s*(?P<oeb_max>\S*)\s*\|\s*
        (?P<tail>.*)$
    """,
    re.VERBOSE,
)

_MSG_RE = re.compile(
    r"""^\s*GPIO\s+(?P<gpio>\d+)\s*:\s*
        (?P<severity>ERROR|Warning)\s*:\s*
        (?P<text>.+?)\s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

_WARN_COUNT_RE = re.compile(r"(\d+)\s+warnings?/errors?", re.IGNORECASE)

_OPENFRAME_DM_BITS = 3
_OPENFRAME_CONFIG_LEN = 11


def _clean(line: str) -> str:
    return line.rstrip("\r\n").rstrip()


def _maybe_int(value: str) -> Optional[int]:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_tail_caravel(tail: str) -> tuple[str, Optional[int]]:
    """Split trailing mode cell into (configuration, warning_count).

    Caravel/caravan reports render the configuration as a single mode name
    such as ``USER_STD_OUTPUT`` followed optionally by ``"N warnings/errors"``
    and any additional free-text warnings printed for the "unknown mode" case.
    """
    tail = tail.strip()
    warning_count: Optional[int] = None
    match = _WARN_COUNT_RE.search(tail)
    if match:
        warning_count = int(match.group(1))
        tail = (tail[: match.start()] + tail[match.end():]).strip()
    return tail, warning_count


def _parse_tail_openframe(tail: str) -> tuple[Optional[str], Optional[str], Optional[int]]:
    """Split trailing column into (config_bits, resolved_mode, warning_count).

    Openframe rows look like ``"01100000000 -> USER_STD_OUTPUT 2 warnings/errors"``.
    """
    tail = tail.strip()
    warning_count: Optional[int] = None
    match = _WARN_COUNT_RE.search(tail)
    if match:
        warning_count = int(match.group(1))
        tail = (tail[: match.start()] + tail[match.end():]).strip()

    config_bits: Optional[str] = None
    resolved: Optional[str] = None
    if "->" in tail:
        left, right = tail.split("->", 1)
        config_bits = left.strip() or None
        resolved = right.strip() or None
    else:
        # All-bits-known-but-mode-unknown case still prints a config.
        resolved = tail or None

    if resolved and resolved.upper() == "UNKNOWN":
        resolved = None
    return config_bits, resolved, warning_count


def _detect_format(lines: list[str]) -> Optional[str]:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if CARAVEL_HEADER_PREFIX in stripped:
            return "caravel"
        if OPENFRAME_HEADER_MARKER in stripped:
            return "openframe"
        if stripped.startswith(OPENFRAME_HEADER_PREFIX) and "Configuration" in stripped:
            return "openframe"
    return None


def _parse_messages(lines: list[str]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        match = _MSG_RE.match(line)
        if not match:
            continue
        severity = match.group("severity")
        normalized = "error" if severity.upper() == "ERROR" else "warning"
        messages.append({
            "gpio": int(match.group("gpio")),
            "severity": normalized,
            "text": match.group("text").strip(),
        })
    return messages


def _split_gpio_rows_and_messages(lines: list[str]) -> tuple[list[str], list[str], bool]:
    """Return (row_lines, message_lines, has_explicit_no_issues_marker).

    Rows appear after the header and before either the "No warnings or errors"
    line or the "*** Detected ..." banner. Messages appear after the banner.
    """
    row_lines: list[str] = []
    message_lines: list[str] = []
    header_seen = False
    in_messages = False
    no_issues_seen = False

    for raw in lines:
        line = _clean(raw)
        stripped = line.strip()
        if not header_seen:
            if (
                CARAVEL_HEADER_PREFIX in stripped
                or OPENFRAME_HEADER_MARKER in stripped
                or (stripped.startswith(OPENFRAME_HEADER_PREFIX) and "Configuration" in stripped)
            ):
                header_seen = True
            continue

        if not stripped:
            continue

        if stripped.startswith("***") and "Detected" in stripped:
            in_messages = True
            continue

        if stripped == "No warnings or errors detected":
            no_issues_seen = True
            in_messages = True
            continue

        if in_messages:
            message_lines.append(line)
        else:
            row_lines.append(line)

    return row_lines, message_lines, no_issues_seen


def _parse_caravel(row_lines: list[str]) -> list[dict[str, Any]]:
    gpios: list[dict[str, Any]] = []
    for line in row_lines:
        match = _CARAVEL_ROW_RE.match(line)
        if not match:
            continue
        configuration, warning_count = _parse_tail_caravel(match.group("tail"))
        gpios.append({
            "gpio": int(match.group("gpio")),
            "user_index": int(match.group("user")),
            "analog_index": _maybe_int(match.group("analog")),
            "in": _maybe_int(match.group("in")),
            "out": match.group("out").strip() or None,
            "analog": _maybe_int(match.group("analog_count")),
            "oeb_min": match.group("oeb_min").strip() or None,
            "oeb_sim": match.group("oeb_sim").strip() or None,
            "oeb_max": match.group("oeb_max").strip() or None,
            "configuration": configuration or None,
            "resolved_mode": configuration or None,
            "warning_count": warning_count,
        })
    return gpios


def _parse_openframe(row_lines: list[str]) -> list[dict[str, Any]]:
    gpios: list[dict[str, Any]] = []
    for line in row_lines:
        match = _OPENFRAME_ROW_RE.match(line)
        if not match:
            continue
        config_bits, resolved, warning_count = _parse_tail_openframe(match.group("tail"))
        dm = config_bits[:_OPENFRAME_DM_BITS] if config_bits and len(config_bits) >= _OPENFRAME_DM_BITS else None
        gpios.append({
            "gpio": int(match.group("gpio")),
            "user_index": int(match.group("gpio")),
            "analog_index": None,
            "in": _maybe_int(match.group("in")),
            "out": match.group("out").strip() or None,
            "analog": _maybe_int(match.group("analog_count")),
            "oeb_min": match.group("oeb_min").strip() or None,
            "oeb_sim": match.group("oeb_sim").strip() or None,
            "oeb_max": match.group("oeb_max").strip() or None,
            "configuration": config_bits,
            "dm": dm,
            "resolved_mode": resolved,
            "warning_count": warning_count,
        })
    return gpios


def _annotate_counts(
    gpios: list[dict[str, Any]],
    messages: list[dict[str, Any]],
) -> None:
    """Populate per-GPIO error/warning counts from the message list.

    Prefer counts derived from messages over the awk "N warnings/errors" token
    because the latter combines both severities without distinguishing them.
    """
    by_gpio: dict[int, dict[str, int]] = {}
    for msg in messages:
        tally = by_gpio.setdefault(msg["gpio"], {"errors": 0, "warnings": 0})
        if msg["severity"] == "error":
            tally["errors"] += 1
        else:
            tally["warnings"] += 1
    for row in gpios:
        tally = by_gpio.get(row["gpio"], {"errors": 0, "warnings": 0})
        row["error_count"] = tally["errors"]
        row["warning_count"] = tally["warnings"]


def parse_report_text(text: str, *, design_type: Optional[str] = None) -> dict[str, Any]:
    """Parse raw cvc.oeb.report text into a structured dict."""
    if not text.strip():
        return {"parse_error": "empty report"}

    lines = text.splitlines()
    detected = _detect_format(lines)
    if detected is None:
        return {"parse_error": "unrecognized report format"}

    row_lines, message_lines, no_issues = _split_gpio_rows_and_messages(lines)
    messages = _parse_messages(message_lines)

    if detected == "caravel":
        gpios = _parse_caravel(row_lines)
        rendered_type = "caravel"
        # Heuristic: caravan reports keep the same header but apply a +11 offset
        # for gpios above 13 (see run_oeb_check). We cannot reliably distinguish
        # caravel from caravan from the report alone, so fall back to the
        # caller-provided design_type when present.
        if design_type in {"caravan", "analog", "caravel"}:
            rendered_type = design_type if design_type in {"caravel", "caravan"} else (
                "caravan" if design_type == "analog" else "caravel"
            )
    else:
        gpios = _parse_openframe(row_lines)
        rendered_type = "openframe"

    _annotate_counts(gpios, messages)

    errors = sum(1 for m in messages if m["severity"] == "error")
    warnings = sum(1 for m in messages if m["severity"] == "warning")

    return {
        "design_type": rendered_type,
        "gpios": gpios,
        "messages": messages,
        "summary": {
            "total": len(gpios),
            "errors": errors,
            "warnings": warnings,
            "no_issues_banner": no_issues,
        },
    }


def parse_report_file(path: Path, *, design_type: Optional[str] = None) -> dict[str, Any]:
    """Read and parse cvc.oeb.report from disk.

    Returns a dict that always includes a ``report_relpath`` pointing at the
    report location (relative-ish — actually the absolute filename the caller
    passed in). On any IO / parse failure, a ``parse_error`` key is set
    instead of raising, so the caller never has to guard against an exception.
    """
    payload: dict[str, Any] = {"report_relpath": str(path)}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        payload["parse_error"] = f"could not read report: {exc}"
        logging.debug("OEB report read failed: %s", exc)
        return payload

    try:
        parsed = parse_report_text(text, design_type=design_type)
    except Exception as exc:  # pragma: no cover - defensive
        payload["parse_error"] = f"parser crashed: {exc}"
        logging.debug("OEB report parse crashed: %s", exc, exc_info=True)
        return payload

    payload.update(parsed)
    return payload


def one_line_summary(report: dict[str, Any]) -> str:
    """Human-readable summary to stash in CheckResult.details."""
    if "parse_error" in report:
        return f"OEB report unavailable: {report['parse_error']}"
    summary = report.get("summary") or {}
    total = summary.get("total", 0)
    errors = summary.get("errors", 0)
    warnings = summary.get("warnings", 0)
    if errors == 0 and warnings == 0:
        return f"0 errors, 0 warnings across {total} GPIOs"
    return f"{errors} error{'s' if errors != 1 else ''}, {warnings} warning{'s' if warnings != 1 else ''} across {total} GPIOs"
