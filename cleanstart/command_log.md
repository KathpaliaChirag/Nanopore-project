# cleanstart command log

every command actually run, in order: why, then result. same pattern as cache_simulation/command_log.md.

---

### [0] 2026-09-19 - folder created on this machine

created `cleanstart/` in the repo root (README.md + this file). Luna copy: `~/cleanstart` (created by hand, see step 1).

---

### [1] 2026-09-19 - Luna inventory check + create ~/cleanstart

```bash
ssh -i ~/.ssh/luna_claude student@luna.cse.iitd.ac.in 'mkdir -p ~/cleanstart && ls -la <S0 classify> <luna.cfg> <laptop.cfg>; ls -d ~/chirag_K/AccuracyDrift/databases/*/; find ~ -name "*.pod5" -size +1G'
```

**why:** confirm S0 binary, hardware configs, databases, and any existing large pod5 exist before choosing the fixed baseline. ssh access to Luna works from this machine (key `~/.ssh/luna_claude`), older notes saying it does not are out of date.

**result:**
- S0 classify exists: `~/chirag_K/tools/kraken2-src-baseline/src/classify` (264 KB, built Aug 3)
- `luna.cfg` (Sep 8) and `laptop.cfg` (Sep 15) exist in `~/cache_simulation/snipersim/config/`
- databases: standard_8gb, standard_16gb, pluspf_103gb, sample_targeted, eskape_genomes, plus centrifuge/centrifuger/metabuli ones
- pod5 files over 1 GB already on Luna: `~/chirag_K/data/pod5/fbe/FBE01990_24778b97_03e50f91_{0,3,5,6,7,9,10,11,13,14}.pod5` (at least 10, so no need to fetch one)
- `~/cleanstart` created, empty
