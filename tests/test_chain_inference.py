"""
Regression tests for the chain detector.

Catches the class of bug that landed Nathan's Bitaxe_004 (pointed at the
DGB pool us1.letsmine.it) under the BTC pool group — `letsmine` wasn't
in the DGB URL needle list. Each fixture pins a real-world (URL, port,
user) → expected_chain mapping so adding a new chain or rearranging
patterns can't silently break the others.
"""

import sys
import os
from pathlib import Path

# Allow running as `python3 tests/test_chain_inference.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import _infer_chain, _CHAIN_INFERENCE_FIXTURES


def main() -> int:
    failures = []
    for label, url, port, user, expected in _CHAIN_INFERENCE_FIXTURES:
        actual = _infer_chain(url, port, user)
        if actual != expected:
            failures.append(
                f"  FAIL  {label!r}: {url}:{port} user={user!r} → got {actual!r}, expected {expected!r}"
            )

    total = len(_CHAIN_INFERENCE_FIXTURES)
    print(f"chain inference: {total - len(failures)} / {total} pass")
    for f in failures:
        print(f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
