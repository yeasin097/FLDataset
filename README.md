# Federated IDS Lab: students generate normal + attack + exploit traffic

Each student gets a small, isolated set of targets on their own private LAN: a
few **company websites** (from a catalog of 50+ simulated organizations) plus
optional **real vulnerable apps** (DVWA / Juice Shop). A per-student **toolbox**
generates **normal** traffic, then **network attacks** (scan / brute / flood) on
the company sites, then **real exploits** (SQL injection, command injection,
reverse shell + exfiltration) on the vulnerable apps. All of it is captured and
labeled. Each student's data becomes one federated-learning client; each company
or app becomes a federated **organization**.

```
      s001 stack          s002 stack       ...     (each behind a compose profile)
   ┌───────────────┐   ┌───────────────┐
   │ toolbox (anchor)│  │ toolbox        │   <- generates traffic; IS the student's
   │ + capture       │  │ + capture      │      "computer"; tcpdump -> data/sXXX
   └──────┬─────────┘   └──────┬─────────┘
      [s001_lan]           [s002_lan]        internal: true (no internet)
      company sites        company sites     <- sites/companies.py
      + vuln app(s)        + vuln app(s)     <- DVWA / Juice Shop (optional)
```

The toolbox and capture share one network namespace, so every request (normal,
attack, exploit) is sourced from the student's one host and recorded. A company
id (e.g. `bank-meridian`) is the **same organization for every student who draws
it**, so flows can later be merged per company.

**Headless by default** (lightest — runs on a low-end PC). Add `--with-desktop`
to also give each student a browser-based Linux desktop (webtop) they can browse
from by hand; that is much heavier (~5 GB image, ~2 GB RAM each).

## Files

| File | Purpose |
|---|---|
| `sites/companies.py` | Catalog of 50+ company sites + the vulnerable-app catalog (DVWA, Juice Shop) |
| `sites/gen_sites.py` | Generates the static content for every company into `sites/content/<id>/` |
| `sites/nginx-site.conf` | Shared nginx config (makes `/login` answer brute force) |
| `generate_compose.py` | Creates `docker-compose.yml`, `students.csv`, `sites_map.csv` |
| `toolbox/` | Debian sidecar: normal traffic + network attacks + real exploit chains (`runner.py`); also the capture image |
| `student/` | `normal.sh` / `attack.sh` / `exploit.sh` / `stop.sh` — only used in `--with-desktop` mode |
| `scripts/session.sh` | Operator helper to bring one student's stack up/down |
| `scripts/student.sh` | Self-host helper for one student (setup / phases / collect) — used in the WSL model |
| `extract_features.py` | pcaps -> labeled flow CSV per student (`flows/s001.csv`, ...) with `site_id`/`sector` |
| `attacker/` | **Old victim-model** scheduler (kept for reference; not used by this flow) |

> **Just want to spin one student up?** See [QUICKSTART.md](QUICKSTART.md).
> **Running the experiment end to end?** See the full operator guide in
> [docs/RUNBOOK.md](docs/RUNBOOK.md) — setup, batches, per-session steps,
> monitoring, dataset extraction, label reference, and troubleshooting.
> **Hand this to students** → [docs/STUDENT.md](docs/STUDENT.md): everything a
> student does on their own Windows laptop with WSL2 — install, run the daily
> phases, send their data, uninstall. Nothing else needed.

## Server requirements

Only **active** students consume resources: each student's whole stack is behind
a compose *profile*, so nothing runs unless that student's session is up.

| Mode | Images pulled/built | RAM per active student |
|---|---|---|
| headless, `--vuln-per-student 0` | ~0.6 GB (toolbox + 2 web images) | ~0.25 GB |
| headless + DVWA (default) | ~1.5 GB | ~0.5 GB |
| `--with-desktop` | ~6 GB (adds webtop) | ~2.5 GB |

So the default headless mode runs several students on a modest laptop; the
desktop mode wants a real server. Run in batches to fit the hardware.

## Run

```bash
pip install pyyaml
python3 sites/gen_sites.py                 # once: build all company site content
python3 generate_compose.py --start 1 --end 100          # headless (light)
# or, to add the browser desktop per student (heavy):
# python3 generate_compose.py --start 1 --end 100 --with-desktop
```

Bring a student online when their session starts, then take it down afterwards:

```bash
docker compose --profile s001 up -d        # or: scripts/session.sh s001 up
docker compose --profile s001 down         # or: scripts/session.sh s001 down
```

Options: `--with-desktop` (add the heavy browser GUI; default headless),
`--sites-per-student N` (default 5, total targets), `--vuln-per-student N`
(default 1, how many are real vulnerable apps, 0–2; `0` = lightest, no exploit
phase), `--base-port`, `--seed`. The desktop and the vulnerable apps are the
heavy parts — drop them for low-end machines.

## Driving a student's phases

The three phases are driven by writing a word to the student's control file.
Headless: use the helper (or `echo attack > control/s001/phase`):

```bash
scripts/student.sh 1 normal      # benign traffic to the company sites
scripts/student.sh 1 attack      # one round of network attacks, then idle
scripts/student.sh 1 exploit     # one round of real exploits, then idle
scripts/student.sh 1 stop        # idle
```

With `--with-desktop`, the student can instead run `./normal.sh`, `./attack.sh`,
`./exploit.sh`, `./stop.sh` from the `fllab` folder on their desktop, and browse
the sites by hand during the normal phase. Their login line is in `students.csv`
(`https://<server-ip>:<url_port>`, username, password; self-signed cert →
"Advanced → Proceed").

The phases:

1. **normal** — benign browsing traffic to the company sites.
2. **attack** — one round of network attacks (portscan, web scan, directory
   brute force, login brute force, SYN flood) on a random subset, then idles.
3. **exploit** — one round of real exploits on the vulnerable apps: SQL
   injection, command injection, reverse shell + data exfiltration. Then idles.

Each student has a **persona** in `students.csv` and a **different random mix of
companies**, so every client's data is different (non-IID).

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
