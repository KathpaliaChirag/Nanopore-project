# Memory Index

- [User Profile](user_profile.md) — Chirag Suthar, summer research intern, holds hobbbit branch (teammate Chirag K holds main)
- [Nanopore Project Overview](project_nanopore.md) — Project goals, pipeline (POD-5 → Dorado → Kraken-2), ESKAPE pathogens, performance research
- [Meeting Minutes Summary](project_meetings.md) — Key decisions and action items from meetings 1–3 (May 2026)
- [Git Rule: Never push to main](feedback_git.md) — Always use `hobbbit` branch in KathpaliaChirag/Nanopore-project
- [Knowledge Manager Workflow](feedback_knowledge_manager.md) — Full rules for ~/memory git repo, push format, session start/end rituals
- [Branch Diff Check on Start](feedback_branch_diff_check.md) — SessionStart hook auto-checks main vs hobbbit diff; say "go" to merge changes
- [Tool Paths](reference_tool_paths.md) — Dorado at ~/dorado/dorado-1.4.0-linux-x64/bin/dorado; nsys and ncu on PATH
- [Local Cache Directories](reference_local_cache.md) — ~/.nsys-symbols for CUDA symbol cache; first run slow, subsequent runs instant
- [Session Hook: Cache Summary](feedback_session_hook_caches.md) — Always update SessionStart hook in ~/.claude/settings.json when new dirs/caches are created
