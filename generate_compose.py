#!/usr/bin/env python3
"""
Generate docker-compose.yml for N students (source model, with vulnerable tier).

Two modes:
  * HEADLESS (default)  -- lightest; runs on a low-end PC. No GUI desktop. The
    toolbox container is the network anchor and generates all traffic; capture
    shares its namespace. Students drive phases from the shell (scripts/student.sh
    or `echo attack > control/sXXX/phase`).
  * --with-desktop       -- adds a browser-based Linux desktop (webtop) per
    student so they can also browse the sites by hand. Much heavier (~5 GB image,
    ~2 GB RAM per student).

Each student gets:
  - static company sites : lightweight nginx/apache containers on the student's
                           own isolated LAN (targets for scan / brute / flood).
  - vulnerable apps      : real DVWA / Juice Shop containers (exploit targets).
                           Use --vuln-per-student 0 for the lightest setup.
  - toolbox              : Debian sidecar; normal-traffic generator + attack /
                           exploit runner. Also the capture image (ships tcpdump).
  - capture              : tcpdump in the anchor's namespace. Full payloads
                           (-s 0) filtered to the lab network (net 10.10.0.0/16),
                           so real internet browsing payloads are never recorded.

Every student's whole stack is behind a compose PROFILE named after the student
(s001, ...), so only ACTIVE students consume resources.

A company / app id is the SAME organization for every student who draws it, so
flows can be merged per organization using sites_map.csv + logs/events.csv.

Usage:
  python3 sites/gen_sites.py                       # once: build site content
  python3 generate_compose.py --start 1 --end 25
  docker compose --profile s001 up -d
"""
import argparse
import csv
import json
import os
import random
import secrets

import yaml

from sites.companies import companies, vuln_apps

PERSONAS = [
    "developer (GitHub, Stack Overflow, docs, package downloads)",
    "student researcher (Google Scholar, PDFs, Wikipedia, online courses)",
    "media user (YouTube, music streaming, news sites)",
    "social user (Facebook web, chat apps on the web, email)",
    "office worker (Google Docs, email, cloud storage, video meetings)",
    "online shopper (e-commerce sites, comparison sites, banking pages)",
]

NGINX_CONF = "./sites/nginx-site.conf"
TOOLBOX_IMAGE = "fl-lab/toolbox:latest"     # built once, reused for capture


def sid(i):
    return f"s{i:03d}"


def _map_row(student, entry):
    """sites_map.csv row (column names expected by extract_features.py)."""
    return {
        "student": student,
        "site_ip": entry["ip"],
        "site_id": entry["id"],
        "site_name": entry["name"],
        "sector": entry["sector"],
        "stack": entry["stack"],
        "type": entry["type"],
        "port": entry["port"],
    }


def build(start, end, base_port, seed, n_sites, n_vuln, with_desktop):
    catalog = companies()
    vcatalog = vuln_apps()
    n_vuln = min(n_vuln, len(vcatalog))
    n_static = max(0, n_sites - n_vuln)
    services, networks, students, site_map_rows = {}, {}, [], []

    # The wan (internet) network only exists to give desktops internet. In
    # headless mode there are no desktops, so the whole lab is air-gapped.
    if with_desktop:
        networks["wan"] = {
            "driver": "bridge",
            "driver_opts": {"com.docker.network.bridge.enable_icc": "false"},
            "ipam": {"config": [{"subnet": "172.30.0.0/16"}]},
        }

    for i in range(start, end + 1):
        s = sid(i)
        lan = f"{s}_lan"
        profile = [s]
        host_ip = f"10.10.{i}.10"            # the student's "computer" on the LAN
        password = secrets.token_urlsafe(9)
        port = base_port + i
        persona = PERSONAS[(i - 1) % len(PERSONAS)]

        # Deterministic per-student mix of companies (non-IID by site mix).
        srnd = random.Random(seed * 1000 + i)
        statics = srnd.sample(catalog, k=n_static)
        vulns = vcatalog[:n_vuln]            # dvwa first -> full exploit chain

        # internal: true -> no route to the internet. Attacks stay inside.
        networks[lan] = {
            "driver": "bridge",
            "internal": True,
            "ipam": {"config": [{"subnet": f"10.10.{i}.0/24"}]},
        }

        # Optional browser desktop (heavy). When present it is the net anchor.
        if with_desktop:
            services[f"{s}-desktop"] = {
                "image": "lscr.io/linuxserver/webtop:ubuntu-xfce",
                "hostname": s,
                "environment": {
                    "PUID": "1000", "PGID": "1000", "TZ": "Asia/Dhaka",
                    "CUSTOM_USER": s, "PASSWORD": password,
                },
                "shm_size": "1gb",
                "security_opt": ["seccomp=unconfined"],
                "mem_limit": "2g",
                "ports": [f"{port}:3001"],
                "volumes": [
                    "./student:/config/Desktop/fllab:ro",
                    f"./control/{s}:/config/Desktop/fllab-control",
                ],
                "networks": {"wan": {}, lan: {"ipv4_address": host_ip}},
                "profiles": profile,
                "restart": "unless-stopped",
            }

        anchor = f"{s}-desktop" if with_desktop else f"{s}-toolbox"

        sites_json = []

        # Static company sites (IPs .20..)
        for k, c in enumerate(statics):
            site_ip = f"10.10.{i}.{20 + k}"
            svc = f"{s}-site-{c['id']}"
            vols = [f"./sites/content/{c['id']}:{c['docroot']}:ro"]
            if c["stack"] == "nginx":
                vols.append(f"{NGINX_CONF}:/etc/nginx/conf.d/default.conf:ro")
            services[svc] = {
                "image": c["image"],
                "hostname": c["id"],
                "volumes": vols,
                "networks": {lan: {"ipv4_address": site_ip}},
                "profiles": profile,
                "restart": "unless-stopped",
            }
            entry = {"id": c["id"], "name": c["name"], "sector": c["sector"],
                     "ip": site_ip, "stack": c["stack"], "type": "static",
                     "port": 80}
            sites_json.append(entry)
            site_map_rows.append(_map_row(s, entry))

        # Vulnerable apps (IPs .40..)
        for k, v in enumerate(vulns):
            site_ip = f"10.10.{i}.{40 + k}"
            services[f"{s}-vuln-{v['id']}"] = {
                "image": v["image"],
                "hostname": v["id"],
                "networks": {lan: {"ipv4_address": site_ip}},
                "profiles": profile,
                "restart": "unless-stopped",
            }
            entry = {"id": v["id"], "name": v["name"], "sector": v["sector"],
                     "ip": site_ip, "stack": v["stack"], "type": v["type"],
                     "port": v["port"]}
            sites_json.append(entry)
            site_map_rows.append(_map_row(s, entry))

        # Toolbox: traffic generator + attack/exploit runner.
        toolbox = {
            # network: host so the image build can reach package mirrors even
            # when the build sandbox's own DNS/bridge is misconfigured.
            "build": {"context": "./toolbox", "network": "host"},
            "image": TOOLBOX_IMAGE,
            "cap_add": ["NET_ADMIN", "NET_RAW"],
            "environment": {
                "STUDENT": s, "DESKTOP_IP": host_ip, "SEED": str(seed),
            },
            "volumes": ["./logs:/logs", f"./control/{s}:/control"],
            "profiles": profile,
            "restart": "unless-stopped",
        }
        if with_desktop:
            toolbox["network_mode"] = f"service:{s}-desktop"
            toolbox["depends_on"] = [f"{s}-desktop"]
        else:
            # headless: the toolbox IS the student's computer on the LAN
            toolbox["hostname"] = s
            toolbox["networks"] = {lan: {"ipv4_address": host_ip}}
        services[f"{s}-toolbox"] = toolbox

        # Capture: tcpdump, reusing the toolbox image. Shares the anchor's netns.
        # capture.sh picks the LAN interface (not -i any, which writes SLL2
        # frames nfstream cannot parse) and filters to the lab network.
        services[f"{s}-capture"] = {
            "image": TOOLBOX_IMAGE,
            "network_mode": f"service:{anchor}",
            "cap_add": ["NET_ADMIN", "NET_RAW"],
            "entrypoint": ["/opt/capture.sh"],
            "volumes": [f"./data/{s}:/pcap"],
            "depends_on": [anchor],
            "profiles": profile,
            "restart": "unless-stopped",
        }

        # Per-student control dir: phase flag + the student's site list.
        os.makedirs(f"control/{s}", exist_ok=True)
        with open(f"control/{s}/phase", "w") as f:
            f.write("idle\n")
        with open(f"control/{s}/sites.json", "w") as f:
            json.dump(sites_json, f, indent=2)
        os.makedirs(f"data/{s}", exist_ok=True)

        row = {"student": s, "persona": persona, "host_ip": host_ip,
               "sites": ";".join(e["id"] for e in sites_json)}
        if with_desktop:
            row = {"student": s, "url_port": port, "username": s,
                   "password": password, **row}
        students.append(row)

    return {"services": services, "networks": networks}, students, site_map_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=25)
    ap.add_argument("--base-port", type=int, default=30000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sites-per-student", type=int, default=5,
                    help="total targets per student (static + vulnerable)")
    ap.add_argument("--vuln-per-student", type=int, default=1,
                    help="how many of them are real vulnerable apps (0-2); "
                         "0 = lightest, no exploit phase")
    ap.add_argument("--with-desktop", action="store_true",
                    help="add the heavy browser GUI desktop per student "
                         "(default: headless, low-resource)")
    a = ap.parse_args()
    assert 1 <= a.start <= a.end <= 250

    compose, students, site_map = build(
        a.start, a.end, a.base_port, a.seed,
        a.sites_per_student, a.vuln_per_student, a.with_desktop)

    with open("docker-compose.yml", "w") as f:
        yaml.safe_dump(compose, f, sort_keys=False)
    os.makedirs("logs", exist_ok=True)

    with open("students.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(students[0].keys()))
        w.writeheader()
        w.writerows(students)
    with open("sites_map.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(site_map[0].keys()))
        w.writeheader()
        w.writerows(site_map)

    n = len(students)
    n_vuln = min(a.vuln_per_student, 2)
    mode = "with-desktop" if a.with_desktop else "headless"
    print(f"Wrote docker-compose.yml, students.csv, sites_map.csv for {n} students ({mode}).")
    print(f"Each student: {a.sites_per_student - n_vuln} static sites + "
          f"{n_vuln} vulnerable app(s), behind a profile.")
    print("Bring a student online:  docker compose --profile s001 up -d")
    if a.with_desktop:
        print("Keep students.csv private: it contains desktop passwords.")


if __name__ == "__main__":
    main()
