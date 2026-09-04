# Minerva: internet access guide

IITD internet only works through a proxy server, and the proxy needs a login with your IITD credentials before it'll pass anything through. each user has their own IITD ID and runs the login script independently.

Server: minerva | Proxy: proxy62.iitd.ac.in:3128

---

## How IITD internet works

```
Your Server ──→ proxy62.iitd.ac.in:3128 ──→ Internet
                (must be logged in to pass through)
```

Without running this script, the server has no internet access. The script logs in and sends a heartbeat every 100 seconds to stay connected.

---

## The script: iitd-login.py

Original author: J Phani Mahesh
Location on Minerva: `/home/chayanika/iitd-login.py`

### What it does step by step

| Step | What happens |
|------|-------------|
| 1 | Fetches the proxy login page from `proxy62.iitd.ac.in` |
| 2 | Extracts a `sessionid` from the HTML |
| 3 | POSTs your userid + password + sessionid to authenticate |
| 4 | Tests connection by fetching `http://example.com` through proxy |
| 5 | Every 100 seconds sends a Refresh heartbeat to stay logged in |
| 6 | If connection drops, auto logs out and logs back in (up to 10 attempts) |

### Script settings

| Variable           | Value                  | Meaning                            |
|--------------------|------------------------|-------------------------------------|
| `SLEEP_TIMER`      | 100 seconds            | How often heartbeat is sent        |
| `LOGIN_ATTEMPTS`   | 5                      | Retries per login attempt          |
| `MAX_CONN_ATTEMPTS`| 10                     | Max reconnect attempts before quit |
| `PROXY_BASE_URL`   | proxy62.iitd.ac.in     | IITD proxy server                  |
| `PROXY_PORT`       | 3128                   | Proxy port                         |

---

## Admin setup: do once per new user

Copy the script to each user's home folder and set the correct permissions:

```bash
for user in user1 user2 user3 user4; do
  sudo cp /home/chayanika/iitd-login.py /home/$user/
  sudo chown $user:$user /home/$user/iitd-login.py
  sudo chmod 700 /home/$user/iitd-login.py
done
```

| Command      | What it does                                      |
|--------------|-----------------------------------------------------|
| `cp`         | Copies script to their home folder                |
| `chown`      | Makes them the owner of the file                  |
| `chmod 700`  | Only they can read/run it, which protects credentials |

---

## User setup: each user does this

### Step 1: start a tmux session

You want the script to survive a closed or disconnected terminal, so it runs inside tmux.

```bash
tmux new -s internet
```

### Step 2: run the login script

```bash
python3 ~/iitd-login.py -d
```

It will prompt:
```
userid: your_iitd_entry_number
passwd: your_password
```

The `-d` flag shows live output so you can confirm it logged in successfully:
```
2026-05-27 21:00:01: Logging in...
2026-05-27 21:00:02: Reading login page...
2026-05-27 21:00:03: Logged in.
2026-05-27 21:00:43: Heartbeat sent
```

### Step 3: detach from tmux

Press `Ctrl + B`, then `D`.

The script keeps running in the background, so your internet stays active.

---

## Useful commands for users

| Command                        | What it does                                      |
|---------------------------------|-----------------------------------------------------|
| `tmux new -s internet`         | Start a new tmux session named "internet"         |
| `tmux attach -t internet`      | Reattach to see live logs                         |
| `tmux ls`                      | List all running tmux sessions                    |
| `pgrep -a python3`             | Check if the login script process is alive        |
| `Ctrl + B, D`                  | Detach from tmux (keeps script running)           |
| `Ctrl + C`                     | Stop the script (inside tmux)                     |

---

## Useful commands for admin

```bash
# Check who is running the login script right now
ps aux | grep iitd-login

# Check all active tmux sessions on server
tmux ls

# See all logged-in users
w
```

---

## Important notes

- The IITD proxy allows **one active session per IITD account**. If the same credentials are used twice, the first session gets kicked out.
- Each user must use **their own IITD entry number and password**.
- If internet stops working, reattach to tmux (`tmux attach -t internet`) and check the logs.
- The script auto-reconnects on failure, so usually no manual intervention is needed.
- Do **not** share credentials or run the script from two terminals at once.

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| `already logged in` message | Script ran twice with same credentials | Kill duplicate process, restart once |
| `Connection test request failed` | Proxy unreachable or wrong credentials | Check userid/passwd, retry |
| Script exits after a while | Exceeded `MAX_CONN_ATTEMPTS` (10) | Restart the script |
| No internet after login | Proxy env variables not set | See below |

### If internet works in the script but not in the terminal

Some tools (pip, wget, curl, conda) need the proxy environment variables set directly:

```bash
# Add to ~/.bashrc so it applies every login
echo 'export http_proxy=http://proxy62.iitd.ac.in:3128' >> ~/.bashrc
echo 'export https_proxy=http://proxy62.iitd.ac.in:3128' >> ~/.bashrc
echo 'export HTTP_PROXY=http://proxy62.iitd.ac.in:3128' >> ~/.bashrc
echo 'export HTTPS_PROXY=http://proxy62.iitd.ac.in:3128' >> ~/.bashrc
source ~/.bashrc
```

Then test:
```bash
curl http://example.com
wget http://example.com
```
