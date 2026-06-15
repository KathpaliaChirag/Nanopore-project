# AccuracyDrift

Test how Kraken2 classification accuracy and cache behavior change across different database sizes and machines.

## Machines

| Machine | RAM | Notes |
|---------|-----|-------|
| Luna (dell-R760) | 504 GB | student@luna.cse.iitd.ac.in |
| Orion (Jetson AGX Orin 64GB) | 64 GB unified | jetsonagx@10.154.233.173, ARM64, 12 cores, see machines/Orion.md |
| Minerva | TBD | student account CK |
| Chirag Suthar's system | TBD | - |
| Lab desktop | TBD | - |

## Databases

| Name | Actual Size | Type | Status on Luna |
|------|-------------|------|----------------|
| sample_targeted | 50 MB | Custom build — 6 reference genomes matching this sample exactly (P. aeruginosa PAO1, E. coli K-12, K. pneumoniae HS11286, E. faecium 62415, S. aureus MRSA252, E. cloacae ATCC 13047) | done |
| eskape_650mb | 142 MB | ESKAPE pathogens only, custom build | done |
| eskape_human_4gb | 3.8 GB | ESKAPE + human, custom build | done |
| standard_8gb | 8 GB | Pre-built standard | done |
| standard_16gb | 16 GB | Pre-built standard | done |
| pluspf_103gb | 103.4 GB | Pre-built PlusPF — Standard + protozoa + fungi; gold-standard accuracy ceiling. Cannot run on Orion (64 GB RAM insufficient). | done |

All 6 databases are ready on Luna at `~/AccuracyDrift/databases/`.

## Transferring to other machines

Each database is just 3 files — fully portable, no rebuild needed:

```bash
# Copy a database to another machine
scp ~/AccuracyDrift/databases/eskape_650mb/{hash.k2d,taxo.k2d,opts.k2d} user@machine:~/AccuracyDrift/databases/eskape_650mb/

# Or copy the whole databases folder
rsync -av ~/AccuracyDrift/databases/ user@machine:~/AccuracyDrift/databases/
```

## Setup on any machine (fresh)

```bash
mkdir -p ~/AccuracyDrift/databases/{standard_8gb,standard_16gb,eskape_650mb,eskape_human_4gb}
cd ~/AccuracyDrift/databases

# Download 8 GB
wget -P standard_8gb https://genome-idx.s3.amazonaws.com/kraken/k2_standard_08gb_20240112.tar.gz
tar -xzf standard_8gb/k2_standard_08gb_20240112.tar.gz -C standard_8gb/ && rm standard_8gb/*.tar.gz

# Download 16 GB
wget -P standard_16gb https://genome-idx.s3.amazonaws.com/kraken/k2_standard_16gb_20240112.tar.gz
tar -xzf standard_16gb/k2_standard_16gb_20240112.tar.gz -C standard_16gb/ && rm standard_16gb/*.tar.gz
```

## Custom Build: eskape_650mb and eskape_human_4gb

Requires `ncbi-genome-download`. Install if not present:
```bash
pip3 install --user ncbi-genome-download
# binary will be at ~/.local/bin/ncbi-genome-download
```

**Notes for Luna:**
- rsync is blocked — `kraken2-build --download-taxonomy` and `--download-library human` will fail, use wget instead
- genome files must be gunzipped before adding to library — kraken2-build does not handle .fna.gz
- taxonomy folder (~14 GB) and library folder can be deleted after build, only hash.k2d / taxo.k2d / opts.k2d are needed

ESKAPE taxids: E.faecium=1352, S.aureus=1280, K.pneumoniae=573, A.baumannii=470, P.aeruginosa=287, Enterobacter=547

```bash
cd ~/AccuracyDrift/databases

# Download ESKAPE genomes (1149 complete assemblies, ~7 GB uncompressed)
mkdir -p eskape_genomes
~/.local/bin/ncbi-genome-download --taxids 1352,1280,573,470,287,547 --formats fasta --assembly-levels complete bacteria -o eskape_genomes --verbose
find eskape_genomes -name "*.fna.gz" -exec gunzip {} \;

# Download taxonomy manually (rsync blocked on Luna)
mkdir -p eskape_650mb/taxonomy
cd eskape_650mb/taxonomy
wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz && tar -xzf taxdump.tar.gz && rm taxdump.tar.gz
wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/accession2taxid/nucl_gb.accession2taxid.gz && gunzip nucl_gb.accession2taxid.gz
cd ~/AccuracyDrift/databases

# Copy taxonomy to eskape_human_4gb (no need to re-download)
cp -r eskape_650mb/taxonomy eskape_human_4gb/

# Build eskape_650mb
find eskape_genomes -name "*.fna" | xargs -I{} kraken2-build --add-to-library {} --db eskape_650mb
kraken2-build --build --db eskape_650mb --max-db-size 700000000 --threads 8
rm -rf eskape_650mb/taxonomy eskape_650mb/library

# Download human genome manually (rsync blocked on Luna)
mkdir -p eskape_human_4gb/library/added
wget https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/001/405/GCF_000001405.40_GRCh38.p14/GCF_000001405.40_GRCh38.p14_genomic.fna.gz -P eskape_human_4gb/library/added/
gunzip eskape_human_4gb/library/added/GCF_000001405.40_GRCh38.p14_genomic.fna.gz

# Build eskape_human_4gb
kraken2-build --add-to-library eskape_human_4gb/library/added/GCF_000001405.40_GRCh38.p14_genomic.fna --db eskape_human_4gb
find eskape_genomes -name "*.fna" | xargs -I{} kraken2-build --add-to-library {} --db eskape_human_4gb
kraken2-build --build --db eskape_human_4gb --max-db-size 4000000000 --threads 8
rm -rf eskape_human_4gb/taxonomy eskape_human_4gb/library

# Cleanup genomes after both builds done
rm -rf eskape_genomes
```
