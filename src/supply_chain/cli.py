"""
cli.py — Command-line entry point for the supply-chain generator.

Usage:
    python -m supply_chain.cli generate --seed 20261022 --mode starter --output-dir data/
    python -m supply_chain.cli generate --seed 20261022 --mode full   --output-dir data/

Modes:
    starter  ~10 % of full scale; completes in < 30 s; used for CI and dev iteration.
    full     500 suppliers, 10k lots, 5k POs, 8k finished lots, 20k deliveries.

This module is intentionally minimal for Block 1. Full generation logic is
implemented in subsequent blocks (generators/, recall/, injectors/, exporters/).
"""

import argparse
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="supply-chain",
        description="YottaFlex Supply-Chain Traceability & Recall Simulation Generator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate the supply-chain dataset")
    gen.add_argument(
        "--seed",
        type=int,
        default=20261022,
        help="Random seed for deterministic generation (default: 20261022)",
    )
    gen.add_argument(
        "--mode",
        choices=["starter", "full"],
        default="starter",
        help="Dataset scale: starter (~10%%) or full (default: starter)",
    )
    gen.add_argument(
        "--output-dir",
        default="data/",
        help="Directory to write output files (default: data/)",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns exit code."""
    args = _parse_args(argv)

    if args.command == "generate":
        # Block 2+ will wire in the full generator pipeline here.
        print(
            f"[supply-chain] generate  seed={args.seed}  mode={args.mode}  "
            f"output={args.output_dir}",
            file=sys.stderr,
        )
        print(
            "Generator pipeline not yet implemented. "
            "Block 1 complete: entity models, ID factory, FSM, and tests.",
            file=sys.stderr,
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
