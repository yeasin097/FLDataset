#!/usr/bin/env python3
"""
Runs attacks against each student's desktop at random times and writes the
ground-truth labels to /logs/attacks.csv.

Non-IID by design: each student gets their own subset of attack types,
and some students get no attacks at all.
"""
import csv, os, random, socket, subprocess, threading, time
from datetime import datetime, timezone

START, END = int(os.environ["START"]), int(os.environ["END"])
SEED = int(os.environ.get("SEED", "42"))
MIN_GAP, MAX_GAP = 20 * 60, 60 * 60          # seconds between attacks
BENIGN_ONLY_SHARE = 0.10                     # 10% of students never attacked

ATTACKS = {
    "portscan":       lambda t: ["nmap", "-sS", "-T3", "-p", "1-10000", t],
    "ssh_bruteforce": lambda t: ["hydra", "-L", "/opt/lists/users.txt",
                                 "-P", "/opt/lists/passwords.txt",
                                 "-t", "4", "-f", f"ssh://{t}:2222"],
    "syn_flood":      lambda t: ["timeout", "60", "hping3", "-S", "-p", "80",
                                 "-i", "u2000", t],         # ~500 pkt/s, 60 s
    "web_scan":       lambda t: ["nikto", "-h", f"http://{t}", "-maxtime", "300s"],
    "dir_bruteforce": lambda t: ["gobuster", "dir", "-u", f"http://{t}",
                                 "-w", "/opt/lists/dirs.txt", "-q"],
}

LOG = "/logs/attacks.csv"
lock = threading.Lock()

def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def log(row):
    with lock:
        new = not os.path.exists(LOG)
        with open(LOG, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["student", "attack", "src_ip", "dst_ip",
                            "start_utc", "end_utc", "exit_code"])
            w.writerow(row)

def is_up(ip):
    try:
        with socket.create_connection((ip, 80), timeout=3):
            return True
    except OSError:
        return False

def student_loop(i):
    rnd = random.Random(SEED * 1000 + i)
    s, target, src = f"s{i:03d}", f"10.10.{i}.10", f"10.10.{i}.66"
    if rnd.random() < BENIGN_ONLY_SHARE:
        print(f"{s}: benign-only student"); return
    allowed = rnd.sample(sorted(ATTACKS), k=rnd.randint(2, 4))
    print(f"{s}: attack types {allowed}")
    time.sleep(rnd.uniform(0, MAX_GAP))       # spread out the first attacks
    while True:
        if is_up(target):                     # only attack while desktop runs
            name = rnd.choice(allowed)
            t0 = now()
            r = subprocess.run(ATTACKS[name](target),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log([s, name, src, target, t0, now(), r.returncode])
        time.sleep(rnd.uniform(MIN_GAP, MAX_GAP))

for i in range(START, END + 1):
    threading.Thread(target=student_loop, args=(i,), daemon=True).start()
while True:
    time.sleep(3600)
