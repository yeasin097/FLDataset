# Student Guide — What You Have To Do

Welcome! You will run a small security lab on your own Windows laptop for a few
weeks. A tool generates network traffic (normal web browsing, and simulated
attacks) against practice websites that run only on your computer. Your laptop
records this traffic. At the end you send the recording to your instructor.

**You do not need to know security or networking.** Just follow the steps.

Your instructor will give you:
- **Your student id** (e.g. `223009712`) — use your real id
- **A seed number** (e.g. `42`) — everyone uses the same one

The lab itself is on GitHub: `https://github.com/yeasin097/FLDataset.git`

---

## Before you start — what you need

- Windows 10 or 11, and you can run programs as **Administrator**
- About **4 GB free memory** and **8 GB free disk**
- Internet (for the one-time setup download)

---

## STEP 1 — Install the lab (one time, ~20 minutes)

### 1a. Turn on WSL in Windows Features

1. Press Start, type **"Turn Windows features on or off"**, open it.
2. Tick these two boxes:
   - ☑ **Windows Subsystem for Linux**
   - ☑ **Virtual Machine Platform**
3. Click **OK**, then **restart your PC** when asked.

### 1b. Install Ubuntu with the installer

Get **`install-wsl.bat`** from the lab (it's in the repo). Right-click it →
**Run as administrator**. It installs Ubuntu 24.04. Restart if it asks you to.

Then open **"Ubuntu 24.04"** from the Start menu. The first time, it asks you to
create a **username and password** — pick any, and remember them.

### 1c. Download the lab and install its tools

In the **Ubuntu** window, copy-paste these lines:

```bash
sudo apt-get update && sudo apt-get install -y git
mkdir 230010112
cd 230010112
git clone https://github.com/yeasin097/FLDataset.git .
bash scripts/setup.sh
```

`setup.sh` installs everything the lab needs. When it finishes it tells you to:

1. In **PowerShell** run: `wsl --shutdown`
2. Re-open the **Ubuntu** window.
3. Check it works (should print an empty table, no error): `docker ps`

### 1d. Start it

Tell the lab who you are (use **your** id and seed), then start:

```bash
cd ~/fl-lab
export FLLAB_ID=223009712
export FLLAB_SEED=42
./scripts/student.sh "$FLLAB_ID" setup
```

The first time this downloads and builds things — **give it 5–15 minutes**. When
it finishes it tells you it is ready. There is no window to look at; the tool
makes the traffic for you. You just run the commands in Step 2.

---

## STEP 2 — Daily routine (about 30 minutes a day, for ~3 weeks)

Each day, open **Ubuntu**, then:

```bash
cd ~/fl-lab
```

Run these (use **your** id instead of `223009712`). Do them in order, and wait a
little between them:

```bash
./scripts/student.sh 223009712 normal     # make normal web traffic — leave it a while
./scripts/student.sh 223009712 stop       # pause the normal traffic

./scripts/student.sh 223009712 attack     # run one round of attacks (stops by itself)
./scripts/student.sh 223009712 exploit    # run one round of exploits (stops by itself)

./scripts/student.sh 223009712 status     # see what has been recorded so far
```

How to spread it over the weeks:
- Spend **most** of your time in `normal`.
- Do a few `attack` and `exploit` rounds across the weeks (not every day).
- Mix it up — there is no exact schedule.

When you are done for the day you can stop everything:

```bash
./scripts/student.sh 223009712 down
```

Next day, start again with:

```bash
./scripts/student.sh 223009712 setup
```

> If `exploit` shows errors the first time, wait a minute and run it again.

---

## STEP 3 — Finish: send your recording (IMPORTANT)

When your collection period ends, create your results file:

```bash
cd ~/fl-lab
./scripts/student.sh 223009712 collect
```

It prints the location of a file named like `fllab-s223009712-....tgz`. From Windows
you can find it at:

```
\\wsl.localhost\Ubuntu-24.04\home\YOUR-LINUX-USERNAME\
```

**Send that `.tgz` file to your instructor** the way they asked (email/upload).
**Wait until they confirm they received it.**

> ⚠️ **Do not uninstall anything until your instructor confirms they have your
> file.** Uninstalling deletes your recording forever.

---

## STEP 4 — Clean up (only after your file is confirmed received)

In **PowerShell**:

```powershell
wsl --unregister Ubuntu-24.04
```

That removes the whole lab and frees up the disk space. Done — thank you!

---

## If something goes wrong

| Problem | Fix |
|---|---|
| `docker ps` says "Cannot connect to the Docker daemon" | Run `sudo systemctl start docker`, then try again. |
| `exploit` shows errors the first time | Wait ~1 minute and run `./scripts/student.sh <N> exploit` again. |
| `install-wsl.bat` fails / "virtualization not enabled" | Make sure both Windows Features in Step 1a are ticked and you restarted; if it still fails, turn on *Virtualization* (*SVM*/*VT-x*) in your PC's BIOS. |
| `git clone` says "could not resolve host" | Check your internet connection, then run the clone line again. |
| Laptop feels slow while running | Run `./scripts/student.sh <N> down` when you are not actively using it. |
| You forgot your id or seed | Ask your instructor. |

If you are stuck, send your instructor a screenshot of the error.
