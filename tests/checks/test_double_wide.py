"""Double-wide openframe specific checks."""

from __future__ import annotations

import re
from pathlib import Path

from cf_precheck.checks.xor import XOR

_BE_CHECKS = Path(__file__).resolve().parents[2] / "src/cf_precheck/be_checks"


def test_oeb_script_covers_all_63_double_wide_gpios():
    script = (_BE_CHECKS / "run_openframe_check").read_text()
    block = re.search(r'if \[\[ "\$DESIGN_NAME" == \*double_wide\* \]\]; then\s+gpio_max=(\d+)', script)
    assert block is not None
    assert int(block.group(1)) == 62


def test_xor_fails_cleanly_when_golden_missing(tmp_path, caplog):
    pdk = tmp_path / "pdks" / "sky130A"
    pdk.mkdir(parents=True)
    precheck_config = {
        "pdk_path": pdk,
        "caravel_root": tmp_path / "stock_caravel",
        "input_directory": tmp_path / "project",
        "output_directory": tmp_path / "out",
    }
    project_config = {
        "type": "double_wide",
        "user_module": "double_wide_openframe_project_wrapper",
        "golden_wrapper": "double_wide_openframe_project_wrapper_empty",
    }
    assert XOR(precheck_config, project_config).run() is False
    assert "double-wide harness root" in caplog.text
