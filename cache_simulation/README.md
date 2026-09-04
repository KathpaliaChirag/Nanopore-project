# cache_simulation

started 2026-09-04. this is where the Sniper-based cache simulator work lives - the pivot away from
real-hardware Luna/Orion profiling for the associativity/eviction case study, decided the same day
sir asked the team to go simulator-based instead (see project memory for the full reasoning).

tool choice: **Sniper**, re-locked after a same-day flip to TEJAS-as-default got reverted back.
TEJAS may still get built in parallel for cross-validation - not decided yet.

mirrors a matching folder on Luna, where the actual build/run work happens (this machine has no
direct Luna access - every Luna step is a command handed over and run by hand, then logged here).

- `command_log.md` - every command actually run on Luna, in order, with why + result. same pattern
  as `plan_paper/command_log.md`.
