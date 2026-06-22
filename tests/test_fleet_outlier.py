"""
Regression tests for fleet-outlier detection.

Catches the Pro-user bug (2026-06) where a correctly-tuned Gamma got
flagged "Fleet outlier" simply for being monitored alongside higher-
hashrate machines. The old check compared raw GH/s against the fleet
median; the fix compares each board's actual-vs-EXPECTED hashrate %,
which is normalized for chip count and model — so mixing board sizes no
longer produces a false positive. A board lagging its OWN spec relative
to its siblings is still flagged.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import _enrich_fleet_outliers


def _dev(label, hashrate, pct_expected, hw=0.1, chain="btc", online=True):
    """Minimal summary with just the fields _enrich_fleet_outliers reads."""
    return {
        "label": label,
        "online": online,
        "metrics": {"hashRate": hashrate},
        "efficiency": {"actualPctOfExpected": pct_expected},
        "hwErrors": {"ratePct": hw},
        "chain": chain,
    }


def _has_outlier(summary):
    return any(r.get("id") == "fleet_outlier"
               for r in summary.get("recommendations", []))


def main() -> int:
    failures = []

    def check(name, cond):
        if not cond:
            failures.append(name)

    # 1. THE BUG: a healthy ~1.2 TH/s Gamma in a fleet of higher-hashrate
    #    machines. All three run at ~100% of their own expected output, so
    #    none should be flagged — even though raw GH/s differs ~4x.
    fleet = _enrich_fleet_outliers([
        _dev("gamma",   hashrate=1200, pct_expected=99),
        _dev("big-1",   hashrate=4800, pct_expected=100),
        _dev("big-2",   hashrate=4700, pct_expected=101),
    ])
    check("healthy mixed fleet: gamma not flagged", not _has_outlier(fleet[0]))
    check("healthy mixed fleet: nobody flagged",
          not any(_has_outlier(s) for s in fleet))

    # 2. A genuinely underperforming board (65% of its own expected) among
    #    healthy siblings SHOULD be flagged.
    fleet = _enrich_fleet_outliers([
        _dev("laggard", hashrate=780,  pct_expected=65),
        _dev("ok-1",    hashrate=1200, pct_expected=100),
        _dev("ok-2",    hashrate=1190, pct_expected=99),
    ])
    check("real laggard flagged", _has_outlier(fleet[0]))
    check("healthy siblings not flagged",
          not _has_outlier(fleet[1]) and not _has_outlier(fleet[2]))

    # 3. HW-error arm still fires independently of hashrate.
    fleet = _enrich_fleet_outliers([
        _dev("errorbox", hashrate=1200, pct_expected=100, hw=3.0),
        _dev("clean-1",  hashrate=1200, pct_expected=100, hw=0.1),
        _dev("clean-2",  hashrate=1200, pct_expected=100, hw=0.1),
    ])
    check("HW-error outlier flagged", _has_outlier(fleet[0]))
    check("clean boards not flagged",
          not _has_outlier(fleet[1]) and not _has_outlier(fleet[2]))

    # 4. Below the 3-device minimum → never fires.
    fleet = _enrich_fleet_outliers([
        _dev("solo-1", hashrate=1200, pct_expected=50),
        _dev("solo-2", hashrate=4800, pct_expected=100),
    ])
    check("sub-threshold fleet: no flags",
          not any(_has_outlier(s) for s in fleet))

    # 5. Boards with no expected figure yet (0%) are ignored, not flagged.
    fleet = _enrich_fleet_outliers([
        _dev("warming", hashrate=0,    pct_expected=0),
        _dev("ok-1",    hashrate=1200, pct_expected=100),
        _dev("ok-2",    hashrate=1190, pct_expected=99),
    ])
    check("zero-expected board not flagged", not _has_outlier(fleet[0]))

    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        return 1
    print("ok — all fleet-outlier regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
