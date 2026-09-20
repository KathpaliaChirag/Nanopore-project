"""
Builds the interactive results page (cache_simulation/report/*.html) from the committed CSVs.

Every number that appears in a chart or table is read from cache_simulation/measurements/ here,
never typed by hand, so the page can be regenerated after any new run:
    python cache_simulation/scripts/build_report.py

Inputs : report/template_head.html, template_body_*.html, app_*.js  (page source, edited by hand)
Outputs: report/cache_simulation_report.html            (Artifact format: no doctype/head/body tags)
         report/cache_simulation_report_standalone.html (same page wrapped so it opens in a browser)
"""
import csv, json, os, glob

ROOT = os.path.join(os.path.dirname(__file__), "..")
MEAS = os.path.join(ROOT, "measurements")
REP = os.path.join(ROOT, "report")


def rows(name):
    """Read one CSV; numeric-looking cells become floats (blank cells become None)."""
    out = []
    with open(os.path.join(MEAS, name), newline="") as f:
        for r in csv.DictReader(f):
            d = {}
            for k, v in r.items():
                v = (v or "").strip()
                if v == "":
                    d[k] = None
                else:
                    try:
                        d[k] = float(v)
                    except ValueError:
                        d[k] = v
            out.append(d)
    return out


def tag(rs, **kw):
    for r in rs:
        r.update(kw)
    return rs


fair = rows("final_fair_batch_2026-09-09_5variant_all_db.csv")
assoc10 = rows("associativity_sweep_2026-09-08_summary.csv")
hwsize = rows("hwsize_comparison_2026-09-09.csv")
r2000 = rows("2000reads_live_summary_2026-09-09.csv")
laptop = rows("laptop_sweep_2026-09-15.csv")
long_s0 = rows("longread_scaling_S0_2026-09-19.csv")
long_4w = rows("longread_scaling_4way_2026-09-19.csv")
hwassoc50 = rows("hw_assoc_sweep_2026-09-14.csv")
hwassoc_big = rows("hw_assoc_sweep_bigdb_2026-09-15.csv")
flat = rows("flatl3_comparison_2026-09-15.csv")

# Size sweep: 50MB and 103GB were run at 10 reads (tiny_10reads), 8GB and 16GB at 50 reads (50reads.fastq).
sizes = []
sizes += tag(rows("size_sweep_50mb_2026-09-15.csv"), reads=10)
sizes += tag([r for r in rows("cache_size_sweep_8gb16gb_2026-09-15.csv") if r["db"] == "8gb"], reads=50)
sizes += tag([r for r in rows("cache_size_sweep_8gb16gb_2026-09-15.csv") if r["db"] == "16gb"], reads=50)
sizes += tag(rows("size_sweep_103gb_2026-09-15.csv"), reads=10)

# Inventory of every measurement file (row counts are computed, not typed).
inventory = []
total_rows = 0
for p in sorted(glob.glob(os.path.join(MEAS, "*.csv"))):
    n = len(rows(os.path.basename(p)))
    inventory.append({"file": os.path.basename(p), "rows": n})
    total_rows += n

DATA = {
    "fair": fair, "assoc10": assoc10, "hwsize": hwsize, "r2000": r2000, "laptop": laptop,
    "longS0": long_s0, "long4": long_4w, "hwassoc50": hwassoc50, "hwassocBig": hwassoc_big,
    "flat": flat, "sizes": sizes, "inventory": inventory, "totalRows": total_rows,
}


def read(name):
    with open(os.path.join(REP, name), encoding="utf-8") as f:
        return f.read()


head = read("template_head.html")
body = "\n".join(read(n) for n in sorted(os.listdir(REP)) if n.startswith("template_body_"))
js = "\n".join(read(n) for n in sorted(os.listdir(REP)) if n.startswith("app_") and n.endswith(".js"))

data_js = "const DATA = " + json.dumps(DATA, separators=(",", ":")) + ";"
page = (
    head + "\n" + body + "\n"
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>\n'
    "<script>\n" + data_js + "\n" + js + "\n</script>\n"
)

with open(os.path.join(REP, "cache_simulation_report.html"), "w", encoding="utf-8") as f:
    f.write(page)
with open(os.path.join(REP, "cache_simulation_report_standalone.html"), "w", encoding="utf-8") as f:
    f.write('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>\n'
            + page + "</body></html>\n")
print("built", len(page) // 1024, "KB;", total_rows, "measurement rows across", len(inventory), "CSVs")
