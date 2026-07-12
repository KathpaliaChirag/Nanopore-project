---
name: reference-local-cache
description: Local cache directories created for tools — what they store and why
metadata: 
  node_type: memory
  type: reference
  originSessionId: f1df5c51-0ba3-417b-8e83-9adb962831ab
---

## nsys symbol cache

- **Path:** `~/.nsys-symbols` (`/home/hobbbit31/.nsys-symbols`)
- **Created:** 2026-05-21
- **Purpose:** Caches CUDA debug symbol files downloaded from NVIDIA's public symbol servers so nsys only downloads them once. Without this, nsys hangs indefinitely after each profiling run waiting for symbols.
- **First run:** slow (5–15 min download after Dorado finishes) — let it sit, don't Ctrl-C
- **Subsequent runs:** instant, uses cached symbols
- **Flag to activate:** `--symbol-source public-symbol-servers,elf` in nsys profile command
