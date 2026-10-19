#!/usr/bin/env python3
"""Does MurmurHash3 earn its place? Backs FLOW.md §7.

Compares raw minimizer vs hashed minimizer on three properties:
  (a) slot uniformity   -- value % capacity
  (b) fingerprint power -- distinct values in the top 26 bits
  (c) the -M gate       -- fraction skipped below the threshold

Input: output of scripts/dump_minimizers.cc  ("<minimizer> <hash>" per line).
"""
import collections, math, sys

CAP = 12_000_000
THRESH = 0xC4EC4EC4EC4EC000          # eskape_big_M12000000, 76.92% skip target

def main(path):
    d = {}
    n = 0
    with open(path) as f:
        for line in f:
            a, b = line.split()
            d[int(a)] = int(b)
            n += 1
    K = len(d)
    print(f"{n:,} minimizer occurrences, {K:,} distinct\n")

    exp_occ = CAP * (1 - (1 - 1 / CAP) ** K)
    print(f"(a) SLOT = value % {CAP:,}")
    print(f"    theoretical slots occupied if perfectly uniform: {exp_occ:,.0f}")
    for label, vals in (("raw minimizer", d.keys()), ("MurmurHash3", d.values())):
        c = collections.Counter(v % CAP for v in vals)
        occ, mx = len(c), max(c.values())
        e = K / CAP
        chi = sum((k - e) ** 2 / e for k in c.values()) + (CAP - occ) * e
        print(f"    {label:14} slots {occ:>9,} ({occ/exp_occ:>6.1%} of ideal)"
              f"  max {mx:>3}/slot  chi2/dof {chi/(CAP-1):>5.2f}")

    print(f"\n(b) FINGERPRINT = top 26 bits")
    fr = len(set(v >> 36 for v in d))              # raw is 62-bit
    fh = len(set(v >> 38 for v in d.values()))     # hash is 64-bit
    print(f"    raw minimizer {fr:>10,} distinct  ({fr/K:>6.1%} of keys separable)")
    print(f"    MurmurHash3   {fh:>10,} distinct  ({fh/K:>6.1%} of keys separable)")

    print(f"\n(c) -M GATE: skip if value < 0x{THRESH:x}  (target 76.92%)")
    print(f"    max possible raw minimizer (2^62) = {2**62:>26,}")
    print(f"    threshold                         = {THRESH:>26,}"
          f"   ({THRESH/2**62:.2f}x larger)")
    sr = sum(1 for v in d if v < THRESH)
    sh = sum(1 for v in d.values() if v < THRESH)
    print(f"    gate on raw minimizer: skips {sr/K:>7.2%}  -> unusable")
    print(f"    gate on hash         : skips {sh/K:>7.2%}  -> ok")

    print("\n(d) slot/fingerprint independence (low 26 vs high 26 bits)")
    for label, vals in (("raw minimizer", list(d)), ("MurmurHash3", list(d.values()))):
        s = vals[:200_000]
        lo = [v & 0x3FFFFFF for v in s]
        hi = [(v >> 38) & 0x3FFFFFF for v in s]
        ml, mh = sum(lo) / len(lo), sum(hi) / len(hi)
        num = sum((a - ml) * (b - mh) for a, b in zip(lo, hi))
        da = math.sqrt(sum((a - ml) ** 2 for a in lo))
        db = math.sqrt(sum((b - mh) ** 2 for b in hi))
        print(f"    {label:14} r = {num/(da*db):+.4f}")
    print("    -> near zero for BOTH; independence was never the benefit.")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "mm.txt")
