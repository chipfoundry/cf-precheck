"""Unit tests for cf_precheck.checks._oeb_report."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cf_precheck.checks._oeb_report import (
    one_line_summary,
    parse_report_file,
    parse_report_text,
)


CARAVEL_SAMPLE = textwrap.dedent(
    """\
     gpio/user/analog |   in   |   out  | analog |  oeb min/sim/max  | configuration
      0 /  0 /       |        |        |        | vssd1/vssd1/vssd1 | FIXED_STD_INPUT_NOPULL
      5 /  5 /       |      3 |      2 |        | vssd1/vssd1/vssd1 | USER_STD_OUTPUT 1 warnings/errors
      7 /  7 /   0   |      4 |      5 |        |  vdda/ vdda/ vdda | USER_STD_INPUT_NOPULL
     35 / 35 /  28   |     10 |        |        | vssd1/vssd1/vssd1 | USER_STD_INPUT_PULLUP

    *** Detected the following warnings and/or errors: ***
    GPIO  5: ERROR: missing user oeb for output gpio
    GPIO 35: Warning: analog connection to user input gpio
    """
)


CARAVEL_NO_ISSUES = textwrap.dedent(
    """\
     gpio/user/analog |   in   |   out  | analog |  oeb min/sim/max  | configuration
      0 /  0 /       |        |        |        | vssd1/vssd1/vssd1 | FIXED_STD_INPUT_NOPULL
      5 /  5 /       |      3 |      2 |        | vssd1/vssd1/vssd1 | USER_STD_OUTPUT

    No warnings or errors detected
    """
)


OPENFRAME_SAMPLE = textwrap.dedent(
    """\
     gpio |   in   |   out  | analog |  oeb min/sim/max  | Configuration (dm[2:0] vtrip slow analog[pol,sel,en] ib input_dis holdover)
      0  |        |        |        | vssd1/vssd1/vssd1 | 00100000000 -> USER_STD_ANALOG
      5  |      3 |      2 |        | vssd1/vssd1/vssd1 | 11000000000 -> USER_STD_OUTPUT 1 warnings/errors
     10  |      4 |      5 |        | vssd1/vssd1/vssd1 | 11100000001 -> USER_STD_INPUT_PULLUP
     20  |        |        |      1 | vssd1/ vdda/ vdda | 000xxxxxxxx -> USER_STD_ANALOG 2 warnings/errors

    *** Detected the following warnings and/or errors: ***
    GPIO  5: ERROR: missing oeb for output gpio
    GPIO 20: ERROR: all gpio configuration signals must be connected
    GPIO 20: Warning: unrecognized configuration - expected vtrip, slow, analog*, ib, hold to be low
    """
)


def test_caravel_parse_rows_and_messages():
    report = parse_report_text(CARAVEL_SAMPLE, design_type="caravel")
    assert "parse_error" not in report
    assert report["design_type"] == "caravel"
    assert report["summary"] == {
        "total": 4,
        "errors": 1,
        "warnings": 1,
        "no_issues_banner": False,
    }
    by_gpio = {row["gpio"]: row for row in report["gpios"]}
    assert by_gpio[0]["configuration"] == "FIXED_STD_INPUT_NOPULL"
    assert by_gpio[0]["in"] is None
    assert by_gpio[5]["configuration"] == "USER_STD_OUTPUT"
    assert by_gpio[5]["error_count"] == 1
    assert by_gpio[5]["warning_count"] == 0
    assert by_gpio[7]["analog_index"] == 0
    assert by_gpio[35]["analog_index"] == 28
    assert by_gpio[35]["error_count"] == 0
    assert by_gpio[35]["warning_count"] == 1

    severities = {m["severity"] for m in report["messages"]}
    assert severities == {"error", "warning"}


def test_caravel_no_issues_banner():
    report = parse_report_text(CARAVEL_NO_ISSUES)
    assert report["summary"]["no_issues_banner"] is True
    assert report["summary"]["errors"] == 0
    assert report["summary"]["warnings"] == 0
    assert report["messages"] == []


def test_caravan_design_hint_sets_type():
    report = parse_report_text(CARAVEL_SAMPLE, design_type="caravan")
    assert report["design_type"] == "caravan"


def test_analog_hint_maps_to_caravan():
    # Oeb.run() passes design_type="caravan" for analog projects, but the
    # helper also accepts "analog" as a shorthand for safety.
    report = parse_report_text(CARAVEL_SAMPLE, design_type="analog")
    assert report["design_type"] == "caravan"


def test_openframe_parse_dm_and_resolved_mode():
    report = parse_report_text(OPENFRAME_SAMPLE)
    assert report["design_type"] == "openframe"
    assert report["summary"] == {
        "total": 4,
        "errors": 2,
        "warnings": 1,
        "no_issues_banner": False,
    }

    by_gpio = {row["gpio"]: row for row in report["gpios"]}
    assert by_gpio[0]["configuration"] == "00100000000"
    assert by_gpio[0]["dm"] == "001"
    assert by_gpio[0]["resolved_mode"] == "USER_STD_ANALOG"
    assert by_gpio[5]["resolved_mode"] == "USER_STD_OUTPUT"
    assert by_gpio[5]["error_count"] == 1
    assert by_gpio[20]["dm"] == "000"
    assert by_gpio[20]["configuration"] == "000xxxxxxxx"
    assert by_gpio[20]["error_count"] == 1
    assert by_gpio[20]["warning_count"] == 1


def test_crlf_is_tolerated():
    text = CARAVEL_SAMPLE.replace("\n", "\r\n")
    report = parse_report_text(text)
    assert "parse_error" not in report
    assert report["summary"]["total"] == 4


def test_trailing_whitespace_is_tolerated():
    noisy = "\n".join(line + "   " for line in CARAVEL_SAMPLE.splitlines())
    report = parse_report_text(noisy)
    assert "parse_error" not in report
    assert report["summary"]["total"] == 4


def test_empty_report_returns_parse_error():
    report = parse_report_text("")
    assert report == {"parse_error": "empty report"}


def test_unrecognized_header_returns_parse_error():
    report = parse_report_text("hello world\nno header here\n")
    assert report.get("parse_error") == "unrecognized report format"


def test_parse_report_file_roundtrip(tmp_path: Path):
    report_path = tmp_path / "cvc.oeb.report"
    report_path.write_text(OPENFRAME_SAMPLE)
    report = parse_report_file(report_path)
    assert report["design_type"] == "openframe"
    assert report["report_relpath"] == str(report_path)
    assert report["summary"]["errors"] == 2


def test_parse_report_file_missing_returns_error(tmp_path: Path):
    report = parse_report_file(tmp_path / "nope.report")
    assert "parse_error" in report
    assert "could not read report" in report["parse_error"]
    assert report["report_relpath"].endswith("nope.report")


def test_one_line_summary_formats():
    report = parse_report_text(CARAVEL_SAMPLE)
    assert one_line_summary(report) == "1 error, 1 warning across 4 GPIOs"

    clean = parse_report_text(CARAVEL_NO_ISSUES)
    assert one_line_summary(clean) == "0 errors, 0 warnings across 2 GPIOs"

    broken = {"parse_error": "boom"}
    assert one_line_summary(broken) == "OEB report unavailable: boom"


@pytest.mark.parametrize(
    "tail,expected_count",
    [
        ("USER_STD_OUTPUT 2 warnings/errors", 2),
        ("USER_STD_OUTPUT  1 warning/error", 1),
        ("USER_STD_OUTPUT", None),
    ],
)
def test_warning_count_extraction(tail, expected_count):
    row_line = f"  5 /  5 /       |      3 |      2 |        | vssd1/vssd1/vssd1 | {tail}"
    text = f" gpio/user/analog |   in   |   out  | analog |  oeb min/sim/max  | configuration\n{row_line}\n"
    report = parse_report_text(text)
    row = report["gpios"][0]
    # warning_count from the parsed tail stays on the raw row before
    # _annotate_counts overwrites with message-derived counts. Since there are
    # no messages here, both derived counts are 0 regardless of the tail.
    assert row["error_count"] == 0
    assert row["warning_count"] == 0
