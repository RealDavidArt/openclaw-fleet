#!/usr/bin/env python3
"""The deterministic half of the stale-deals skill.

Fetching, filtering and sorting live here, so they run the same way every
time and can be tested without a model. The agent only writes next steps.
Uses made-up data; swap `load_deals` for your CRM call.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

STALE_DAYS = 14
OUT = Path(__file__).resolve().parent / "out" / "stale-deals.json"


def load_deals() -> list[dict]:
    today = date.today()
    return [
        {"name": "Acme Logistics expansion", "last_activity": today - timedelta(days=21),
         "note": "Champion asked for a security review packet"},
        {"name": "Globex renewal", "last_activity": today - timedelta(days=3),
         "note": "Pricing call booked"},
        {"name": "Initech pilot", "last_activity": today - timedelta(days=17),
         "note": "Pilot results sent, no reply"},
    ]


def main() -> None:
    today = date.today()
    stale = sorted(
        ({"name": d["name"], "days_idle": (today - d["last_activity"]).days, "note": d["note"]}
         for d in load_deals() if (today - d["last_activity"]).days >= STALE_DAYS),
        key=lambda d: -d["days_idle"],
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(stale, indent=2))
    print(f"{len(stale)} stale" + (f", oldest {stale[0]['days_idle']} days" if stale else ""))


if __name__ == "__main__":
    main()
