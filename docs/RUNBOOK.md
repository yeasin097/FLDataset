# Federated IDS Lab — Experiment Runbook

Complete operator guide for setting up, running, and collecting data from the
lab. Read [README.md](../README.md) first for the high-level idea; this document
is the step-by-step procedure.

> **Audience:** the researcher/operator running the collection. Students only
> need the short "Student instructions" card in §7.

---

## Contents

1. [What the experiment produces](#1-what-the-experiment-produces)
2. [Architecture recap](#2-architecture-recap)
3. [Prerequisites](#3-prerequisites)
4. [One-time setup](#4-one-time-setup)
5. [Planning batches & capacity](#5-planning-batches--capacity)
6. [Generating a batch](#6-generating-a-batch)
7. [Running a session (operator + student)](#7-running-a-session-operator--student)
8. [Monitoring & verifying](#8-monitoring--verifying)
9. [Tearing down a session](#9-tearing-down-a-session)
10. [Building the dataset](#10-building-the-dataset)
11. [Grouping into federated organizations](#11-grouping-into-federated-organizations)
12. [Label reference](#12-label-reference)
13. [Data & file layout](#13-data--file-layout)
14. [Troubleshooting](#14-troubleshooting)
15. [Safety, ethics & privacy](#15-safety-ethics--privacy)
16. [Command cheat sheet](#16-command-cheat-sheet)

---

## 1. What the experiment produces

For each student you collect one labeled network-traffic dataset
(`flows/sXXX.csv`). Every flow carries:

- `label` — `benign`, a network-attack type, or an exploit type.
- `site_id` / `site_name` / `sector` — which simulated organization the flow is
  with.

These per-student CSVs are the **local datasets** for federated learning (one
client per student). Grouping flows by `site_id` across students gives you
federated **organizations** (§11).

---

## 2. Architecture recap

```
                 Internet
                    |
          [wan: ICC off -> desktops cannot see each other]
            |              |               |
      s001-desktop    s002-desktop   ...  sNNN-desktop   <- students use these
       + toolbox       + toolbox          + toolbox      (traffic generator, in netns)
       + capture       + capture          + capture      (tcpdump -> data/sXXX)
            |              |               |
      [s001_lan]      [s002_lan]      [sNNN_lan]   internal: true (no internet)
      company sites   company sites   company sites   .20, .21, ...
      + vuln app(s)   + vuln app(s)   + vuln app(s)   .40, .41
```

Per student, on the isolated LAN `10.10.<i>.0/24`:

| Host | IP | Role |
|---|---|---|
| anchor (`10.10.<i>.10`) | `10.10.<i>.10` | the student's "computer": toolbox (headless) or desktop (`--with-desktop`); capture shares its netns |
| static company sites | `10.10.<i>.20` … | targets for scan / brute / flood |
| vulnerable app(s) | `10.10.<i>.40` … | targets for real exploits + reverse shell |

The diagram above shows `--with-desktop` mode. In the **headless** default there
is no desktop: the **toolbox** is the anchor at `10.10.<i>.10` and **capture**
shares its namespace, so all generated traffic is sourced from `10.10.<i>.10`
and recorded. Either way the toolbox acts on a phase word written to
`control/sXXX/phase` (via `scripts/student.sh`, or the desktop scripts in
`--with-desktop` mode).

---

## 3. Prerequisites

**Host OS:** Linux (Ubuntu 22.04+ recommended). The stack runs on Docker; a
Windows/macOS Docker host works for small tests but Linux is expected for a real
run (networking, `internal` bridges, tcpdump).

**Software:**

- Docker Engine 24+ with the Compose v2 plugin (`docker compose version`).
- Python 3.9+.
- Python packages: `pyyaml` (to generate the compose), and later `nfstream` +
  `pandas` (to extract features).

```bash
docker compose version          # must print v2.x
python3 --version
pip install pyyaml
```

**Permissions:** the operator account must be able to run `docker` (in the
`docker` group) and to read the pcaps under `data/`.

**Images on first run** (sizes approximate): `nginx:alpine` / `httpd:alpine`
(small), and — unless you use `--vuln-per-student 0` — `vulnerables/web-dvwa`
(~0.9 GB) and/or `bkimminich/juice-shop` (~0.4 GB). The `toolbox` image is
**built locally** from `toolbox/Dockerfile` (Debian slim + tools, ~0.3 GB) the
first time you bring a student up, and is reused for the capture sidecar. Only
`--with-desktop` pulls the heavy `webtop:ubuntu-xfce` (~5 GB).

---

## 4. One-time setup

From the project root (`fl-lab/`):

```bash
# 1. Install the generator dependency
pip install pyyaml

# 2. Build all simulated company site content (writes sites/content/<id>/)
python3 sites/gen_sites.py
```

`gen_sites.py` is deterministic and idempotent — re-run it any time; it
regenerates `sites/content/`. Do this **before** generating the compose, because
the site containers mount those directories.

> Pre-pull the images once so the first student session is fast. Headless
> default: `docker pull vulnerables/web-dvwa`. Only if you use `--with-desktop`:
> `docker pull lscr.io/linuxserver/webtop:ubuntu-xfce`.

---

## 5. Planning batches & capacity

Only **active** students consume resources — each student's whole stack is behind
a Docker Compose *profile*, so nothing runs until you bring that student online.

The lab is **headless by default** (no GUI desktop) — the light option. Add
`--with-desktop` only if students must browse by hand; it is far heavier.

Rough per-active-student cost:

| Component | RAM |
|---|---|
| toolbox (anchor) + capture | ~150–250 MB |
| each static site (nginx/apache) | ~10–30 MB |
| each vulnerable app (DVWA / Juice Shop) | ~150–300 MB |
| desktop (`--with-desktop` only) | ~1–2 GB |

So a headless student with 4 static sites + 1 DVWA ≈ **0.5 GB** (≈ **0.25 GB**
with `--vuln-per-student 0`); with `--with-desktop` ≈ **2.5 GB**. Headless runs
dozens of students on a modest box; desktop mode wants a real server (~20/64 GB).

Decide up front:

- **Total students** (e.g. 100) → `--start` / `--end` ranges.
- **Desktop or headless** → omit for headless (default), or `--with-desktop`.
- **Targets per student** → `--sites-per-student` (default 5).
- **Vulnerable apps per student** → `--vuln-per-student` (default 1, 0–2; `0`
  skips DVWA and the exploit phase — the lightest option). DVWA is always first
  (it supports the full exploit + reverse-shell chain); the second is Juice Shop.
- **Disk**: capture is **full-payload** (`-s 0`), filtered to the lab network.
  Budget generously — a busy session can produce hundreds of MB/hour per
  student. Pcaps rotate hourly (`-G 3600`). For 100 students over 3 weeks, plan
  **1–2 TB**.

You can split the 100 students across many generated batches (e.g. weekly), or
generate all 100 once and only bring up a subset at a time. Both work; the
profile gate is what limits resource use, not the compose size.

---

## 6. Generating a batch

```bash
python3 generate_compose.py --start 1 --end 100 \
    --sites-per-student 5 --vuln-per-student 1 --seed 42
```

Outputs (in the project root):

- `docker-compose.yml` — all services, each behind profile `sXXX`.
- `students.csv` — one row per student: persona, host IP, and the assigned site
  ids (plus URL port, username, **password** when `--with-desktop`). Keep
  private when it contains passwords.
- `sites_map.csv` — `student, site_ip, site_id, site_name, sector, stack, type,
  port`. Used later by feature extraction; safe to keep.
- `control/sXXX/phase` — the phase flag (starts `idle`).
- `control/sXXX/sites.json` — the student's assigned targets (read by toolbox).
- `data/sXXX/` — empty, will hold that student's pcaps.
- `logs/` — will hold `events.csv` (ground truth, shared by all students).

The assignment is **deterministic** given `--seed`: re-running with the same
seed produces the same student→sites mapping. Change the seed to reshuffle.

> Regenerating is safe for mapping, but it rewrites `students.csv` with **new
> passwords**. If a batch is already handed out, don't regenerate it.

---

## 7. Running a session (operator + student)

### Operator: bring the student online

```bash
# first time (builds the toolbox image):
docker compose --profile s001 up -d --build

# subsequent times:
docker compose --profile s001 up -d        # or: scripts/session.sh s001 up
```

This starts the student's company sites, the vulnerable app(s), the toolbox, and
capture (plus the desktop in `--with-desktop` mode). Drive the phases headless
with `scripts/student.sh s001 normal|attack|exploit|stop`.

Give the student their line from `students.csv`:

```
URL:      https://<server-ip>:<url_port>     (e.g. https://198.51.100.7:30001)
Username: s001
Password: <from students.csv>
```

The desktop certificate is self-signed → the student clicks **Advanced →
Proceed**.

> **DVWA needs ~1–2 minutes** to initialise its database after the container
> starts. Have the student run normal/attack traffic first; run `exploit.sh`
> once DVWA has settled.

### Student instructions (hand this out)

On the desktop there is an **`fllab`** folder (also on the Desktop). Open a
terminal there and run, in order, pausing between phases with `./stop.sh`:

1. **`./normal.sh`** — generates normal browsing traffic to the company sites.
   Also browse them yourself in the web browser. Run `./stop.sh` to pause.
2. **`./attack.sh`** — one round of network attacks on the company sites. It
   stops by itself.
3. **`./exploit.sh`** — one round of real exploits on the vulnerable apps
   (SQL injection, command injection, reverse shell). It stops by itself.
4. **`./stop.sh`** — idle between phases.

Suggested daily rhythm: **30–45 min/day for ~3 weeks**, mostly in `normal`, with
a few `attack` / `exploit` rounds per session. Everything is labeled
automatically — students don't track anything.

Rules for students: only interact with the lab targets; no personal accounts or
passwords inside the desktop; no illegal content.

### What happens under the hood

Each script writes a word (`normal` / `attack` / `exploit` / `idle`) to
`control/sXXX/phase`. The toolbox reads it:

- `normal` → loops benign HTTP to the static sites until the phase changes.
- `attack` → one round of scan/brute/flood on a random subset, then sets `idle`.
- `exploit` → one round of real exploits on the vuln app(s), then sets `idle`.

Every action appends a ground-truth row to `logs/events.csv`.

---

## 8. Monitoring & verifying

```bash
# Which of a student's containers are running
docker compose --profile s001 ps

# Toolbox activity (what it is attacking/exploiting right now)
docker compose logs -f s001-toolbox

# Capture is producing pcaps (files should appear/grow)
ls -lh data/s001/

# Ground-truth events as they are written
tail -f logs/events.csv

# Confirm a student's sites are reachable from the toolbox
docker compose exec s001-toolbox curl -s -o /dev/null -w "%{http_code}\n" http://10.10.1.20
```

Health checklist for a live student:

- [ ] `s001-desktop`, `s001-toolbox`, `s001-capture`, and the site/vuln
  containers all show `Up`.
- [ ] `data/s001/` has at least one `.pcap` that grows over time.
- [ ] Running `attack.sh` adds rows to `logs/events.csv` within a minute.
- [ ] Running `exploit.sh` eventually logs `sqli`, `cmd_injection`, and
  `reverse_shell` rows for `vuln-dvwa` (exit_code `0`). Exit `-2`/`-1` usually
  means DVWA wasn't ready — wait and re-run `exploit.sh`.

---

## 9. Tearing down a session

```bash
docker compose --profile s001 down          # or: scripts/session.sh s001 down
```

This stops and removes the student's containers and their LAN. **Pcaps in
`data/s001/` and rows in `logs/events.csv` are preserved** (they're bind-mounted
on the host). Bring the same student back up later to continue collecting; new
pcaps are added alongside the old ones.

To stop everything that is currently up:

```bash
docker compose down --remove-orphans
```

---

## 10. Building the dataset

Do this after collection (or periodically). From the project root:

```bash
pip install nfstream pandas
IP_HASH_KEY="$(openssl rand -hex 16)" python3 extract_features.py
```

`extract_features.py`:

- reads every `data/sXXX/*.pcap` and turns it into flows (nfstream, with
  statistical features),
- labels each flow using `logs/events.csv` (attack/exploit windows) and
  `sites_map.csv` (which IP is which organization),
- replaces external IPs with a keyed HMAC hash (set `IP_HASH_KEY` to a secret
  and **keep it stable** across runs if you want consistent hashing),
- writes one `flows/sXXX.csv` per student and prints the per-student label
  counts.

Each row has the flow statistics plus `site_id`, `site_name`, `sector`, and
`label`. Because capture is full-payload, you can extend this script with
payload/DPI features for the exploit and reverse-shell classes.

> Keep the **same `IP_HASH_KEY`** for the whole study so hashed external IPs
> match across students and re-runs. Store it with your secrets, not in git.

---

## 11. Grouping into federated organizations

A `site_id` is the same organization for every student who was assigned it
(e.g. `bank-meridian`, or `vuln-dvwa`). To build an organization's dataset,
concatenate the matching flows across all students:

```python
import glob, pandas as pd
frames = [pd.read_csv(f) for f in glob.glob("flows/s*.csv")]
allflows = pd.concat(frames, ignore_index=True)

# one organization = all students' flows toward a given company/app
bank = allflows[allflows.site_id == "bank-meridian"]
dvwa = allflows[allflows.site_id == "vuln-dvwa"]

# or group by sector to make larger orgs
for sector, df in allflows.groupby("sector"):
    df.to_csv(f"orgs/{sector}.csv", index=False)
```

For **Flower** (or any FL framework): run one client per `flows/sXXX.csv` for the
per-student setup, or one client per organization CSV for the grouped setup.
Grouping happens only in your data — students never work together.

---

## 12. Label reference

`logs/events.csv` columns: `student, phase, label, site_id, site_name, sector,
src_ip, dst_ip, start_utc, end_utc, exit_code`.

| Phase | Label | Meaning |
|---|---|---|
| normal | `benign` | scripted normal browsing window |
| attack | `portscan` | `nmap -sS` TCP SYN scan of ports 1–10000 |
| attack | `web_scan` | `nikto` web vulnerability scan |
| attack | `dir_bruteforce` | `dirb` directory brute force |
| attack | `login_bruteforce` | `hydra` HTTP POST login brute force |
| attack | `syn_flood` | `hping3` SYN flood (~333 pkt/s, ~45 s) |
| exploit | `login_success` | successful login to DVWA (default creds) |
| exploit | `sqli` | SQL injection (DVWA `' OR '1'='1`; Juice Shop login bypass / union) |
| exploit | `cmd_injection` | DVWA OS command injection (`cat /etc/passwd`) |
| exploit | `reverse_shell` | DVWA command-injection reverse shell + data exfiltration |

`exit_code` is the tool's return code (`0` = ran; `-1` = timed out / no shell;
`-2` = target not reachable / not ready).

Flows are labeled by matching a flow's time span to an event window for the same
`site_id` (±5 s tolerance). Flows with no matching attack/exploit window are
`benign`. Flows not involving any known site IP get an empty `site_id` — with
the lab-network capture filter these are rare.

---

## 13. Data & file layout

```
fl-lab/
├─ README.md                 overview
├─ docs/RUNBOOK.md           this file
├─ generate_compose.py       batch generator (profiles, IPs, control files)
├─ extract_features.py       pcaps -> labeled flows
├─ sites/
│  ├─ companies.py           company catalog + VULN_APPS catalog
│  ├─ gen_sites.py           static-site content generator
│  ├─ nginx-site.conf        shared nginx config (/login answers brute force)
│  └─ content/<id>/          generated site content (one dir per company)
├─ toolbox/
│  ├─ Dockerfile             Debian-slim image (nmap, hydra, hping3, nikto, dirb, tcpdump)
│  ├─ runner.py              phase runner: normal / attack / exploit
│  └─ lists/                 users / passwords / dirs wordlists
├─ student/                  normal.sh attack.sh exploit.sh stop.sh (--with-desktop only)
├─ scripts/session.sh        operator up/down helper
├─ scripts/student.sh        per-student setup / phases / collect helper
├─ attacker/                 OLD victim-model scheduler (reference only, unused)
│
│  === generated per run (NOT in git) ===
├─ docker-compose.yml
├─ students.csv              PRIVATE (passwords)
├─ sites_map.csv
├─ control/sXXX/{phase,sites.json}
├─ data/sXXX/*.pcap          raw captures (full payload, lab net only)
├─ logs/events.csv           ground-truth labels
└─ flows/sXXX.csv            final per-student datasets
```

Put `students.csv`, `control/`, `data/`, `logs/`, `flows/`, and
`docker-compose.yml` in `.gitignore` if this ever becomes a git repo.

---

## 14. Troubleshooting

**Desktop won't open / certificate warning.** Expected — self-signed. Click
*Advanced → Proceed*. Confirm the port is published:
`docker compose --profile s001 ps` and check `students.csv` for the `url_port`.

**`exploit.sh` logs exit `-2` for DVWA.** DVWA's MySQL hadn't finished starting.
Wait 1–2 minutes after `up`, then re-run `./exploit.sh`. The runner re-initialises
the DB each time, so re-running is safe.

**`reverse_shell` logs exit `-1`.** The callback didn't connect in time (DVWA
slow, or command injection blocked). Re-run `./exploit.sh`. Verify the app can
reach the desktop: `docker compose exec s001-vuln-vuln-dvwa bash -c 'cat < /dev/tcp/10.10.1.10/4444'`
should connect while a listener is active.

**No pcaps in `data/sXXX/`.** Check the capture container is `Up` and has
`NET_ADMIN`/`NET_RAW` (it does by default). `docker compose logs s001-capture`.
Remember the filter is `net 10.10.0.0/16` — only lab traffic is recorded, so an
idle student with no site traffic yet produces an empty file until they browse.

**Student browsing the real internet isn't in the data.** By design — the
capture filter excludes it for privacy. Only lab-target traffic is recorded.

**Scripts not found on the desktop.** They are at
`/config/Desktop/fllab/` (mounted read-only). The writable `control/` subfolder
is where phase words go. If the folder is missing, confirm the `volumes` in the
desktop service and that `control/sXXX/` exists on the host.

**Port already in use.** Change `--base-port` (desktop `i` publishes
`base_port + i`). Ensure the range doesn't collide with other services.

**Juice Shop target.** It listens on port **3000** (recorded in `sites.json`
and `sites_map.csv`); the toolbox uses that port automatically.

**Out of RAM / host thrashing.** Too many active students. `down` some profiles
and run smaller batches (§5).

**Containers fail with `adding interface … to bridge … failed: Device does not
exist`, and/or custom networks never work (only the default `docker0` does).**
This is Docker 29's nftables backend failing on some (often newer-kernel) hosts:
it creates a user-defined bridge, the nft rule step fails, Docker rolls the
bridge back, and the veth attach then finds no device. **The fix that worked:**
switch the host to the iptables-legacy backend and restart Docker:
```bash
sudo apt-get install -y nftables
sudo update-alternatives --set iptables  /usr/sbin/iptables-legacy
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy
sudo systemctl restart docker
# verify: a container on a NEW network can reach out
docker network create t && docker run --rm --network t alpine true && docker network rm t
```

**Toolbox build fails resolving the package mirror (`Temporary failure
resolving …`).** The build already uses `network: host` (set in
`generate_compose.py`), which avoids this on most hosts. If it still happens, set
the daemon DNS and rebuild:
```bash
sudo mkdir -p /etc/docker
echo '{"dns": ["8.8.8.8", "1.1.1.1"]}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker && docker compose --profile s001 up -d --build
```

**`curl: command not found` on a minimal host.** Install Docker from the distro
repos instead of the get.docker.com script: `sudo apt-get install -y docker.io
docker-compose-v2`.

**Regenerated compose changed passwords.** `generate_compose.py` mints new
passwords each run. Don't regenerate a batch that's already in use; keep the
`students.csv` you handed out.

---

## 15. Safety, ethics & privacy

- **Isolation:** every LAN is `internal: true` — targets, attacks, and the
  reverse shell have **no internet route**. The reverse shell can only call back
  to the student's own desktop inside the isolated LAN.
- **Scope:** attacks and exploits only ever hit the lab's own sites and
  vulnerable apps. Desktops cannot see each other (`wan` has ICC disabled).
- **Vulnerable apps are deliberately insecure** (DVWA, Juice Shop) — never
  publish their ports; keep them on the internal LANs only.
- **Publish only desktop ports.** Nothing else should be reachable from outside.
- **Consent & approval:** obtain ethics approval and signed informed consent
  before collecting. Tell students their traffic is recorded.
- **Privacy:** capture is filtered to the lab network, so students' real
  internet browsing is not recorded; any external IPs that do appear are hashed
  (`IP_HASH_KEY`) in the final CSVs. Full payloads are captured **only** for lab
  traffic.
- **Secrets:** `students.csv` holds passwords and `IP_HASH_KEY` is a secret —
  keep both out of git and out of shared drives.

---

## 16. Command cheat sheet

```bash
# One-time
pip install pyyaml
python3 sites/gen_sites.py

# Generate a batch of 100 students
python3 generate_compose.py --start 1 --end 100 --sites-per-student 5 --vuln-per-student 1

# Bring a student up / down
docker compose --profile s001 up -d --build     # first time
scripts/session.sh s001 up
scripts/session.sh s001 down

# Monitor
docker compose --profile s001 ps
docker compose logs -f s001-toolbox
tail -f logs/events.csv
ls -lh data/s001/

# Build the dataset
pip install nfstream pandas
IP_HASH_KEY="$(openssl rand -hex 16)" python3 extract_features.py
```
