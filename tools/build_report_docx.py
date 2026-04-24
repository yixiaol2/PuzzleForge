"""Validate that the submitted executive summary deck is present."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTIVE_SUMMARY = ROOT / "docs" / "PuzzleForge_Executive_Summary.pptx"


def main() -> None:
    if not EXECUTIVE_SUMMARY.exists():
        raise SystemExit(f"Missing expected executive summary: {EXECUTIVE_SUMMARY}")
    print(f"Executive summary present: {EXECUTIVE_SUMMARY}")


if __name__ == "__main__":
    main()
