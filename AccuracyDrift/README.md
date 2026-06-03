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

| Name | Size | Type |
|------|------|------|
| eskape_650mb | ~650 MB | ESKAPE pathogens only, custom build |
| eskape_human_4gb | ~4 GB | ESKAPE + human, custom build |
| standard_8gb | 8 GB | Pre-built standard |
| standard_16gb | 16 GB | Pre-built standard |

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
pip install ncbi-genome-download
```

ESKAPE taxids: E.faecium=1352, S.aureus=1280, K.pneumoniae=573, A.baumannii=470, P.aeruginosa=287, Enterobacter=547

```bash
cd ~/AccuracyDrift/databases

# Download ESKAPE genomes once (shared for both builds)
mkdir -p eskape_genomes
ncbi-genome-download --taxids 1352,1280,573,470,287,547 --formats fasta --assembly-levels complete bacteria -o eskape_genomes

# Build eskape_650mb
kraken2-build --download-taxonomy --db eskape_650mb
find eskape_genomes -name "*.fna.gz" | xargs -I{} kraken2-build --add-to-library {} --db eskape_650mb
kraken2-build --build --db eskape_650mb --max-db-size 700000000 --threads 8

# Build eskape_human_4gb
kraken2-build --download-taxonomy --db eskape_human_4gb
kraken2-build --download-library human --db eskape_human_4gb
find eskape_genomes -name "*.fna.gz" | xargs -I{} kraken2-build --add-to-library {} --db eskape_human_4gb
kraken2-build --build --db eskape_human_4gb --max-db-size 4000000000 --threads 8

# Cleanup raw genomes after both builds done
rm -rf eskape_genomes eskape_650mb/library eskape_human_4gb/library
```
