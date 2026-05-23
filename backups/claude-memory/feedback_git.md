---
name: feedback_git
description: Never push to main branch in KathpaliaChirag/Nanopore-project repo — always use hobbbit branch
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9a86dc94-8e0b-4889-829e-ce6613e7ca92
---

Never push to `main` in the repo `https://github.com/KathpaliaChirag/Nanopore-project.git`. Always work on and push to the `hobbbit` branch.

**Why:** User is a collaborator (not owner) and wants all personal work isolated to their own branch.

**How to apply:** Any time git push or commit work is done in the Nanopore-project repo, verify the current branch is `hobbbit` before pushing. If ever on `main`, switch to `hobbbit` first.
