# Minerva — User Management Guide

> System: Ubuntu 22.04.4 LTS | Server: minerva
> Maintained by: chayanika (sudo account)

---

## Overview

This guide covers creating and managing user accounts on Minerva.
All admin commands require the sudo account (`chayanika`).

---

## Creating a New User (With Sudo — Admin Only)

### Step 1: Create the user with a home directory

```bash
sudo useradd -m -s /bin/bash <username>
```

| Flag | What it does                                      |
|------|---------------------------------------------------|
| `-m` | Creates a home directory at `/home/<username>`    |
| `-s /bin/bash` | Sets bash as the default shell          |

### Step 2: Set a password

```bash
sudo passwd <username>
```

You will be prompted to enter and confirm the password.

### Step 3: Lock down the home directory

```bash
sudo chmod 700 /home/<username>
sudo chown -R <username>:<username> /home/<username>
```

| Command  | What it does                                                   |
|----------|----------------------------------------------------------------|
| `chmod 700` | Only owner can read/write/enter — no access for others    |
| `chown`  | Ensures the user owns all files in their home folder           |

### Step 4: Verify the account

```bash
getent passwd <username>       # confirm user exists
id <username>                  # show UID, GID, groups
sudo -l -U <username>          # confirm no sudo access
```

### Step 5 (Optional): Force password change on first login

```bash
sudo chage -d 0 <username>
```

---

## Creating All 4 Lab Users (Batch)

```bash
for user in user1 user2 user3 user4; do
  sudo useradd -m -s /bin/bash $user
  sudo passwd $user
  sudo chmod 700 /home/$user
  sudo chown -R $user:$user /home/$user
done
```

---

## What "No Sudo" Means in Practice

| Action                          | Without Sudo | Notes                              |
|---------------------------------|--------------|------------------------------------|
| System-wide package install     | No           | Can't use `sudo apt install`       |
| Install in home dir (`~/local`) | Yes          | Fully allowed, no impact on others |
| Use conda/miniconda             | Yes          | Installs in home dir               |
| Run jobs / use GPU              | Yes          | Normal user access                 |
| Read other users' files         | No           | `chmod 700` blocks this            |
| Modify system config            | No           | Protected paths                    |

---

## Installing Tools Without Sudo (User Side)

### Option A: Install from source into home dir

```bash
mkdir -p ~/local
# example for valgrind:
wget https://sourceware.org/pub/valgrind/valgrind-3.22.0.tar.bz2
tar xf valgrind-3.22.0.tar.bz2
cd valgrind-3.22.0
./configure --prefix=$HOME/local
make && make install
echo 'export PATH=$HOME/local/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Option B: Conda (recommended for most tools)

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh    # installs to ~/miniconda3
conda install -c conda-forge valgrind
```

### Option C: Admin installs system-wide (once, for everyone)

```bash
sudo apt install valgrind -y
```

---

## Removing a User

```bash
sudo userdel -r <username>     # deletes user AND their home directory
```

> **Warning:** `-r` permanently deletes `/home/<username>`. Back up first if needed.

Without `-r`:
```bash
sudo userdel <username>        # removes account but keeps home directory
```

---

## Checking User Info

| Command                        | What it shows                            |
|--------------------------------|------------------------------------------|
| `getent passwd`                | All users on the system                  |
| `getent passwd <username>`     | Single user — UID, GID, home, shell      |
| `id <username>`                | UID, primary group, all groups           |
| `groups <username>`            | Groups the user belongs to               |
| `sudo -l -U <username>`        | What sudo commands (if any) they can run |
| `last <username>`              | Login history                            |
| `ls -la /home/`                | Home dir permissions for all users       |

---

## Granting Access to Specific Shared Folders

If a user needs access to a shared project folder:

```bash
# Create a shared group
sudo groupadd labgroup

# Add users to it
sudo usermod -aG labgroup user1
sudo usermod -aG labgroup user2

# Create shared folder owned by that group
sudo mkdir /home/shared_project
sudo chown root:labgroup /home/shared_project
sudo chmod 770 /home/shared_project    # group can read/write, others cannot
```

---

## GPU Access

By default users can submit GPU jobs. To check GPU availability:

```bash
nvidia-smi                     # as any user
```

If using a job scheduler (SLURM):
```bash
squeue                         # see running jobs
sbatch myjob.sh                # submit a job
sinfo                          # see node/GPU availability
```

---

## Important Notes

- Root disk (`/dev/sda3`) is at **100% capacity** as of 2026-05-27. See `minerva_stats.md`.
- Users should store large datasets in designated scratch/data directories, not home dirs.
- Warn users: home dir has no automatic backup unless configured separately.

---

## Quick Reference

```bash
# Create user
sudo useradd -m -s /bin/bash <username> && sudo passwd <username>

# Lock home dir
sudo chmod 700 /home/<username>

# Verify no sudo
sudo -l -U <username>

# Delete user + home
sudo userdel -r <username>

# List all human users (UID >= 1000)
awk -F: '$3 >= 1000 && $3 < 65534 {print $1, $3, $6}' /etc/passwd
```
