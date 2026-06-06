# AccuracyDrift

Test how Kraken2 classification accuracy and cache behavior change across different database sizes and machines.

## Machines

| Machine | RAM | Notes |
|---------|-----|-------|
| Luna (dell-R760) | 504 GB | student@luna.cse.iitd.ac.in |
| Minerva | TBD | student account CK |
| Chirag Suthar's system | TBD | - |
| Lab desktop | TBD | - |

## Databases

| Name | Size | Type | Status on Luna |
|------|------|------|----------------|
| eskape_650mb | ~650 MB | ESKAPE pathogens only, custom build | taxonomy ready, build pending |
| eskape_human_4gb | ~4 GB | ESKAPE + human, custom build | taxonomy ready, build pending |
| standard_8gb | 8 GB | Pre-built standard | extracted, ready |
| standard_16gb | 16 GB | Pre-built standard | downloaded, extract pending |

## Setup on any machine

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

Note: Luna blocks rsync so `kraken2-build --download-taxonomy` will fail. Download taxonomy manually via wget instead (see below).

ESKAPE taxids: E.faecium=1352, S.aureus=1280, K.pneumoniae=573, A.baumannii=470, P.aeruginosa=287, Enterobacter=547

```bash
cd ~/AccuracyDrift/databases

# Download ESKAPE genomes (1149 complete assemblies, ~2.2 GB)
mkdir -p eskape_genomes
~/.local/bin/ncbi-genome-download --taxids 1352,1280,573,470,287,547 --formats fasta --assembly-levels complete bacteria -o eskape_genomes --verbose

# Download taxonomy manually (rsync is blocked on Luna)
mkdir -p eskape_650mb/taxonomy
cd eskape_650mb/taxonomy
wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz && tar -xzf taxdump.tar.gz && rm taxdump.tar.gz
wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/accession2taxid/nucl_gb.accession2taxid.gz && gunzip nucl_gb.accession2taxid.gz
cd ~/AccuracyDrift/databases

# Copy taxonomy to eskape_human_4gb (no need to re-download)
cp -r eskape_650mb/taxonomy eskape_human_4gb/

# Build eskape_650mb
find eskape_genomes -name "*.fna.gz" | xargs -I{} kraken2-build --add-to-library {} --db eskape_650mb
kraken2-build --build --db eskape_650mb --max-db-size 700000000 --threads 8

# Build eskape_human_4gb
kraken2-build --download-library human --db eskape_human_4gb
find eskape_genomes -name "*.fna.gz" | xargs -I{} kraken2-build --add-to-library {} --db eskape_human_4gb
kraken2-build --build --db eskape_human_4gb --max-db-size 4000000000 --threads 8

# Cleanup after both builds done
rm -rf eskape_genomes eskape_650mb/library eskape_human_4gb/library
```
