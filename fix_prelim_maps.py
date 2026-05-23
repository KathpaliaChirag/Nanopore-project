import os, re, glob

lib_dir = "/home/chira/eskape_db/library/added"
seqid2taxid_path = "/home/chira/eskape_db/seqid2taxid.map"

# Load the seqid -> taxid mapping we already built
seqid_to_taxid = {}
with open(seqid2taxid_path) as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 2:
            acc_v = parts[0]
            taxid = parts[1]
            seqid_to_taxid[acc_v] = taxid
            # also store without version (NC_008710.1 -> NC_008710)
            acc = acc_v.rsplit('.', 1)[0]
            seqid_to_taxid[acc] = taxid

print(f"Loaded {len(seqid_to_taxid)//2} seqid->taxid mappings")

# Fix every prelim_map file in library/added/
fixed = 0
for map_path in glob.glob(os.path.join(lib_dir, "prelim_map*.txt")):
    lines_out = []
    with open(map_path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) == 3 and parts[0] == 'ACCNUM':
                acc_v = parts[1]
                acc   = parts[2]
                taxid = seqid_to_taxid.get(acc_v) or seqid_to_taxid.get(acc)
                if taxid:
                    lines_out.append(f"TAXID\t{taxid}\t{acc_v}\n")
                    fixed += 1
                else:
                    lines_out.append(line)
            else:
                lines_out.append(line)
    with open(map_path, 'w') as f:
        f.writelines(lines_out)
    print(f"Fixed {os.path.basename(map_path)}")

print(f"\nTotal entries fixed: {fixed}")
print("Now re-run: ~/kraken2-build/kraken2-build --build --db ~/eskape_db")
