# Luna — User Management Guide

> System: Ubuntu 22.04 LTS | Server: dell-R760 (luna)
> Maintained by: chayanika (sudo account)

---

## Overview

All admin commands require the sudo account (`chayanika`).
Luna has more resources than Minerva (503 GB RAM, 2× L40S, 210 MB L3) but the same
user management process applies.

---

## Creating a New User (Needs Sudo — chayanika)

### Step 1: Create user with home directory

```bash
sudo useradd -m -s /bin/bash <username>
```

| Flag | What it does |
|---|---|
| `-m` | Creates `/home/<username>` |
| `-s /bin/bash` | Bash as default shell |

### Step 2: Set password

```bash
sudo passwd <username>
```

### Step 3: Lock down home directory

```bash
sudo chmod 700 /home/<username>
sudo chown -R <username>:<username> /home/<username>
```

`chmod 700` = only owner can read/write/enter. No visibility for other users.

### Step 4: Verify no sudo

```bash
getent passwd <username>       # confirm user exists
id <username>                  # show UID, GID, groups
sudo -l -U <username>          # should say: not allowed to run sudo
```

### Step 5 (Optional): Force password change on first login

```bash
sudo chage -d 0 <username>
```

---

## Create `student` Account (Specific Commands)

```bash
sudo useradd -m -s /bin/bash student
sudo passwd student
sudo chmod 700 /home/student
sudo chown -R student:student /home/student
```

Verify:
```bash
getent passwd student
id student
sudo -l -U student
ls -la /home/ | grep student
```

---

## What `student` Can and Cannot Do

| Action | Without Sudo | Notes |
|---|---|---|
| System-wide `apt install` | No | No sudo |
| Install in `~/local` | Yes | Fully allowed |
| Use conda/miniconda | Yes | Installs in home dir |
| Run `perf stat` | Yes (software events only) | Hardware counters need `perf_event_paranoid ≤ 1` — system-wide fix, ask chayanika |
| Use `gcc`, `g++`, `make` | Yes | In system PATH |
| Run GPU jobs | Yes | `nvidia-smi` works; both L40S accessible |
| Read other users' files | No | `chmod 700` blocks this |
| Modify `/proc/sys/...` | No | Needs root |

---

## Luna-Specific Considerations

### perf_event_paranoid
```
Current value: 4 (blocks ALL hardware counters for non-root)
```
This blocks hardware PMU events for `student` (and all non-root users).
Fix (one-time, as chayanika):
```bash
sudo sysctl -w kernel.perf_event_paranoid=1
echo 'kernel.perf_event_paranoid=1' | sudo tee /etc/sysctl.d/99-perf.conf
```
Once done, `student` gets full hardware counters — LLC-load-misses, stalled-cycles-backend, TMA. No per-user change needed.

### Resource Limits (Optional)
To prevent runaway jobs from eating all 503 GB RAM:
```bash
# /etc/security/limits.conf
student hard as 32000000       # max 32 GB virtual memory
student hard nproc 64          # max 64 processes
student hard nofile 4096       # max open files
```

### Disk Quota (Optional)
```bash
# Check if quota tools are installed
sudo apt install quota quotatool

# Enable quota on /dev/sda3 (root filesystem)
# Edit /etc/fstab — add usrquota to root mount options, then:
sudo quotacheck -cum /
sudo quotaon /

# Set student quota: 50 GB soft, 60 GB hard
sudo setquota -u student 50G 60G 0 0 /
sudo repquota -u /          # check current usage
```

---

## Tool Inventory Check (Run as `student` After Login)

Log in as student:
```bash
su - student        # from chayanika's terminal
# or
ssh student@<luna-ip>
```

Then run the full check:
```bash
echo "=== PATH ===" && echo $PATH

echo "=== Core tools ===" && \
  which gcc g++ python3 make perl 2>/dev/null

echo "=== Profiling tools ===" && \
  which perf valgrind nvcc nsys ncu likwid-perfctr numactl 2>/dev/null

echo "=== Tool versions ===" && \
  gcc --version 2>/dev/null | head -1 && \
  perf --version 2>/dev/null && \
  python3 --version 2>/dev/null

echo "=== Perf paranoid ===" && cat /proc/sys/kernel/perf_event_paranoid

echo "=== GPU access ===" && nvidia-smi 2>/dev/null | head -15

echo "=== Disk ===" && df -h /home

echo "=== RAM ===" && free -h

echo "=== User info ===" && id && groups

echo "=== Sudo check ===" && sudo -l 2>&1 | head -5

echo "=== Perf smoke test ===" && perf stat ls 2>&1 | tail -10
```

Paste the output here → add to `luna_stats.md` under a "Student Account — Tool Inventory" section.

---

## Removing a User

```bash
sudo userdel -r student     # removes account AND /home/student
```

Without `-r`:
```bash
sudo userdel student        # removes account, keeps /home/student
```

---

## Shared Folder for Lab (Optional)

If student needs access to shared data (e.g., the kraken2 DB or pod5 files):
```bash
sudo groupadd labgroup
sudo usermod -aG labgroup student
sudo usermod -aG labgroup CK

sudo mkdir /home/shared_lab
sudo chown root:labgroup /home/shared_lab
sudo chmod 770 /home/shared_lab     # group can read/write, others cannot
```

---

## Quick Reference

```bash
# Full create + lock in one block
sudo useradd -m -s /bin/bash student && \
sudo passwd student && \
sudo chmod 700 /home/student && \
sudo chown -R student:student /home/student

# Verify
sudo -l -U student
id student

# Delete + home dir
sudo userdel -r student

# List all human users (UID >= 1000)
awk -F: '$3 >= 1000 && $3 < 65534 {print $1, $3, $6}' /etc/passwd
```

---

## Existing Users (Audited 2026-05-28)

| Username | Role | Sudo | Home |
|---|---|---|---|
| chayanika | Admin | Yes | `/home/chayanika` |
| student | Student (to be created) | No | `/home/student` |

> Update this table when new accounts are created.
