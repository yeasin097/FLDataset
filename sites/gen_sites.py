#!/usr/bin/env python3
"""
Generate the static content for every company in the catalog, one directory per
company under sites/content/<id>/. These directories are mounted read-only into
lightweight nginx/apache containers at runtime, so no custom image build and no
per-site Docker image are needed.

Each generated site has:
  - a themed home page + common pages + sector pages + N article pages
    (page count and size vary by company -> varied flow features),
  - assets/style.css and assets/logo.svg (extra sub-resource requests),
  - a /login page with a real <form method=post> (target for login brute force),
  - robots.txt advertising some disallowed paths,
  - a random subset of "sensitive" directories actually served (admin/, backup/,
    api/, ...) so directory brute force gets realistic 200/404 patterns.

Run once on the host before `docker compose up`:
    python3 sites/gen_sites.py
"""
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)              # so `companies` imports whatever the cwd
from companies import companies       # noqa: E402  (works from any directory)

CONTENT = os.path.join(HERE, "content")

_LOREM = (
    "We deliver reliable solutions for our customers across the region. "
    "Our team combines decades of experience with modern technology to keep "
    "operations running smoothly and securely every single day. "
)


def _filler(scale, r):
    return "<p>" + (_LOREM * (scale * r.randint(2, 5))) + "</p>"


def _page(company, title, body, nav):
    name = company["name"]
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | {name}</title>
<link rel="stylesheet" href="/assets/style.css">
</head><body>
<header><img src="/assets/logo.svg" alt="logo" class="logo"><h1>{name}</h1>
<nav>{nav}</nav></header>
<main><h2>{title}</h2>
{body}
</main>
<footer><small>&copy; 2026 {name}. All rights reserved. Sector: {company['sector']}.</small></footer>
</body></html>
"""


def _nav(pages):
    links = ['<a href="/">Home</a>']
    for p in pages:
        links.append(f'<a href="/{p}.html">{p.title()}</a>')
    return " · ".join(links)


def _login_page(company):
    # Contains the literal token "login-form" so an Apache-served login.html
    # gives hydra a stable failure string; nginx sites override /login in conf.
    name = company["name"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Sign in | {name}</title>
<link rel="stylesheet" href="/assets/style.css"></head><body>
<header><h1>{name}</h1></header>
<main><h2>Staff / Customer Login</h2>
<form class="login-form" method="post" action="/login">
  <label>Username <input type="text" name="username"></label>
  <label>Password <input type="password" name="password"></label>
  <button type="submit">Sign in</button>
</form>
<p class="hint">Authorized users only.</p>
</main></body></html>
"""


def _css(r):
    hue = r.randint(0, 359)
    return f""":root{{--brand:hsl({hue},55%,42%)}}
*{{box-sizing:border-box}}
body{{font-family:system-ui,Arial,sans-serif;margin:0;color:#1a1a1a;background:#f6f7f9}}
header{{background:var(--brand);color:#fff;padding:18px 24px}}
header h1{{margin:.2em 0}}
nav a{{color:#fff;text-decoration:none}}
main{{max-width:900px;margin:24px auto;padding:0 20px}}
.logo{{height:34px;vertical-align:middle;margin-right:10px}}
footer{{color:#666;text-align:center;padding:30px}}
.login-form label{{display:block;margin:8px 0}}
button{{background:var(--brand);color:#fff;border:0;padding:10px 16px;border-radius:6px}}
"""


def _logo(r):
    hue = r.randint(0, 359)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="34" height="34">'
            f'<rect width="34" height="34" rx="7" fill="hsl({hue},60%,45%)"/>'
            f'<circle cx="17" cy="17" r="8" fill="#fff" opacity=".85"/></svg>')


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_site(company):
    r = random.Random("content:" + company["id"])
    root = os.path.join(CONTENT, company["id"])
    if os.path.isdir(root):
        shutil.rmtree(root)
    pages = company["pages"]
    nav = _nav(pages[:6])

    # Home page
    body = _filler(company["scale"], r) + "<ul>" + "".join(
        f'<li><a href="/article-{i}.html">Update {i}</a></li>'
        for i in range(1, company["articles"] + 1)) + "</ul>"
    write(os.path.join(root, "index.html"), _page(company, "Home", body, nav))

    # Common + sector pages
    for p in pages:
        if p == "login":
            write(os.path.join(root, "login.html"), _login_page(company))
        else:
            write(os.path.join(root, f"{p}.html"),
                  _page(company, p.title(), _filler(company["scale"], r), nav))

    # Article pages (bulk of the varied page count / size)
    for i in range(1, company["articles"] + 1):
        write(os.path.join(root, f"article-{i}.html"),
              _page(company, f"Update {i}", _filler(company["scale"], r), nav))

    # Assets
    write(os.path.join(root, "assets", "style.css"), _css(r))
    write(os.path.join(root, "assets", "logo.svg"), _logo(r))

    # robots.txt advertises some (not all) hidden paths
    advertised = company["hidden"][: max(2, len(company["hidden"]) // 2)]
    robots = "User-agent: *\n" + "".join(
        f"Disallow: /{h}/\n" for h in advertised)
    write(os.path.join(root, "robots.txt"), robots)

    # Served "sensitive" directories (dir brute force finds these; others 404)
    for h in company["hidden"]:
        if h.endswith(".php"):
            write(os.path.join(root, h),
                  "<?php /* setup placeholder */ echo 'setup'; ?>")
        else:
            write(os.path.join(root, h, "index.html"),
                  _page(company, f"/{h}", "<p>Restricted area. Authorized personnel only.</p>", nav))

    return len(pages) + company["articles"]


def main():
    cs = companies()
    os.makedirs(CONTENT, exist_ok=True)
    total = 0
    for c in cs:
        n = build_site(c)
        total += n
    print(f"Generated {len(cs)} company sites under {CONTENT} "
          f"({total} HTML pages total).")


if __name__ == "__main__":
    main()
