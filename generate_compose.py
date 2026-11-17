#!/usr/bin/env python3
"""
Generate docker-compose.yml for N students (source model, with vulnerable tier).

Each student gets:
  - desktop : a full Linux desktop in the browser (the student works here)
  - static company sites : lightweight nginx/apache containers on the student's
                           own isolated LAN (targets for scan / brute / flood).
  - vulnerable apps : real DVWA / Juice Shop containers (targets for the exploit
                      phase: SQLi, command injection, reverse shell + exfil).
  - toolbox : a Kali sidecar in the desktop's network namespace that generates
              the student's normal traffic and runs attacks / exploits on
              demand, sourced from the desktop IP and recorded by capture.
  - capture : tcpdump in the same namespace. Full payloads (-s 0) but FILTERED
              to the lab network (net 10.10.0.0/16), so the student's real
              internet browsing payloads are never recorded (privacy).

Every student's whole stack is behind a compose PROFILE named after the student
(s001, s002, ...), so only ACTIVE students consume resources. Bring one online
with:  docker compose --profile s001 up -d   (or scripts/session.sh s001 up)

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


def build(start, end, base_port, seed, n_sites, n_vuln):
    rnd = random.Random(seed)
    catalog = companies()
    vcatalog = vuln_apps()
    n_vuln = min(n_vuln, len(vcatalog))
    n_static = max(0, n_sites - n_vuln)
    services, networks, students, site_map_rows = {}, {}, [], []

    # Shared internet network for desktops. ICC disabled = desktops cannot
    # talk to each other, only to the internet.
    networks["wan"] = {
        "driver": "bridge",
        "driver_opts": {"com.docker.network.bridge.enable_icc": "false"},
        "ipam": {"config": [{"subnet": "172.30.0.0/16"}]},
    }

    for i in range(start, end + 1):
        s = sid(i)
        lan = f"{s}_lan"
        profile = [s]
        desktop_ip = f"10.10.{i}.10"
        password = secrets.token_urlsafe(9)
        port = base_port + i
        persona = PERSONAS[(i - 1) % len(PERSONAS)]

        # Deterministic per-student mix of companies (non-IID by site mix).
        srnd = random.Random(seed * 1000 + i)
        statics = srnd.sample(catalog, k=n_static)
        vulns = vcatalog[:n_vuln]               # dvwa first -> full exploit chain

        # internal: true -> no route to the internet. Attacks stay inside.
        networks[lan] = {
            "driver": "bridge",
            "internal": True,
            "ipam": {"config": [{"subnet": f"10.10.{i}.0/24"}]},
        }

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
            "ports": [f"{port}:3001"],          # HTTPS desktop in browser
            "volumes": [
                "./student:/config/Desktop/fllab:ro",
                # sibling (not nested) so the writable control mount does not
                # need a mountpoint created inside the read-only scripts mount
                f"./control/{s}:/config/Desktop/fllab-control",
            ],
            "networks": {"wan": {}, lan: {"ipv4_address": desktop_ip}},
            "profiles": profile,
            "restart": "unless-stopped",
        }

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
            svc = f"{s}-vuln-{v['id']}"
            spec = {
                "image": v["image"],
                "hostname": v["id"],
                "networks": {lan: {"ipv4_address": site_ip}},
                "profiles": profile,
                "restart": "unless-stopped",
            }
            services[svc] = spec
            entry = {"id": v["id"], "name": v["name"], "sector": v["sector"],
                     "ip": site_ip, "stack": v["stack"], "type": v["type"],
                     "port": v["port"]}
            sites_json.append(entry)
            site_map_rows.append(_map_row(s, entry))

        # Kali toolbox: normal-traffic generator + attack/exploit runner, in the
        # desktop's network namespace so its traffic is the student's traffic.
        services[f"{s}-toolbox"] = {
            # network: host so the image build can reach package mirrors even
            # when the build sandbox's own DNS/bridge is misconfigured.
            "build": {"context": "./toolbox", "network": "host"},
            "network_mode": f"service:{s}-desktop",
            "cap_add": ["NET_ADMIN", "NET_RAW"],
            "environment": {
                "STUDENT": s, "DESKTOP_IP": desktop_ip, "SEED": str(seed),
            },
            "volumes": ["./logs:/logs", f"./control/{s}:/control"],
            "depends_on": [f"{s}-desktop"],
            "profiles": profile,
            "restart": "unless-stopped",
        }

        services[f"{s}-capture"] = {
            "image": "nicolaka/netshoot",
            "network_mode": f"service:{s}-desktop",
            "cap_add": ["NET_ADMIN", "NET_RAW"],
            # -s 0: full payloads (needed for exploit/post-exploit detection).
            # Filter to the lab network so the student's real internet browsing
            # payloads are never captured. -G 3600: new pcap file every hour.
            "command": [
                "tcpdump", "-i", "any", "-n", "-s", "0", "-G", "3600",
                "-w", "/pcap/%Y%m%d-%H%M%S.pcap", "-Z", "root",
                "net", "10.10.0.0/16",
            ],
            "volumes": [f"./data/{s}:/pcap"],
            "depends_on": [f"{s}-desktop"],
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

        students.append({
            "student": s, "url_port": port, "username": s,
            "password": password, "persona": persona,
            "desktop_ip": desktop_ip,
            "sites": ";".join(e["id"] for e in sites_json),
        })

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
                    help="how many of them are real vulnerable apps (max 2)")
    a = ap.parse_args()
    assert 1 <= a.start <= a.end <= 250

    compose, students, site_map = build(
        a.start, a.end, a.base_port, a.seed,
        a.sites_per_student, a.vuln_per_student)

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
    print(f"Wrote docker-compose.yml, students.csv, sites_map.csv for {n} students.")
    print(f"Each student: {a.sites_per_student - n_vuln} static sites + "
          f"{n_vuln} vulnerable app(s), behind a profile.")
    print("Bring a student online:  docker compose --profile s001 up -d")
    print("Keep students.csv private: it contains passwords.")


if __name__ == "__main__":
    main()
