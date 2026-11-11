#!/usr/bin/env python3
"""Run pipeline stages in order and refuse to trust "ok" without evidence.

An agent's turn ending ok is the agent's claim, not proof. Each stage can
declare `expect` checks that run after it finishes:

  {"file": "out/brief-{date}.md"}          must exist and be written during the stage
  {"file": "...", "fresh_minutes": 30}     or modified in the last N minutes
  {"stdout_regex": "drafted \\d+"}         stdout must match
  {"stdout_not_regex": "(?i)unable to"}    stdout must not match

A stage that exits 0 but misses a check is `unverified`. It counts as a failure,
and every stage that lists it in `needs` is skipped.

  python3 pipeline_expect.py pipeline.example.json
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path


def check_expect(stage: dict, out: str, started: float) -> list[str]:
    misses = []
    for c in stage.get("expect") or []:
        if "file" in c:
            p = Path(c["file"].format(date=date.today().isoformat()))
            if not p.exists():
                misses.append(f"missing {p}")
                continue
            cutoff = time.time() - c["fresh_minutes"] * 60 if "fresh_minutes" in c else started
            if p.stat().st_mtime < cutoff:
                misses.append(f"stale {p}")
        if "stdout_regex" in c and not re.search(c["stdout_regex"], out):
            misses.append(f"stdout lacks /{c['stdout_regex']}/")
        if "stdout_not_regex" in c and re.search(c["stdout_not_regex"], out):
            misses.append(f"stdout matched /{c['stdout_not_regex']}/")
    return misses


def main(path: str) -> int:
    stages = json.loads(Path(path).read_text())["stages"]
    status: dict[str, str] = {}

    for st in stages:
        name = st["name"]
        blocked = [n for n in st.get("needs", []) if status.get(n) != "ok"]
        if blocked:
            status[name] = "skipped"
            continue
        started = time.time()
        r = subprocess.run(st["cmd"], shell=True, capture_output=True, text=True,
                           timeout=st.get("timeout", 900))
        if r.returncode != 0:
            status[name] = "failed"
        elif misses := check_expect(st, r.stdout, started):
            status[name] = "unverified: " + ", ".join(misses)
        else:
            status[name] = "ok"

    bad = {k: v for k, v in status.items() if v != "ok"}
    if bad:
        print("WARNING: " + "; ".join(f"{k} {v}" for k, v in bad.items()))
        return 1
    print(f"{len(status)} stages ok, all verified")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "pipeline.example.json"))
