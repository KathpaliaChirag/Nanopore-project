---
name: feedback-branch-diff-check
description: "On every session start in this project, check and report content differences between origin/main and origin/hobbbit branches"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2ee01d3d-000d-4a7d-a07c-81302861a228
---

At the start of every session in /home/hobbbit31/Desktop/summer_project, automatically check if origin/main and origin/hobbbit have diverged.

**Why:** The two branches diverged (e.g. plan.md WSL2 perf section updated on main but not hobbbit). User wants to catch these silently each session rather than discovering them manually.

**How to apply:** A SessionStart hook in .claude/settings.local.json handles this automatically — it runs `git fetch` + `git diff origin/main origin/hobbbit` and injects the result as a systemMessage. If a diff is shown at session start, report it to the user. If they say "go", merge the main changes into hobbbit.
