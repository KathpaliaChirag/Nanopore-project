#!/usr/bin/env python3
"""
gap_analysis.py - where does the 50MB ESKAPE db disagree with the 103GB db?

Input : kraken2 --output / --report files from the SAME reads run on both dbs.
Output: (1) confusion between "ESKAPE species bucket / other classified /
        unclassified" for the two dbs, (2) for reads the 103GB db assigns to an
        ESKAPE species but 50MB does not (missed = sensitivity gap), the top
        taxa involved, (3) for reads 50MB assigns to an ESKAPE species but
        103GB assigns elsewhere (wrong = precision gap), what 103GB calls them.

usage: gap_analysis.py A.out A.rep B.out B.rep      (A = small db, B = big db)
"""
import sys
from collections import Counter

ESKAPE = {
    "Enterococcus faecium": 1352, "Staphylococcus aureus": 1280,
    "Klebsiella pneumoniae": 573, "Acinetobacter baumannii": 470,
    "Pseudomonas aeruginosa": 287, "Enterobacter cloacae": 550,
}


def load_report(path):
    """returns names{taxid:name}, rank{taxid:rank}, parent{taxid:parent}."""
    names, rank, parent = {}, {}, {}
    stack = []  # (depth, taxid)
    for line in open(path):
        f = line.rstrip("\n").split("\t")
        if len(f) < 6:
            continue
        tid = int(f[4])
        raw = f[5]
        depth = (len(raw) - len(raw.lstrip(" "))) // 2
        names[tid] = raw.strip()
        rank[tid] = f[3]
        while stack and stack[-1][0] >= depth:
            stack.pop()
        parent[tid] = stack[-1][1] if stack else 0
        stack.append((depth, tid))
    return names, rank, parent


def eskape_species_of(tid, parent):
    """walk up from tid; return the ESKAPE species taxid it sits under, else 0."""
    seen = 0
    while tid and seen < 64:
        if tid in ESKAPE.values():
            return tid
        tid = parent.get(tid, 0)
        seen += 1
    return 0


def load_calls(path):
    calls = []
    for line in open(path):
        f = line.split("\t", 4)
        calls.append(int(f[2]) if f[0] == "C" else 0)
    return calls


def bucket(tid, parent):
    if tid == 0:
        return "unclassified"
    sp = eskape_species_of(tid, parent)
    return ("ESKAPE:" + str(sp)) if sp else "other"


def main():
    a_out, a_rep, b_out, b_rep = sys.argv[1:5]
    an, ar, ap = load_report(a_rep)
    bn, br, bp = load_report(b_rep)
    a, b = load_calls(a_out), load_calls(b_out)
    assert len(a) == len(b), (len(a), len(b))
    n = len(a)
    inv = {v: k for k, v in ESKAPE.items()}

    def label(bk):
        if bk.startswith("ESKAPE:"):
            return inv[int(bk.split(":")[1])]
        return bk

    conf = Counter()
    missed = Counter()   # big says ESKAPE sp X, small says something else
    wrong = Counter()    # small says ESKAPE sp X, big says something else
    for ta, tb in zip(a, b):
        ba, bb = bucket(ta, ap), bucket(tb, bp)
        conf[(label(ba), label(bb))] += 1
        if bb.startswith("ESKAPE") and ba != bb:
            missed[(label(bb), label(ba), bn.get(tb, str(tb)))] += 1
        if ba.startswith("ESKAPE") and ba != bb:
            wrong[(label(ba), label(bb), bn.get(tb, "unclassified" if tb == 0 else str(tb)))] += 1

    print(f"reads: {n}")
    print("\n== bucket totals ==")
    ca = Counter(label(bucket(t, ap)) for t in a)
    cb = Counter(label(bucket(t, bp)) for t in b)
    print(f"{'bucket':32s} {'50MB':>9s} {'103GB':>9s}")
    for k in sorted(set(ca) | set(cb)):
        print(f"{k:32s} {ca[k]:9d} {cb[k]:9d}")

    agree = sum(v for (x, y), v in conf.items() if x == y)
    print(f"\nreads where both dbs agree on the bucket: {agree} ({100*agree/n:.2f}%)")

    print("\n== MISSED: 103GB says ESKAPE species, 50MB says something else ==")
    tot = sum(missed.values())
    print(f"total {tot} reads ({100*tot/n:.2f}% of all)")
    for (sp, what50, name103), v in missed.most_common(15):
        print(f"{v:7d}  103GB: {name103[:38]:38s} -> 50MB: {what50}")

    print("\n== WRONG: 50MB says ESKAPE species, 103GB says something else ==")
    tot = sum(wrong.values())
    print(f"total {tot} reads ({100*tot/n:.2f}% of all)")
    for (sp, what103, name103), v in wrong.most_common(20):
        print(f"{v:7d}  50MB: {sp:24s} -> 103GB: {name103[:44]}")


if __name__ == "__main__":
    main()
