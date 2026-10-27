# cycle 3, R3 vote, a4_hw

**AGREE**: both lists are unchanged from cycle 2.

factual fixes (non-blocking, class splits):
1. **H1-wsl2.** "shuts down after 60 s idle": `vmIdleTimeout` is marked "Only available on Windows 11" in the same table [external: microsoft wsl-config]. on windows 10 the idle shutdown is [UNCLEAR]. the 50% memory default and `autoMemoryReclaim` = `dropCache` have no such mark.
2. **H4-hpc slot.** "page cache is charged to the job" holds only where the cluster runs slurm on cgroup v2. that was my [guess]. the slurm page says nothing about page cache [external: slurm cgroup.conf]. tag it "[guess: cgroup v2 clusters]".
