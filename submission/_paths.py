"""Shared starter-kit locator for all submission scripts.

The audited inputs (fertility.py, corpus_sample/, bench/) live in the starter
kit, which the assignment ships as a zip that extracts to a doubled folder
(starter_kit/starter_kit/). Resolution order:

1. the STARTER_KIT environment variable (points at the folder containing
   fertility.py / bench/), for graders with any layout;
2. walking upward from this file, trying both starter_kit/ and
   starter_kit/starter_kit/ nestings.

Fails fast with an actionable message instead of a FileNotFoundError mid-run.
"""

import os
from pathlib import Path


def find_starter_kit(start: Path | None = None) -> Path:
    env = os.environ.get("STARTER_KIT")
    if env:
        p = Path(env)
        if (p / "bench" / "bench_log.csv").exists():
            return p
        raise SystemExit(f"STARTER_KIT={env} does not contain bench/bench_log.csv")
    here = (start or Path(__file__)).resolve()
    for base in [here, *here.parents]:
        for cand in (base / "starter_kit" / "starter_kit", base / "starter_kit"):
            if (cand / "bench" / "bench_log.csv").exists():
                return cand
    raise SystemExit(
        "starter_kit not found (looked for bench/bench_log.csv in starter_kit/ and "
        "starter_kit/starter_kit/ up the tree). Set STARTER_KIT=<path-to-kit>."
    )
