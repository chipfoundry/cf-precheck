from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.table import Table

from cf_precheck import __version__
from cf_precheck.logging import console


@dataclass
class CheckResult:
    name: str
    surname: str = ""
    status: str = "pass"  # "pass", "fail", "skip"
    duration_s: float = 0.0
    details: Optional[str] = None
    reason: Optional[str] = None

    @property
    def display_name(self) -> str:
        return self.surname or self.name

    def to_dict(self) -> dict:
        d: dict = {"status": self.status, "duration_s": round(self.duration_s, 2)}
        if self.details:
            d["details"] = self.details
        if self.reason:
            d["reason"] = self.reason
        return d


@dataclass
class ResultsCollector:
    pdk: str = ""
    input_file_hash: Optional[str] = None
    results: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    @property
    def all_passed(self) -> bool:
        return all(r.status != "fail" for r in self.results)

    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "fail"]

    @property
    def passed(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "pass"]

    @property
    def skipped(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "skip"]

    def print_summary(self) -> None:
        table = Table(title="Precheck Summary", show_lines=False, pad_edge=True)
        table.add_column("Check", style="bold", min_width=20)
        table.add_column("Status", justify="center", min_width=8)
        table.add_column("Duration", justify="right", min_width=10)

        for r in self.results:
            if r.status == "pass":
                status = "[pass]PASS[/pass]"
            elif r.status == "fail":
                status = "[fail]FAIL[/fail]"
            else:
                status = "[skip]SKIP[/skip]"
            duration = f"{r.duration_s:.1f}s" if r.duration_s > 0 else "-"
            table.add_row(r.display_name, status, duration)

        console.print()
        console.print(table)

    def write_to_project_json(self, project_dir: Path) -> None:
        """Merge precheck results into .cf/project.json."""
        cf_dir = project_dir / ".cf"
        cf_dir.mkdir(parents=True, exist_ok=True)
        project_json_path = cf_dir / "project.json"

        data: dict = {}
        if project_json_path.exists():
            try:
                data = json.loads(project_json_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        checks_dict = {}
        for r in self.results:
            checks_dict[r.name] = r.to_dict()

        precheck_blob: dict = {
            "version": __version__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pdk": self.pdk,
            "passed": self.all_passed,
            "checks": checks_dict,
        }
        if self.input_file_hash:
            precheck_blob["input_file_hash"] = self.input_file_hash

        data["precheck"] = precheck_blob

        project_json_path.write_text(json.dumps(data, indent=2) + "\n")
        console.print(f"[dim]Results saved to {project_json_path}[/dim]")
        console.print(f"[dim]Full log at {project_dir / 'precheck_results'}[/dim]")
