import os, re, glob

lib_dir = "/home/chira/eskape_db/library/added"
seqid2taxid_path = "/home/chira/eskape_db/seqid2taxid.map"

entries = []

source_prefixes = ('e_faecium', 's_aureus', 'k_pneumoniae', 'a_baumannii', 'p_aeruginosa', 'e_cloacae')

for fpath in glob.glob(os.path.join(lib_dir, "*.fna")):
    fname = os.path.basename(fpath)
    if any(fname.startswith(p) for p in source_prefixes):
        continue
    with open(fpath) as f:
        for line in f:
            if line.startswith('>'):
                m = re.search(r'\|kraken:taxid\|(\d+)', line)
                if m:
                    taxid = m.group(1)
                    accession = line[1:].split()[0]
                    entries.append(f"{accession}\t{taxid}")

with open(seqid2taxid_path, 'w') as f:
    f.write('\n'.join(entries) + '\n')

print(f"Written {len(entries)} entries to seqid2taxid.map")
for e in entries:
    print(e)
