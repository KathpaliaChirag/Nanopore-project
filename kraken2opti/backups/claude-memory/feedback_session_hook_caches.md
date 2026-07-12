---
name: feedback-session-hook-caches
description: Always update the SessionStart hook in ~/.claude/settings.json when new project directories or caches are created
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f1df5c51-0ba3-417b-8e83-9adb962831ab
---

Whenever a new directory, cache, or results folder is created for this project, update the SessionStart hook command in `~/.claude/settings.json` to include it in the printed summary.

**Why:** User wants every session to display all local directories/caches so nothing is forgotten across sessions.

**How to apply:** After creating any new directory (results folder, build output, tool cache, data directory), immediately edit the `command` field under `hooks.SessionStart` in `~/.claude/settings.json` to add a new `echo` line for it. Mark `(NOT YET CREATED)` for planned but not yet created dirs.

**Current entries (as of 2026-05-21):**
- `~/.nsys-symbols` — CUDA symbol cache for nsys
- `~/results/nsight/` — nsys profiling output
- `~/kraken2-build/` — Kraken-2 -pg build (NOT YET CREATED)
