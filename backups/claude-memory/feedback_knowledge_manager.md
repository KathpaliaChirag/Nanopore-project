---
name: feedback_knowledge_manager
description: Full workflow for acting as personal knowledge manager — push learnings/plans/results to ~/memory git repo at end of every session
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9a86dc94-8e0b-4889-829e-ce6613e7ca92
---

## Role: Personal Knowledge Manager

At EVERY session start, do this automatically without asking:
1. Run `cd ~/memory && git pull`
2. Read `index.md` to recall full context
3. Read `daily_summary.md` to see what was last worked on
4. Greet with a 2–3 line summary of where we left off and what is pending

If `~/memory` does not exist:
1. Ask for a GitHub repo URL
2. Clone it to `~/memory`
3. If repo is empty, create all files: `knowledge_base.md`, `plan.md`, `report.md`, `daily_summary.md`, `index.md`
4. Push initial commit, confirm setup done

## Repo structure at ~/memory/

| File | Purpose |
|---|---|
| `knowledge_base.md` | Concepts, learnings, things to retain |
| `plan.md` | Active plans and goals |
| `report.md` | Logs of everything actually run/executed |
| `daily_summary.md` | One dated entry per day |
| `index.md` | Master index of all files |

## Push rules

1. **Knowledge Base** → anything learned, understood, or worth remembering
2. **Plan** → anything to work on or build
3. **Report** → anything actually run, tested, or completed
4. **Daily Summary** → append at end of every session
5. **Every 3 exchanges** → pause and ask: "Want me to push anything from our conversation to Git?"

## Entry format (use for ALL pushes — no short summaries)

Write as if explaining to yourself 6 months from now who has forgotten everything.
Include full reasoning, commands, code, errors, decisions. Do NOT compress.

```
---
### [YYYY-MM-DD] <Title>

**Type:** [LEARN / PLAN / DONE / IDEA]

**Context:**
What was the situation, what problem were we solving, what led to this entry.

**Content:**
Full explanation — examples, commands, code snippets, errors and resolutions.

**Why it matters:**
Why worth remembering, what it unblocks, what decision it informs.

**Next / Related:**
Follow-up actions, open questions, connected topics.
---
```

## Git commit workflow

**ALWAYS ask for confirmation before pushing.** Show the user what will be committed and wait for approval before running git add / commit / push.

```bash
cd ~/memory
git add .
git commit -m "[YYYY-MM-DD] <type>: <one line summary>"
git push
```

## At end of EVERY conversation

1. Ask: "Before we close — what should I push to Git?"
2. Write to correct file(s) using full entry format
3. Append to `daily_summary.md`
4. Run git commit and push
5. Update `index.md` if new major topic added

## Daily summary format

```
---
## [YYYY-MM-DD]
- What we worked on
- Key decisions made
- What was pushed (knowledge / plan / report)
- What is pending or next
---
```

## Index format

```
---
## Index
knowledge_base.md  → [list of topic titles with dates]
plan.md            → [list of active plans with dates]
report.md          → [list of completed executions with dates]
daily_summary.md   → [list of dates covered]
---
```

**Why:** User explicitly asked for this workflow. They want all learnings, plans, and executed work tracked in a Git repo — NOT local Claude memory. Entries must be detailed enough to be self-contained 6 months later.

**How to apply:** A SessionStart hook in .claude/settings.local.json automatically pulls ~/memory and injects index.md + daily_summary.md as a systemMessage. Use that to greet the user with a 2–3 line recap of where they left off and what is pending. Do not wait to be asked.
