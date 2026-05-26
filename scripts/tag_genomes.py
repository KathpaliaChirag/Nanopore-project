import gzip

taxids = {
    "e_faecium.fna.gz":    1352,
    "s_aureus.fna.gz":     1280,
    "k_pneumoniae.fna.gz":  573,
    "a_baumannii.fna.gz":   470,
    "p_aeruginosa.fna.gz":  287,
    "e_cloacae.fna.gz":     550,
}

for fname, taxid in taxids.items():
    inpath = f"/home/chira/eskape_db/library/added/{fname}"
    outpath = inpath.replace(".fna.gz", "_tagged.fna")
    with gzip.open(inpath, "rt") as fin, open(outpath, "w") as fout:
        for line in fin:
            if line.startswith(">"):
                line = line.rstrip() + f"|kraken:taxid|{taxid}\n"
            fout.write(line)
    print(f"Tagged {fname} -> taxid {taxid}")
