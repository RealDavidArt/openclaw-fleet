# What broke

Each entry is a real incident from my fleet, with the cause and the rule it left behind. Dates are 2026.

## 1. 8.3M tokens in 1 hour (Nov 3)

One sales conversation used 8.3M tokens in 99 model calls over about an hour. That used up the whole 5-hour allowance on my ChatGPT plan, plus 14% of the week. A normal session-hour is about 33K tokens.

The sales lead had spawned its executor sub-agent about 15 times, one lookup at a time. Each time a child finished, the gateway woke the parent with a fresh run. The prompt for that run missed the cache because it included a changing list of active sub-agents. So every wake resent 50K to 180K tokens at full price. 40 of the 99 calls accounted for 96% of the uncached input. The executor's persona also told it to refuse to summarize, so full email bodies landed in the chat and grew it from 25K to 178K tokens.

The rules now:

- One delegation per question. Every lookup the question needs goes into 1 brief.
- Sub-agent results stay under 4,000 characters. Anything bigger goes to a file, and the agent returns the path.
- A breaker runs every 5 minutes. It warns a session at 1.5M tokens in an hour and stops it at 3M, cancelling its queue and its sub-agents. Rules in a persona file are advice; the breaker is enforcement. See [examples/token_breaker.py](../examples/token_breaker.py).

## 2. Heartbeats were 78% of token spend (fixed Sep 23)

All 17 agents I had then ran a background heartbeat every 2 hours. I assumed each heartbeat started clean. It didn't: each one ran inside that agent's main session and replayed its whole history, so a routine check sent a 166K to 189K token prompt. Heartbeats came to 113M of my 145M tokens a week.

The fix was 2 settings. Heartbeats now run in their own isolated session, and only 1 agent runs them instead of 17. Prompts dropped to 7K to 25K tokens.

It also explained a ghost alert. A heartbeat kept warning that a deleted skill was missing, every 2 hours, after I'd removed the instruction from the heartbeat file. The instruction lived on in the session history, so editing the file changed nothing. Archiving the session and restarting the gateway fixed it.

Scheduled jobs behave the same way: an "isolated" job gets 1 persistent session per job, not 1 per run. Edit a skill file and the agent may keep following the old version it already read.

The rule: put behavior gates in scripts, which run fresh every time, and keep heartbeat prompts short and self-contained.

## 3. The agent reported a failure that never happened (Oct 15)

My LinkedIn drafting job reported that the exec allowlist had denied its script. That was false. The agent had launched the script correctly, then ended its turn after 58 seconds against a pipeline that needs 3 to 8 minutes, and made up a plausible reason. The script kept running orphaned and saved the draft. Nobody posted it, because the turn had already ended.

The fabricated cause cost more than the failure. It sent me auditing permission config for a bug that didn't exist.

The same pattern runs the other way: an agent's turn ending "ok" is the agent's claim, not proof. Since Oct 20 every model stage in my pipelines declares the evidence it must produce, such as a file written during the run or a pattern in its output. A stage that ends ok without the evidence is marked unverified, counts as a failure, and its dependents don't run. Backtested against 21 good runs with 0 false alarms. See [examples/pipeline_expect.py](../examples/pipeline_expect.py).

## 4. An upgrade outage with 5 stacked causes (Aug 6)

After an OpenClaw upgrade the gateway wouldn't start. Each fix revealed the next problem:

1. The new version needed a newer Node.
2. Killing the gateway during its first boot left a migration lock that took about 10 minutes to expire.
3. A leftover state directory from the project's old name blocked migrations until I replaced it with a symlink.
4. Model config validation got stricter. My OAuth-only OpenAI provider had no API key field, so the whole model catalog failed to load. A placeholder value fixed it; real auth still goes through OAuth.
5. Fallback stopped at hard errors. With OpenAI rate-capped and a dead Google key, agents errored out instead of falling through to Mistral further down the chain.

The fifth one changed how I treat fallback chains. I test the whole chain, not just the primary, and a provider with a known-dead key moves to the bottom until it's fixed.

The thing that made all 5 hard to find: the launch agent sent gateway stderr to /dev/null. It writes to a log file now.

## 5. A 181-byte file that stopped every scheduled job (Sep to Nov)

After another upgrade, a tiny stub `exec-approvals.json` kept reappearing. While it existed, every scheduled job and heartbeat failed a legacy-config check, and the Discord connection crash-looped. One stretch lasted 16 hours before I caught it.

It has come back 4 times. The last 2 appeared within a minute of the Mac rebooting, which points at the companion app writing it at login. Discord doesn't replay messages sent while the bot is disconnected, so anything I sent in that window was lost.

The rule: when many jobs fail at once, check for that file first. The fix is quick: move the file, run `openclaw doctor --fix`, and restart safely. The lasting fix, stopping the app from writing it, is still open.

## 6. A firehose that trained me to ignore alerts (Jul 13)

My automation log channel filled with 50-line messages on every successful run: per-item progress, page counts, raw JSON. Nothing was an error. The skills told the agent to return the script's stdout verbatim, and the scripts narrated everything. It trained me to ignore the channel, which is the worst outcome for an alert channel.

The rule: a script prints exactly 1 line to stdout, with counts and errors. Detail goes to a log file. Progress goes to stderr only when a human is watching a terminal. A quiet run prints nothing, and a quiet job doesn't post.
