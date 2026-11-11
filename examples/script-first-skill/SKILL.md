---
name: stale-deals
description: Daily list of open deals with no activity in 14+ days, with 1 suggested next step each.
---

# Stale deals

1. Run the script. It does all the data work and prints JSON to a file, plus 1 summary line.

   ```
   cd examples/script-first-skill && python3 stale_deals.py
   ```

2. If the summary line says `0 stale`, stop. Post nothing.

3. Otherwise read `out/stale-deals.json`. For each deal, write 1 next step based on the last activity note. This is the only part that needs judgment.

4. Post the list. 1 line per deal: name, days idle, next step.
