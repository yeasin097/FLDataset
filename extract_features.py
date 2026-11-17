#!/usr/bin/env python3
"""
Turn each student's pcaps into a labeled flow CSV (one CSV per student =
one federated client's local dataset).

  pip install nfstream pandas
  python3 extract_features.py

Two labels are attached to every flow:
  - label   : the attack type (portscan, web_scan, dir_bruteforce,
              login_bruteforce, syn_flood) or "benign".
  - site_id : which company (organization) the flow is with, or "" for
              non-site traffic (e.g. the student's real internet browsing).

Labeling uses:
  - sites_map.csv  : student + site_ip -> site_id / name / sector
  - logs/events.csv: ground-truth attack/normal windows written by the toolbox.
A flow is an attack if its company matches an attack event for that student and
their time ranges overlap; otherwise it is benign.

Grouping by site_id across students gives you per-organization datasets.
External (internet) IPs are replaced by a keyed hash for privacy.
"""
import glob
import hashlib
import hmac
import os

import pandas as pd
from nfstream import NFStreamer

SECRET = os.environ.get("IP_HASH_KEY", "change-me").encode()
OUT = "flows"
os.makedirs(OUT, exist_ok=True)

events = pd.read_csv("logs/events.csv")
for c in ("start_utc", "end_utc"):
    events[c] = pd.to_datetime(events[c], utc=True).astype("int64") // 10**6  # ms
attacks = events[events.label != "benign"]

smap = pd.read_csv("sites_map.csv")
# (student, site_ip) -> site metadata
site_lookup = {
    (r.student, r.site_ip): (r.site_id, r.site_name, r.sector)
    for r in smap.itertuples()
}


def anon(ip):
    if isinstance(ip, str) and ip.startswith("10.10."):
        return ip
    return "ext-" + hmac.new(SECRET, str(ip).encode(), hashlib.sha256).hexdigest()[:12]


def site_of(student, row):
    """Which company this flow is with (match either endpoint)."""
    for ip in (row.dst_ip, row.src_ip):
        hit = site_lookup.get((student, ip))
        if hit:
            return hit
    return ("", "", "")


def attack_label(student, site_id, row, windows):
    if not site_id:
        return "benign"
    for w in windows.itertuples():
        if w.site_id == site_id \
                and row.bidirectional_first_seen_ms <= w.end_utc + 5000 \
                and row.bidirectional_last_seen_ms >= w.start_utc - 5000:
            return w.label
    return "benign"


for folder in sorted(glob.glob("data/s*")):
    s = os.path.basename(folder)
    frames = []
    for pcap in sorted(glob.glob(f"{folder}/*.pcap")):
        df = NFStreamer(source=pcap, statistical_analysis=True).to_pandas()
        if not df.empty:
            frames.append(df)
    if not frames:
        continue
    df = pd.concat(frames, ignore_index=True)
    windows = attacks[attacks.student == s]

    site_ids, site_names, sectors, labels = [], [], [], []
    for r in df.itertuples():
        sid_, sname, sector = site_of(s, r)
        site_ids.append(sid_)
        site_names.append(sname)
        sectors.append(sector)
        labels.append(attack_label(s, sid_, r, windows))
    df["site_id"] = site_ids
    df["site_name"] = site_names
    df["sector"] = sectors
    df["label"] = labels

    df["src_ip"] = df["src_ip"].map(anon)
    df["dst_ip"] = df["dst_ip"].map(anon)
    df.to_csv(f"{OUT}/{s}.csv", index=False)
    print(s, len(df), "flows", df["label"].value_counts().to_dict())
