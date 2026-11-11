# Patterns

The rules every agent, skill and script in the fleet follows. Most came out of an incident in [what-broke.md](what-broke.md).

## Script first

Deterministic work goes in a script. The skill file becomes a 1-line exec, and the model only handles what needs judgment: reading a transcript, ranking deals, drafting a message.

Scripts make the job testable without a model, they run the same way every time, and they're immune to stale session history (incident 2). They also cost a fraction of the tokens.

The inverse matters too. Wrapping judgment in a script, with a regex where a model should read the text, produces confident wrong answers. Keep each kind of work where it belongs.

An example is in [examples/script-first-skill/](../examples/script-first-skill/).

## One line out

A scheduled script prints 1 human-readable line to stdout, for example `transcripts: 19 processed, 0 new claims, 19 skipped`. Detail goes to `logs/<job>.log`. A run where nothing changed prints nothing, and a job with nothing to say doesn't post.

Exit codes stay meaningful. The scheduler treats non-zero as failure, so cleaning up output must never change them.

## Evidence over claims

A model stage in a pipeline declares what it will leave behind:

```json
{
  "name": "morning_brief",
  "agent": "admin",
  "expect": [
    {"file": "outputs/brief-{date}.md", "fresh_minutes": 30},
    {"stdout_not_regex": "(?i)unable to|failed to"}
  ]
}
```

If the turn ends ok but the evidence is missing, the stage is unverified. It counts as a failure, its output isn't relayed, and stages that depend on it are skipped. See [examples/pipeline_expect.py](../examples/pipeline_expect.py).

## Token budget

- Cost is conversation size times number of calls, because every call resends the whole conversation.
- 1 delegation per question, with every lookup in 1 brief.
- More than 2 spawns or about 10 model calls for 1 request: the agent stops and asks before continuing.
- Never pull whole emails, transcripts or exports into the chat. Save to a file, then read excerpts of 40 lines at most.
- The breaker in [examples/token_breaker.py](../examples/token_breaker.py) enforces all of this.

## Models

Every agent uses the same provider order, with no exceptions:

1. OpenAI, through my ChatGPT subscription's OAuth sign-in rather than a pay-per-token API key
2. Anthropic
3. Mistral
4. Google

Agents are tiered by the job across 3 sizes of model. The strongest goes to my override agent, the sales lead and the LinkedIn writer, where judgment and voice matter. Security, health and 1 business lead get the middle tier. Executors, researchers and even the chief of staff get the small one, because running scripts and routing requests don't need the big model.

Two rules came from failures. A scheduled job never sets its own model, because switching models inside a live session throws an error in my gateway version, so jobs inherit from the agent. And I test the whole fallback chain after every upgrade, because my gateway stops at a hard error instead of falling through (incident 4).

Upgrades can also move models without telling you. After 1 upgrade, scheduled jobs started taking their model from the sub-agent setting instead of the agent's primary. The sales lead's scheduled jobs dropped to the small model, and customer follow-up emails were drafted on it before I noticed. Every agent above the small tier now sets both values, and I check which model a job actually used after each upgrade.

## Taste preferences

Every agent that writes for a customer or the public reads a table of writing rules before drafting and checks its draft against them before handing it back. Each rule came from a draft I rejected, and each one records when the opposite is right, so rules don't harden into caricature. Details in [taste-preferences](https://github.com/RealDavidArt/taste-preferences).

## Secrets

API keys live in a gitignored `.env`. Agents and scripts read from it, never from hardcoded values.

My private config repo learned this late. Early commits included per-agent auth profile files and a dashboard with a hardcoded token, from before those paths were gitignored. Ignoring a file later doesn't remove it from history. I rotated what was exposed, and it's why this repo is a fresh write-up instead of my working repo with the secrets scrubbed.

Before anything goes public:

```bash
gitleaks detect --source . --log-opts="--all"
```

## Memory

The agents lose everything when a session ends unless it's written down. Daily notes go to a dated file per agent. Durable facts go to a Supabase-backed store the agents can search in under a second, and a nightly job compiles them into a summary file that agents load in direct sessions with me. After a notable run only, an agent appends 3 lines to its own memory file: date and summary, context, and the rule it learned. Padding that file makes it worse, so "nothing notable" is the default.
