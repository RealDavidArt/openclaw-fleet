#!/usr/bin/env python3
"""Token breaker: a hard per-session token budget for an agent fleet.

Run it every 5 minutes from your scheduler. For each session it sums the
tokens used in the last 60 minutes:

  WARN  at 1.5M tokens: tell the session's channel once every 2 hours
  STOP  at 3.0M tokens: abort the session (clearing its queue and its
        sub-agents), compact it, and say why

A quiet run prints nothing. Detail goes to the log file.

This is a stripped-down version of the one I run. The 3 functions marked
ADAPT are the only parts tied to your gateway: where usage comes from, how to
stop a session, and how to post a message.

  python3 token_breaker.py --dry-run   # report what it would do, act on nothing
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

WINDOW_S = 60 * 60
WARN_TOKENS = 1_500_000
STOP_TOKENS = 3_000_000
REWARN_S = 2 * 60 * 60

HERE = Path(__file__).resolve().parent
STATE = HERE / "state" / "token_breaker.json"
LOG = HERE / "logs" / "token-breaker.log"


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    if sys.stderr.isatty():  # progress only when a human is watching
        print(msg, file=sys.stderr)


# ---- ADAPT: these 3 functions talk to your gateway ---------------------------

def usage_events(since: float) -> list[dict]:
    """Return model-call usage since `since`: [{"session", "ts", "tokens"}].

    Count input + cache reads + output. Cache reads are cheap per token but
    still burn plan quota, and they're what a runaway parent resends.
    This demo reads a JSON-lines file; mine reads each agent's transcript store.
    """
    path = HERE / "usage.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text().splitlines():
        e = json.loads(line)
        if e["ts"] >= since:
            events.append(e)
    return events


def stop_session(session: str) -> None:
    """Abort the session, clear its queued turns, cancel its sub-agents, compact it."""
    log(f"STOP {session} (wire this to your gateway's abort + compact calls)")


def notify(session: str, text: str) -> None:
    """Post to the session's own channel, or a fallback alerts channel."""
    log(f"NOTIFY {session}: {text}")

# ------------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    now = time.time()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    totals: dict[str, int] = defaultdict(int)

    for e in usage_events(now - WINDOW_S):
        # After a stop, only calls made after the stop count toward the next one.
        if e["ts"] > state.get(e["session"], {}).get("stopped_at", 0):
            totals[e["session"]] += e["tokens"]

    actions = []
    for session, used in sorted(totals.items(), key=lambda kv: -kv[1]):
        s = state.setdefault(session, {})
        if used >= STOP_TOKENS:
            actions.append(f"stop {session} at {used:,} tokens/h")
            if not args.dry_run:
                stop_session(session)
                notify(session, f"Stopped: {used:,} tokens in the last hour "
                                f"(limit {STOP_TOKENS:,}). Start a fresh conversation "
                                f"and put every lookup into 1 brief.")
                s["stopped_at"] = now
        elif used >= WARN_TOKENS and now - s.get("warned_at", 0) > REWARN_S:
            actions.append(f"warn {session} at {used:,} tokens/h")
            if not args.dry_run:
                notify(session, f"{used:,} tokens in the last hour. "
                                f"This session stops at {STOP_TOKENS:,}.")
                s["warned_at"] = now
        log(f"{session}: {used:,} tokens in window")

    if not args.dry_run:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=2))

    if actions:  # one line, and only when something happened
        print(("dry run: " if args.dry_run else "") + "; ".join(actions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
