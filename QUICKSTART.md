# Quickstart

Minimal path to one running student. Full guide: [docs/RUNBOOK.md](docs/RUNBOOK.md).

```bash
# 1. One-time setup
pip install pyyaml
python3 sites/gen_sites.py

# 2. Generate a batch (here: students 1..5)
python3 generate_compose.py --start 1 --end 5

# 3. Bring student s001 online (first run builds the toolbox image)
docker compose --profile s001 up -d --build

# 4. Hand s001 their login from students.csv
#    URL https://<server-ip>:30001  user s001  password <students.csv>
#    (self-signed cert -> Advanced -> Proceed)
```

On the desktop, open a terminal in the `fllab` folder and run in order:

```bash
./normal.sh     # normal traffic  (./stop.sh to pause)
./attack.sh     # network attacks (one round)
./exploit.sh    # real exploits   (one round; wait ~2 min after up for DVWA)
./stop.sh       # idle
```

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
