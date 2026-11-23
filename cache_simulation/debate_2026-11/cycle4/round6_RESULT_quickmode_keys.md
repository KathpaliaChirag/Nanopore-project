# a bug in my own lazy report-key shortcut, found by an implementer's small test (luna, 2026-11-23)

the "lazy keys" version of the HLL guard (round 5 of cycle 3: insert the empty per-taxon report entries once per read from hit_counts instead of once per hit group) is NOT byte-identical to stock in --quick mode on the capped databases: the plain report of --quick on standard_8gb has the same lines in a different order for count-1 rows. implementer I5 saw it in its small-input matrix and noticed the unchanged bin_pread2 shows it too.

bisect (80,000 FASTQ lines, standard_8gb, --quick, 8 threads, vs stock S19): hll (no keys): report differs; serial: differs; final (per-hit key insertion, the version before the lazy shortcut): IDENTICAL; final2 (lazy keys): differs; pread2: differs. so the lazy shortcut is the cause and per-hit insertion is exact.

why the validation matrix missed it: it ran --quick only on the 50 MB database (sample_targeted), where the difference does not show; the capped databases (8 GB, 16 GB) were only in a short core subset without --quick.

fix (code/quickmode_keys_fix.diff, built as impl_out2 / bin_out2): in --quick mode keep stock's per-hit key creation (`else if (opts.quick_mode) (void) curr_taxon_counts[taxon];` in the resolve loop) and skip the lazy hit_counts loop when quick mode is on. normal mode keeps the cheap lazy path.

verification of the fix (standard_8gb and standard_16gb, 80,000 FASTQ lines, 8 threads, vs stock): --quick, --quick --minimum-hit-groups 3, plain, --report-zero-counts: per-read output identical and report BYTE-identical in all eight combinations.

lesson: a shortcut that changes WHEN a side effect (map key creation) happens needs a test in every mode that moves the side effect (quick mode early exit here). the matrix should run --quick, --confidence and --minimum-hit-groups on a capped database too (added to the todo for validate_matrix.sh).
