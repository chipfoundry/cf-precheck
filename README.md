# cf-precheck

ChipFoundry MPW tapeout precheck tool. Validates user projects before shuttle submission by running a sequence of design-rule and consistency checks.

## Installation

```bash
pip install cf-precheck
```

### External tool dependencies

Some checks invoke external EDA tools that must be available on `$PATH`:

- [KLayout](https://www.klayout.de/) — used by all Klayout DRC checks and the XOR check
- [Magic](http://opencircuitdesign.com/magic/) — used by the optional Magic DRC check and LVS
- [Netgen](http://opencircuitdesign.com/netgen/) — used by the LVS check

## Usage

```
cf-precheck -i <project_dir> -p <pdk_path> -c <caravel_root> [options] [check ...]
```

### Required arguments

| Flag | Description |
|------|-------------|
| `-i`, `--input-directory` | Path to the user project directory |
| `-p`, `--pdk-path` | Path to the PDK installation (variant-specific, e.g. `$PDK_ROOT/sky130A`) |
| `-c`, `--caravel-root` | Path to the golden Caravel root (or set `$GOLDEN_CARAVEL`) |

### Optional arguments

| Flag | Description |
|------|-------------|
| `-o`, `--output-directory` | Output directory (default: `<project>/precheck_results/<timestamp>`) |
| `--magic-drc` | Include the Magic DRC check (off by default) |
| `--skip-checks check [...]` | Skip specific checks |
| `-v`, `--verbose` | Show verbose/debug output |
| `--version` | Print version and exit |

### Positional arguments

Pass one or more check names to run only those checks. If omitted, all applicable checks are run.

### Example

```bash
# Run all checks
cf-precheck -i ./my_project -p $PDK_ROOT/sky130A -c ./caravel

# Run only specific checks
cf-precheck -i ./my_project -p $PDK_ROOT/sky130A -c ./caravel topcell_check gpio_defines

# Include the optional Magic DRC check
cf-precheck -i ./my_project -p $PDK_ROOT/sky130A -c ./caravel --magic-drc

# Skip certain checks
cf-precheck -i ./my_project -p $PDK_ROOT/sky130A -c ./caravel --skip-checks lvs oeb
```

## Checks

| Check | Description |
|-------|-------------|
| `topcell_check` | Validates the top cell name in the GDS |
| `gpio_defines` | Validates GPIO directives in `verilog/rtl/user_defines.v` |
| `pdn` | Power distribution network check |
| `metal_check` | Metal density check |
| `xor` | XOR comparison against the golden wrapper to detect out-of-bounds edits |
| `magic_drc` | Full DRC using Magic *(optional, off by default)* |
| `klayout_feol` | Klayout Front End Of Line DRC |
| `klayout_beol` | Klayout Back End Of Line DRC |
| `klayout_offgrid` | Klayout off-grid violations check |
| `klayout_metal_minimum_clear_area_density` | Klayout metal density check |
| `klayout_pin_label_purposes_overlapping_drawing` | Klayout pin/label overlap check |
| `klayout_zero_area` | Klayout zero-area cell check |
| `spike_check` | Detects invalid paths in the design |
| `illegal_cellname_check` | Detects cells with illegal names |
| `oeb` | Output-enable-bar signal connectivity check |
| `lvs` | Layout vs. Schematic check |

## Results

Check results are saved to `<project>/.cf/project.json` under the `precheck` key:

```json
{
  "precheck": {
    "version": "1.0.0",
    "timestamp": "2026-03-17T12:00:00+00:00",
    "pdk": "sky130A",
    "passed": false,
    "checks": {
      "topcell_check": { "status": "pass", "duration_s": 1.2 },
      "gpio_defines": { "status": "fail", "duration_s": 0.8, "details": "..." }
    }
  }
}
```

Detailed logs are written to `<project>/precheck_results/<timestamp>/logs/precheck.log`.

## License

Apache-2.0
