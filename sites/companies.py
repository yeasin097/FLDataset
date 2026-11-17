#!/usr/bin/env python3
"""
Catalog of simulated company websites (the "organizations").

Each company is one identity that is SHARED across the whole lab: company
`bank-meridian` is the same organization for every student who gets it, so
after collection you can merge all students' flows toward that company into a
single federated "organization" dataset.

Only a handful of these run at any moment: each student session brings ~5 of
them online on that student's isolated LAN. So the catalog can be large and
varied while the running footprint stays small.

Per-company attributes are derived deterministically from the company id, so
the generated sites and the compose file always agree (same pages, same hidden
paths, same server stack) no matter when they are regenerated.
"""
import random

# (id, display name, sector)  --  52 companies across distinct sectors.
_COMPANIES = [
    ("bank-meridian",      "Meridian Trust Bank",        "finance"),
    ("ins-safeharbor",     "SafeHarbor Insurance",       "insurance"),
    ("shop-bazaario",      "Bazaario Online Store",      "ecommerce"),
    ("health-vitacare",    "VitaCare Clinic",            "healthcare"),
    ("edu-northgate",      "Northgate University",       "education"),
    ("gov-rivermouth",     "City of Rivermouth Portal",  "government"),
    ("news-ledger",        "The Daily Ledger",           "news"),
    ("air-skyroute",       "SkyRoute Airlines",          "airline"),
    ("hotel-grandvista",   "Grand Vista Hotels",         "hospitality"),
    ("log-swiftcargo",     "SwiftCargo Logistics",       "logistics"),
    ("realty-homenest",    "HomeNest Realty",            "realestate"),
    ("law-brackenridge",   "Brackenridge Law Group",     "legal"),
    ("mfg-ironworks",      "IronWorks Manufacturing",    "manufacturing"),
    ("energy-voltedge",    "VoltEdge Energy",            "energy"),
    ("tel-nexlink",        "Nexlink Telecom",            "telecom"),
    ("saas-clouddesk",     "CloudDesk SaaS",             "saas"),
    ("game-pixelforge",    "PixelForge Games",           "gaming"),
    ("media-streamwave",   "StreamWave Media",           "streaming"),
    ("social-connectly",   "Connectly Social",           "socialmedia"),
    ("food-quickbite",     "QuickBite Delivery",         "fooddelivery"),
    ("rest-olivethyme",    "Olive & Thyme Bistro",       "restaurant"),
    ("retail-urbanmart",   "UrbanMart Retail",           "retail"),
    ("auto-driveline",     "DriveLine Motors",           "automotive"),
    ("pharma-novapharm",   "NovaPharm Labs",             "pharma"),
    ("bio-genesphere",     "GeneSphere Biotech",         "biotech"),
    ("consult-apex",       "Apex Consulting Group",      "consulting"),
    ("acct-ledgerline",    "Ledgerline Accountants",     "accounting"),
    ("hr-peoplefirst",     "PeopleFirst HR",             "hr"),
    ("recruit-talentbridge","TalentBridge Recruiting",   "recruiting"),
    ("learn-brightpath",   "BrightPath Learning",        "elearning"),
    ("ngo-greenroots",     "GreenRoots Foundation",      "nonprofit"),
    ("travel-wanderlust",  "Wanderlust Travel",          "travel"),
    ("fit-pulsefit",       "PulseFit Gyms",              "fitness"),
    ("fashion-vellora",    "Vellora Fashion",            "fashion"),
    ("jewel-luxecarat",    "Luxe & Carat Jewelers",      "jewelry"),
    ("elec-circuitcity",   "CircuitCity Electronics",    "electronics"),
    ("book-pageturner",    "PageTurner Books",           "bookstore"),
    ("music-soundscape",   "Soundscape Records",         "music"),
    ("photo-lumenlens",    "LumenLens Studio",           "photography"),
    ("arch-formworks",     "FormWorks Architects",       "architecture"),
    ("build-keystone",     "Keystone Construction",      "construction"),
    ("agri-harvestfields", "Harvest Fields Agro",        "agriculture"),
    ("ship-portside",      "PortSide Shipping",          "shipping"),
    ("crypto-blockvault",  "BlockVault Exchange",        "crypto"),
    ("fintech-paystream",  "PayStream Fintech",          "fintech"),
    ("mkt-brightwave",     "BrightWave Marketing",       "marketing"),
    ("pub-inkpress",       "InkPress Publishing",        "publishing"),
    ("sec-sentinelguard",  "SentinelGuard Security",     "security"),
    ("cloud-nimbus",       "Nimbus Cloud Services",      "cloud"),
    ("iot-smarthome",      "SmartHome IoT",              "iot"),
    ("dc-corestack",       "CoreStack Datacenter",       "datacenter"),
    ("travelagency-globetrek","GlobeTrek Tours",         "travel"),
]

# Real vulnerable web apps. Each is ONE organization shared across every
# student who draws it (e.g. all students' DVWA traffic merges into one "DVWA"
# org). These are the targets of the exploit phase: real SQL injection, command
# injection, and a reverse shell / exfil post-exploitation stage. Listed first
# -> dvwa, which supports the full chain incl. the reverse shell.
VULN_APPS = [
    {"id": "vuln-dvwa", "name": "Damn Vulnerable Web App",
     "sector": "vulnerable-webapp", "image": "vulnerables/web-dvwa",
     "port": 80, "type": "dvwa", "stack": "php"},
    {"id": "vuln-juiceshop", "name": "OWASP Juice Shop",
     "sector": "vulnerable-webapp", "image": "bkimminich/juice-shop",
     "port": 3000, "type": "juiceshop", "stack": "node"},
]


def vuln_apps():
    return [dict(a) for a in VULN_APPS]


# Web server image used per company -> gives two genuinely different HTTP
# server fingerprints (Server: nginx vs Server: Apache) in the captured traffic.
STACKS = {
    "nginx":  {"image": "nginx:alpine",  "docroot": "/usr/share/nginx/html"},
    "apache": {"image": "httpd:alpine",  "docroot": "/usr/local/apache2/htdocs"},
}

# Pool of "interesting" paths a scanner/dir-brute-force might discover.
# A random subset is actually served by each site (the rest 404) so that
# directory brute force produces realistic hit/miss patterns.
_HIDDEN_POOL = [
    "admin", "login", "config", "backup", "uploads", "api", "docs",
    "phpmyadmin", "server-status", "test", "old", "dev", "staging",
    "db", "internal", "portal", "dashboard", "setup.php",
]

# Extra per-sector landing pages (on top of the common pages) so page count
# and total site size differ by sector -> varied flow byte/packet features.
_SECTOR_PAGES = {
    "finance":   ["accounts", "loans", "cards", "transfers"],
    "ecommerce": ["products", "cart", "checkout", "deals", "category"],
    "healthcare":["appointments", "doctors", "services", "patients"],
    "education": ["courses", "admissions", "faculty", "library"],
    "news":      ["world", "business", "sports", "opinion", "tech"],
    "airline":   ["booking", "checkin", "destinations", "fares"],
    "saas":      ["pricing", "features", "docs", "status", "api"],
    "gaming":    ["games", "store", "leaderboard", "community"],
    "streaming": ["browse", "movies", "series", "live"],
    "government":["services", "permits", "records", "notices"],
}


def _rng(cid):
    return random.Random("company:" + cid)


def companies():
    """Return the full catalog as a list of dicts with derived attributes."""
    out = []
    for idx, (cid, name, sector) in enumerate(_COMPANIES):
        r = _rng(cid)
        stack = "nginx" if idx % 2 == 0 else "apache"
        pages = ["about", "contact", "services", "news", "login"]
        pages += _SECTOR_PAGES.get(sector, ["products", "team", "faq"])
        # Content scale 1..4 -> how much filler text per page (page byte size).
        scale = r.randint(1, 4)
        # Number of secondary articles/listing pages (more pages = more flows).
        articles = r.randint(3, 12)
        hidden = r.sample(_HIDDEN_POOL, r.randint(3, 6))
        out.append({
            "id": cid,
            "name": name,
            "sector": sector,
            "stack": stack,              # nginx | apache
            "image": STACKS[stack]["image"],
            "docroot": STACKS[stack]["docroot"],
            "pages": pages,
            "scale": scale,
            "articles": articles,
            "hidden": hidden,
        })
    return out


def by_id():
    return {c["id"]: c for c in companies()}


if __name__ == "__main__":
    cs = companies()
    print(f"{len(cs)} companies")
    for c in cs:
        print(f"  {c['id']:24} {c['stack']:6} {c['sector']:13} "
              f"pages={len(c['pages'])+c['articles']:2} hidden={len(c['hidden'])}")
