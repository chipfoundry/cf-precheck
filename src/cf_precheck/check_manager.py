from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path

from cf_precheck.checks.topcell import TopcellCheck
from cf_precheck.checks.gpio_defines import GpioDefines
from cf_precheck.checks.pdn import PDNMulti
from cf_precheck.checks.metal import MetalCheck
from cf_precheck.checks.xor import XOR
from cf_precheck.checks.magic_drc import MagicDRC
from cf_precheck.checks.klayout_drc import (
    KlayoutFEOL, KlayoutBEOL, KlayoutOffgrid,
    KlayoutMetalMinimumClearAreaDensity,
    KlayoutPinLabelPurposesOverlappingDrawing,
    KlayoutZeroArea,
)
from cf_precheck.checks.spike import SpikeCheck
from cf_precheck.checks.illegal_cellname import IllegalCellnameCheck
from cf_precheck.checks.oeb import Oeb
from cf_precheck.checks.lvs import Lvs


class CheckManagerNotFound(Exception):
    pass


class CheckManager:
    __ref__: str | None = None
    __surname__: str | None = None
    __supported_pdks__: list[str] | None = None
    __supported_type__: list[str] = ["analog", "digital", "openframe", "mini"]
    __optional__: bool = False

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.result = True

    def run(self) -> bool:
        """Override in subclasses to implement the check."""
        return self.result


ALL_CHECKS: OrderedDict[str, type[CheckManager]] = OrderedDict([
    (TopcellCheck.__ref__, TopcellCheck),
    (GpioDefines.__ref__, GpioDefines),
    (PDNMulti.__ref__, PDNMulti),
    (MetalCheck.__ref__, MetalCheck),
    (XOR.__ref__, XOR),
    (MagicDRC.__ref__, MagicDRC),
    (KlayoutFEOL.__ref__, KlayoutFEOL),
    (KlayoutBEOL.__ref__, KlayoutBEOL),
    (KlayoutOffgrid.__ref__, KlayoutOffgrid),
    (KlayoutMetalMinimumClearAreaDensity.__ref__, KlayoutMetalMinimumClearAreaDensity),
    (KlayoutPinLabelPurposesOverlappingDrawing.__ref__, KlayoutPinLabelPurposesOverlappingDrawing),
    (KlayoutZeroArea.__ref__, KlayoutZeroArea),
    (SpikeCheck.__ref__, SpikeCheck),
    (IllegalCellnameCheck.__ref__, IllegalCellnameCheck),
    (Oeb.__ref__, Oeb),
    (Lvs.__ref__, Lvs),
])


def build_sequence(
    all_checks: OrderedDict[str, type[CheckManager]],
    pdk: str,
    project_type: str,
    include_optional: bool = False,
    only: list[str] | None = None,
    skip: list[str] | None = None,
) -> list[str]:
    """
    Build the ordered list of check ref-keys to run, filtering by PDK,
    project type, optional status, and user overrides.
    """
    sequence: list[str] = []
    for ref, cls in all_checks.items():
        if cls.__supported_pdks__ and pdk not in cls.__supported_pdks__:
            continue
        if project_type not in cls.__supported_type__:
            continue
        if cls.__optional__ and not include_optional:
            continue
        sequence.append(ref)

    if only:
        sequence = [c for c in sequence if c in only]
    if skip:
        sequence = [c for c in sequence if c not in skip]

    return sequence


def get_check_manager(name: str, precheck_config: dict, project_config: dict) -> CheckManager:
    if name.lower() in ALL_CHECKS:
        return ALL_CHECKS[name.lower()](precheck_config, project_config)
    raise CheckManagerNotFound(f"The check '{name}' does not exist")
