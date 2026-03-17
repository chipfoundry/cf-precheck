#!/usr/bin/env python3
"""Backward-compatible entry point for mpw_precheck.

Old cf-cli versions invoke:
    python3 mpw_precheck.py --input_directory <path> --pdk_path <path> [checks...]

This shim translates those arguments and delegates to the new cf-precheck CLI.
"""
import os
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--input_directory", "-i")
    parser.add_argument("--pdk_path", "-p")
    parser.add_argument("--output_directory", "-o", default=None)
    parser.add_argument("--private", action="store_true")
    args, remaining = parser.parse_known_args()

    cmd = ["cf-precheck"]

    if args.input_directory:
        cmd.extend(["-i", args.input_directory])
    if args.pdk_path:
        cmd.extend(["-p", args.pdk_path])
    if args.output_directory:
        cmd.extend(["-o", args.output_directory])

    caravel_root = os.environ.get("GOLDEN_CARAVEL")
    if caravel_root:
        cmd.extend(["-c", caravel_root])

    cmd.extend(remaining)

    os.execvp("cf-precheck", cmd)


if __name__ == "__main__":
    main()
