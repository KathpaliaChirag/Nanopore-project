p = "/home/student/e1/sn/src0/src/classify.cc"
s = open(p).read()
bad = '"K2 block bases = %zu' + chr(10) + '", v);'
good = '"K2 block bases = %zu' + chr(92) + 'n", v);'
if s.count(bad) != 1:
    print("FIX FAIL", s.count(bad)); raise SystemExit(1)
open(p, "w").write(s.replace(bad, good)); print("FIX OK")
