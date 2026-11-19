# Quickstart

Minimal path to one running student (headless / low-resource). Full guide:
[docs/RUNBOOK.md](docs/RUNBOOK.md).

```bash
# 1. One-time setup
pip install pyyaml
python3 sites/gen_sites.py

# 2. Generate a batch (here: students 1..5), headless
python3 generate_compose.py --start 1 --end 5

# 3. Bring student s001 online (first run builds the toolbox image)
docker compose --profile s001 up -d --build
```

Drive the phases (headless — from the shell):

```bash
scripts/student.sh 1 normal     # normal traffic  (scripts/student.sh 1 stop to pause)
scripts/student.sh 1 attack     # network attacks (one round)
scripts/student.sh 1 exploit    # real exploits   (one round; wait ~2 min for DVWA)
scripts/student.sh 1 stop       # idle
```

> Prefer the browser desktop? Add `--with-desktop` in step 2 (heavy, ~5 GB),
> then open `https://<server-ip>:30001` (login in `students.csv`) and run
> `./normal.sh` etc. from the desktop's `fllab` folder.

Watch it work, then tear down:

```bash
tail -f logs/events.csv                 # ground-truth labels appear here
ls -lh data/s001/                       # pcaps grow here
docker compose --profile s001 down      # stop (pcaps + logs are kept)
```

Build the dataset after collection:

```bash
pip install nfstream pandas
IP_HASH_KEY="$(openssl rand -hex 16)" python3 extract_features.py
#   -> flows/s001.csv ... (one labeled dataset per student)
```
