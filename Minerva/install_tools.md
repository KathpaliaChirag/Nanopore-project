# Minerva — Tool Installs

> perf_event_paranoid=1 ✓ | nsys PATH fix ✓ | sudo apt NOT allowed
> Sudo still usable for non-apt commands (dpkg, modprobe, chmod, etc.)

---

## Needs sudo (chayanika)

### valgrind
```bash
git clone https://sourceware.org/git/valgrind.git ~/valgrind-src
cd ~/valgrind-src
./autogen.sh && ./configure --prefix=/usr/local
make -j8 && sudo make install
valgrind --version
```

### LIKWID
```bash
git clone https://github.com/RRZE-HPC/likwid ~/likwid-src
cd ~/likwid-src
make -j8
sudo make install
sudo modprobe msr
echo 'msr' | sudo tee -a /etc/modules
sudo chmod +s /usr/local/bin/likwid-perfctr /usr/local/bin/likwid-pin
likwid-perfctr --version
```

### Intel VTune
```bash
# Download installer from https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler-download.html
# Transfer to Minerva then:
chmod +x vtune_installer.sh
sudo ./vtune_installer.sh -a --eula accept --install-dir /opt/intel/vtune
echo 'source /opt/intel/vtune/latest/env/vars.sh' | sudo tee /etc/profile.d/vtune.sh
source /etc/profile.d/vtune.sh
vtune --version
```

### DCGM
```bash
# Get .deb URL from https://developer.nvidia.com/dcgm
wget <dcgm-ubuntu2204-deb-url> -O ~/dcgm.deb
sudo dpkg -i ~/dcgm.deb
sudo systemctl enable nvidia-dcgm && sudo systemctl start nvidia-dcgm
dcgmi discovery -l
```

---

## Per user, no sudo (chirag / rishabh / CK / rohit)

### heaptrack + gperftools (via conda)
```bash
conda install -c conda-forge heaptrack gperftools -y
```

### FlameGraph
```bash
git clone https://github.com/brendangregg/FlameGraph ~/FlameGraph
```

### Kraken-2 with profiling flags
```bash
git clone https://github.com/DerrickWood/kraken2 ~/kraken2-src
cd ~/kraken2-src
sed -i 's/CXXFLAGS=/CXXFLAGS=-pg -g /' src/Makefile
./install_kraken2.sh ~/kraken2-build-pg
```

### Dorado (Phase 4 only)
```bash
wget https://cdn.oxfordnanoportal.com/software/analysis/dorado-1.4.0-linux-x64.tar.gz
tar -xzf dorado-1.4.0-linux-x64.tar.gz
```
