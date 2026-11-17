# Federated IDS Lab: students generate normal + attack + exploit traffic

Every student works **alone**, at any time, on their own Linux desktop that
opens in a web browser. On the student's private lab network sit a few **company
websites** (drawn from a catalog of 50+ simulated organizations) plus one or
more **real vulnerable apps** (DVWA / Juice Shop). The student generates
**normal** traffic, then **network attacks** (scan / brute / flood) on the
company sites, then **real exploits** (SQL injection, command injection, reverse
shell + data exfiltration) on the vulnerable apps. All of it is captured and
labeled. Each student's data becomes one federated-learning client; each
company or app becomes a federated **organization**.

```
                 Internet
                    |
          [wan network: desktops cannot see each other]
            |             |              |
      s001-desktop   s002-desktop  ...  s100-desktop   <- students use these
       + toolbox      + toolbox          + toolbox      (normal + attack, in netns)
       + capture      + capture          + capture      (tcpdump -> data/sXXX)
            |             |              |
      [s001_lan]     [s002_lan]     [s100_lan]   internal only, no internet
      company sites  company sites  company sites   <- sites/companies.py
      + vuln app(s)  + vuln app(s)  + vuln app(s)   <- DVWA / Juice Shop
```

The student's toolbox runs **inside the desktop's network namespace**, so every
request (normal or attack) is sourced from the desktop and recorded by that
student's capture. A company id (e.g. `bank-meridian`) is the **same
organization for every student who draws it**, so flows can later be merged
per company.

## Files

| File | Purpose |
|---|---|
| `sites/companies.py` | Catalog of 50+ company sites + the vulnerable-app catalog (DVWA, Juice Shop) |
| `sites/gen_sites.py` | Generates the static content for every company into `sites/content/<id>/` |
| `sites/nginx-site.conf` | Shared nginx config (makes `/login` answer brute force) |
| `generate_compose.py` | Creates `docker-compose.yml`, `students.csv`, `sites_map.csv` |
| `toolbox/` | Kali sidecar: normal traffic + network attacks + real exploit chains (`runner.py`) |
| `student/` | The `normal.sh` / `attack.sh` / `exploit.sh` / `stop.sh` scripts the student runs |
| `scripts/session.sh` | Operator helper to bring one student's stack up/down |
| `scripts/student.sh` | Self-host helper for one student (setup / phases / collect) — used in the WSL model |
| `extract_features.py` | pcaps -> labeled flow CSV per student (`flows/s001.csv`, ...) with `site_id`/`sector` |
| `attacker/` | **Old victim-model** scheduler (kept for reference; not used by this flow) |

> **Just want to spin one student up?** See [QUICKSTART.md](QUICKSTART.md).
> **Running the experiment end to end?** See the full operator guide in
> [docs/RUNBOOK.md](docs/RUNBOOK.md) — setup, batches, per-session steps,
> monitoring, dataset extraction, label reference, and troubleshooting.
> **Students self-hosting on their own laptop?** See
> [docs/WSL-STUDENT.md](docs/WSL-STUDENT.md) — run one client in WSL2, collect,
> send data, uninstall cleanly.

## Server requirements

Only **active** students consume resources: each student's whole stack is
behind a compose *profile*, so sites are not running unless that student's
session is up. An active student costs roughly their desktop (~1–2 GB) plus 5
tiny web servers (~10–30 MB each) plus the toolbox. Run students in batches
(e.g. 20–25 at a time) to fit a modest server.

## Run

```bash
pip install pyyaml
python3 sites/gen_sites.py                 # once: build all company site content
python3 generate_compose.py --start 1 --end 100
```

Bring a student online when their session starts (this is the "5 websites come
online" step), then take it down afterwards:

```bash
docker compose --profile s001 up -d        # or: scripts/session.sh s001 up
docker compose --profile s001 down         # or: scripts/session.sh s001 down
```

Options: `--sites-per-student N` (default 5, total targets), `--vuln-per-student N`
(default 1, how many of them are real vulnerable apps, max 2), `--base-port`,
`--seed`. Vulnerable apps (DVWA ~ several hundred MB, Juice Shop ~200 MB RAM)
are the heavy part — keep `--vuln-per-student` low and run small batches.

Send each student their line from `students.csv`:
`https://<server-ip>:<url_port>`, username and password.
(The certificate is self-signed, so they must click "Advanced -> Proceed".)

## What a student does (individually)

On the desktop there is a `fllab` folder with three scripts. The student runs,
in order:

1. **`./normal.sh`** — benign browsing traffic to their company sites (and they
   can browse them in the real browser too). `./stop.sh` pauses.
2. **`./attack.sh`** — **one round** of network attacks (portscan, web scan,
   directory brute force, login brute force, SYN flood) against a random subset
   of the company sites, then idles.
3. **`./exploit.sh`** — **one round** of **real exploits** against the
   vulnerable apps: SQL injection, command injection, and a reverse shell +
   data exfiltration (post-exploitation). Then idles.
4. **`./stop.sh`** — idle between phases.

Each student has a **persona** in `students.csv` (developer, media user, office
worker, ...) and a **different random mix of companies**, so every client's
data is different (non-IID). Rules: no personal accounts or passwords inside the
desktop, no illegal content.

Under the hood the scripts just write a phase word (`normal` / `attack` /
`exploit` / `idle`) to a shared control file; the toolbox reads it and acts,
writing ground truth to `logs/events.csv` (student, phase, **label**, **site
label**, times). Labels include `benign`, the network-attack types, and the
exploit types: `login_success`, `sqli`, `cmd_injection`, `reverse_shell`.

## After collection

```bash
pip install nfstream pandas
IP_HASH_KEY=<random-secret> python3 extract_features.py
```

Each `flows/sXXX.csv` is one federated client, with two labels per flow:
`label` (attack/exploit type or `benign`) and `site_id` (which company/app). To
build federated **organizations**, group flows by `site_id` (or `sector`) across
all students — e.g. every student's traffic toward `bank-meridian` is one bank
org, and every student's `vuln-dvwa` traffic is one vulnerable-app org. Grouping
happens only in your data, so students never work together.

Capture is now **full payloads** (`-s 0`), so you can add payload/DPI features on
top of the flow statistics (useful for the exploit and reverse-shell classes).

## Safety checklist

- Attack networks are `internal: true`: targets, attacks, and the reverse shell
  have **no internet route** — the shell can only call back to the student's own
  desktop inside the isolated LAN.
- Attacks/exploits only ever hit the lab's own sites and vulnerable apps.
- Vulnerable apps (DVWA, Juice Shop) are deliberately insecure — keep them on
  the `internal: true` LANs only and never expose their ports.
- Never publish ports other than the desktop ports.
- Get ethics approval and signed consent before collection.
- Capture is filtered to the lab network (`net 10.10.0.0/16`), so the student's
  real internet browsing is **not** recorded; external IPs are still hashed in
  the final CSVs.
- `students.csv` contains passwords, so don't share it or put it in git.
