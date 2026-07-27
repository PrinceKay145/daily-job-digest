#!/usr/bin/env python3
"""
Daily job scraper for Ridwan A. Adebayo.

Pulls ML / AI / Data / LLM roles from a set of live job sources, filters them
against a keyword profile built from Ridwan's CV, drops seniority-mismatched
and already-seen roles, and emails a clean digest.

Designed to run once per day via GitHub Actions (see .github/workflows/daily-jobs.yml)
but runs fine locally too:  python scrape_jobs.py            (sends email)
                            python scrape_jobs.py --dry-run  (prints, no email)

Requires:  requests   (see requirements.txt)
Secrets (env vars):  EMAIL_FROM, EMAIL_APP_PASSWORD   (Gmail + app password)
Optional env vars:   EMAIL_TO (defaults to princekay145@gmail.com)
"""

import os
import re
import sys
import json
import html
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests


def _load_dotenv():
    """Load KEY=VALUE lines from a local .env, for running by hand.

    Real environment variables always win, so this is a no-op on GitHub Actions
    (where the secrets arrive as env vars and no .env file exists). Deliberately
    hand-rolled rather than pulling in python-dotenv — `requests` stays the only
    dependency. .env is gitignored; never commit it.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG  — edit freely. This is the only part you normally touch.
# ─────────────────────────────────────────────────────────────────────────────

# A title must contain at least ONE of these to be considered.
INCLUDE = [
    "machine learning", "ml engineer", "ml-engineer", "ml/", "/ml",
    "ai engineer", "ai-engineer", "applied ai", "ai developer", "ai/ml",
    "data scientist", "data science", "data analyst", "data engineer",
    "llm", "nlp", "rag", "genai", "generative ai", "gen ai",
    "mlops", "analytics engineer", "research engineer", "ml intern",
    "ai intern", "ml researcher", "аналитик данных", "машинн", "нейросет",
    "data science", "дата-сайентист", "data-scientist", "ии-инженер",
    "ai automation", "quant",
    # NOTE: bare "python" was removed after measuring it — it matched 22 roles,
    # 19 of them plain backend/infra Python engineering (12 from Canonical alone).
    # Precision-first per CLAUDE.md. Re-add it here if you want that firehose back.
    # "prompt" was likewise narrowed to "prompt engineer" (bare "prompt" pulled
    # in copywriting roles). "quant" was measured and kept: 3/3 were real fits.
    "prompt engineer",
]

# A title containing ANY of these is dropped (too senior / not a fit).
EXCLUDE = [
    "senior", "staff", "principal", "lead ", " lead", "head of", "head,",
    "director", "chief", " vp", "vp,", "architect", "manager", "руководител",
    "тимлид", "ведущий", "старший", "sales", "продаж", "маркет", "recruiter",
    "account executive", "solutions consultant", "customer success",
    "sdr", "business developer", "bd ", "counsel", "legal",
]

# ── Second track: entry-level support & sales ────────────────────────────────
# These roles are deliberately dropped by EXCLUDE above (they aren't ML work),
# so they get their own include/exclude pair and land in a separate section at
# the bottom of the digest. Two extra rules apply to this track only:
#   1. seniority gate is stricter — entry level only
#   2. the posting must have a KNOWN date within SUPPORT_FRESH_DAYS.
#      No date = not shown. This is why web3.career and hh.ru never appear in
#      this section: neither exposes a posting date to scrape.
SUPPORT_FRESH_DAYS = 7

SUPPORT_INCLUDE = [
    # customer / technical support
    "customer support", "customer service", "customer care", "customer experience",
    "client support", "client services", "technical support", "tech support",
    "support specialist", "support agent", "support representative",
    "support associate", "support engineer", "support advocate",
    "helpdesk", "help desk", "service desk", "it support", "desktop support",
    "player support", "community support", "onboarding specialist",
    "поддержк", "техподдержк", "оператор call",
    # entry-level sales
    "sales development", "business development representative",
    "inside sales", "sales representative", "sales associate", "sales assistant",
    "sales agent", "lead generation", "менеджер по продажам",
]

# Stricter seniority gate for the support track. Note this list deliberately
# omits the bare "lead " / " lead" from EXCLUDE — that would kill every
# "Lead Generation Specialist" posting, which is exactly an entry-level sales role.
SUPPORT_EXCLUDE = [
    "senior", "staff", "principal", "head of", "head,", "director", "chief",
    "vp,", " vp", "manager", "team lead", "teamlead", "tech lead", "supervisor",
    "architect", "partner", "руководител", "тимлид", "ведущий", "старший",
    "sales engineer", "solutions consultant", "recruiter", "counsel", "legal",
]

# Location buckets → used only for tagging, never for exclusion
# (Ridwan is open to Russia AND overseas).
WORLDWIDE_HINTS = ["worldwide", "anywhere", "global", "emea",
                   "africa", "nigeria"]
RUSSIA_HINTS = ["russia", "росси", "москв", "moscow", "spb", "санкт"]

RECIPIENT = os.environ.get("EMAIL_TO", "princekay145@gmail.com")

# hh.ru text queries (Russian market). schedule=remote pulls remote-only.
HH_QUERIES = ["ML engineer", "LLM", "Data Scientist", "AI engineer",
              "аналитик данных", "NLP", "MLOps", "AI automation"]

# Greenhouse boards worth watching (token -> friendly name)
GREENHOUSE = {
    "canonical": "Canonical (Ubuntu)",
    "scaleai": "Scale AI",
    "turing": "Turing",
    "snorkelai": "Snorkel AI",
    "toloka": "Toloka",
}
# Lever boards
LEVER = {"binance": "Binance"}
# Ashby boards
ASHBY = {"mercor": "Mercor", "weaviate": "Weaviate"}

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/126 Safari/537.36"),
      "Accept-Language": "en-US,en;q=0.9,ru;q=0.8"}

SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")
TIMEOUT = 45

# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def clean(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", s or ""))).strip()

def match_term(title, include, exclude):
    """Return the include-term that fired, or None. Exclude always wins."""
    t = (title or "").lower()
    if any(k in t for k in exclude):
        return None
    for k in include:
        if k in t:
            return k
    return None

def title_ok(title):
    return match_term(title, INCLUDE, EXCLUDE) is not None

def parse_date(s):
    """Best-effort epoch / ISO / 'YYYY-MM-DD hh:mm:ss UTC' → date. None if unparseable."""
    if s in (None, ""):
        return None
    s = str(s).strip()
    if s.isdigit():                       # epoch seconds, or milliseconds (Lever)
        n = int(s)
        if n > 10_000_000_000:
            n //= 1000
        try:
            return datetime.datetime.fromtimestamp(n, datetime.timezone.utc).date()
        except (OSError, OverflowError, ValueError):
            return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime.date(*(int(x) for x in m.groups()))
        except ValueError:
            return None
    return None

def loc_tag(text):
    t = (text or "").lower()
    if any(h in t for h in RUSSIA_HINTS):
        return "🇷🇺 Russia"
    if any(h in t for h in WORLDWIDE_HINTS):
        if "united states" in t or "u.s. only" in t or "us only" in t:
            return "US/remote"
        return "🌍 worldwide/remote"
    return "remote?"

def job(source, title, company, url, location="", salary="", date=""):
    d = parse_date(date)
    return {"source": source, "title": clean(title), "company": clean(company),
            "url": url, "location": clean(location), "salary": salary,
            "date": d.isoformat() if d else "",
            "age_days": max(0, (datetime.date.today() - d).days) if d else None,
            "loc_tag": loc_tag(f"{title} {location}")}

# ─────────────────────────────────────────────────────────────────────────────
# sources — each returns a list of job dicts; each is defensively wrapped
# ─────────────────────────────────────────────────────────────────────────────

def src_remotive():
    out = []
    for term in ["machine learning", "data science", "ai engineer",
                 "data analyst", "llm", "nlp",
                 # support/sales track
                 "customer support", "technical support", "sales development"]:
        r = requests.get("https://remotive.com/api/remote-jobs",
                         params={"search": term, "limit": 60},
                         headers=UA, timeout=TIMEOUT)
        for j in r.json().get("jobs", []):
            out.append(job("Remotive", j.get("title"), j.get("company_name"),
                           j.get("url"), j.get("candidate_required_location", ""),
                           "", (j.get("publication_date") or "")[:10]))
    return out

def src_remoteok():
    out = []
    for tag in ["machine-learning", "ai", "data-science", "data-analyst",
                "python", "nlp", "llm",
                # support/sales track
                "customer-support", "support", "sales"]:
        r = requests.get(f"https://remoteok.com/api?tag={tag}", headers=UA, timeout=TIMEOUT)
        data = r.json()
        for j in data[1:]:
            out.append(job("RemoteOK", j.get("position"), j.get("company"),
                           j.get("url"), j.get("location", ""),
                           "", j.get("epoch") or (j.get("date") or "")[:10]))
    return out

def src_himalayas():
    out = []
    for off in range(0, 400, 100):
        r = requests.get("https://himalayas.app/jobs/api",
                         params={"limit": 100, "offset": off}, headers=UA, timeout=TIMEOUT)
        js = r.json().get("jobs", [])
        if not js:
            break
        for j in js:
            loc = j.get("locationRestrictions", "")
            if isinstance(loc, list):
                loc = ", ".join(str(x) for x in loc)
            loc = str(loc).strip("[]'\"")
            out.append(job("Himalayas", j.get("title"), j.get("companyName"),
                           j.get("applicationLink"), loc, "",
                           j.get("pubDate")))
    return out

def src_tether():
    out = []
    r = requests.get("https://tether.recruitee.com/api/offers/", headers=UA, timeout=TIMEOUT)
    seen = set()
    for o in r.json().get("offers", []):
        t = o.get("title", "")
        if t in seen:
            continue
        seen.add(t)
        out.append(job("Tether", t, "Tether", o.get("careers_url"),
                       o.get("location", "Remote"), "",
                       o.get("published_at") or o.get("created_at")))
    return out

def src_greenhouse():
    out = []
    for token, name in GREENHOUSE.items():
        try:
            data = None
            for attempt in range(2):
                r = requests.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                    headers=UA, timeout=TIMEOUT)
                try:
                    data = r.json()
                    break
                except Exception:
                    continue
            for j in (data or {}).get("jobs", []):
                out.append(job(name, j.get("title"), name,
                               j.get("absolute_url"),
                               j.get("location", {}).get("name", ""), "",
                               j.get("first_published") or j.get("updated_at")))
        except Exception as e:
            print(f"  [greenhouse:{token}] {e}", file=sys.stderr)
    return out

def src_lever():
    out = []
    for token, name in LEVER.items():
        try:
            r = requests.get(f"https://api.lever.co/v0/postings/{token}?mode=json",
                             headers=UA, timeout=TIMEOUT)
            for j in r.json():
                cats = j.get("categories", {})
                out.append(job(name, j.get("text"), name, j.get("hostedUrl"),
                               f"{cats.get('location','')} {cats.get('team','')}",
                               "", j.get("createdAt")))
        except Exception as e:
            print(f"  [lever:{token}] {e}", file=sys.stderr)
    return out

def src_ashby():
    out = []
    for token, name in ASHBY.items():
        try:
            r = requests.get(
                f"https://api.ashbyhq.com/posting-api/job-board/{token}",
                headers=UA, timeout=TIMEOUT)
            for j in r.json().get("jobs", []):
                loc = j.get("location", "")
                if j.get("isRemote"):
                    loc += " remote"
                out.append(job(name, j.get("title"), name, j.get("jobUrl"), loc,
                               "", j.get("publishedAt")))
        except Exception as e:
            print(f"  [ashby:{token}] {e}", file=sys.stderr)
    return out

def src_web3career():
    out = []
    for page in ["ai-jobs", "machine-learning-jobs", "data-jobs", "python-jobs"]:
        try:
            r = requests.get(f"https://web3.career/{page}", headers=UA, timeout=TIMEOUT)
            for row in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S):
                h = re.search(r'href="(/[^"]+)"[^>]*>\s*<h2[^>]*>(.*?)</h2>', row, re.S)
                if not h:
                    continue
                comp = re.search(r"<h3[^>]*>(.*?)</h3>", row, re.S)
                full = clean(row)
                if "remote" not in full.lower():
                    continue
                out.append(job("web3.career", h.group(2),
                               comp.group(1) if comp else "",
                               "https://web3.career" + h.group(1), "remote"))
        except Exception as e:
            print(f"  [web3:{page}] {e}", file=sys.stderr)
    return out

def src_hh():
    """hh.ru — Russian market, remote filter. May 403 from some IPs; degrades safely."""
    out = []
    from urllib.parse import quote
    for q in HH_QUERIES:
        for exp in ["noExperience", "between1And3"]:
            try:
                url = ("https://hh.ru/search/vacancy?text=" + quote(q) +
                       "&schedule=remote&experience=" + exp +
                       "&order_by=publication_time&per_page=20")
                r = requests.get(url, headers=UA, timeout=TIMEOUT)
                if r.status_code != 200:
                    continue
                for m in re.finditer(
                        r'data-qa="serp-item__title[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                        r.text, re.S):
                    link = m.group(1).split("?")[0]
                    out.append(job("hh.ru", m.group(2), "", link, "Russia"))
            except Exception as e:
                print(f"  [hh:{q}:{exp}] {e}", file=sys.stderr)
    return out

SOURCES = [
    ("Remotive", src_remotive),
    ("RemoteOK", src_remoteok),
    ("Himalayas", src_himalayas),
    ("Tether", src_tether),
    ("Greenhouse", src_greenhouse),
    ("Lever", src_lever),
    ("Ashby", src_ashby),
    ("web3.career", src_web3career),
    ("hh.ru", src_hh),
]

# ─────────────────────────────────────────────────────────────────────────────
# pipeline
# ─────────────────────────────────────────────────────────────────────────────

def classify(j):
    """Tag a job as the 'ml' track, the 'support' track, or None (dropped).

    The ML track wins any overlap. The support track additionally requires a
    known posting date no older than SUPPORT_FRESH_DAYS — stale or undated
    support/sales roles are not worth anyone's inbox.
    """
    term = match_term(j["title"], INCLUDE, EXCLUDE)
    if term:
        return "ml", term
    term = match_term(j["title"], SUPPORT_INCLUDE, SUPPORT_EXCLUDE)
    if term and j["age_days"] is not None and j["age_days"] <= SUPPORT_FRESH_DAYS:
        return "support", term
    return None, None

def collect():
    all_jobs = {}
    for name, fn in SOURCES:
        try:
            got = fn()
            kept = 0
            for j in got:
                if not j["url"]:
                    continue
                track, term = classify(j)
                if not track:
                    continue
                j["track"], j["why"] = track, term
                all_jobs[j["url"]] = j
                kept += 1
            print(f"[{name}] pulled {len(got)}, matched {kept}")
        except Exception as e:
            print(f"[{name}] FAILED: {e}", file=sys.stderr)
    return list(all_jobs.values())

def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=0)

LOC_ORDER = {"🌍 worldwide/remote": 0, "US/remote": 1, "🇷🇺 Russia": 2, "remote?": 3}

def _row(j, show_age=False):
    sal = f' · <span style="color:#0a7">{j["salary"]}</span>' if j["salary"] else ""
    loc = f' · {j["location"]}' if j["location"] else ""
    age = ""
    if show_age and j["age_days"] is not None:
        age = (' · <span style="color:#c60;">today</span>' if j["age_days"] == 0
               else f' · <span style="color:#c60;">{j["age_days"]}d ago</span>')
    return (f'<tr><td style="padding:8px 10px;border-bottom:1px solid #eee;">'
            f'<a href="{j["url"]}" style="color:#1155cc;text-decoration:none;font-weight:600;">'
            f'{html.escape(j["title"])}</a><br>'
            f'<span style="color:#555;font-size:13px;">{html.escape(j["company"])} · '
            f'{j["loc_tag"]}{loc}{sal}{age} · <i>{j["source"]}</i></span></td></tr>')

def build_email(new_jobs):
    ml = [j for j in new_jobs if j["track"] == "ml"]
    support = [j for j in new_jobs if j["track"] == "support"]
    ml.sort(key=lambda j: (LOC_ORDER.get(j["loc_tag"], 9), j["source"], j["title"]))
    # support section is about freshness, so newest first
    support.sort(key=lambda j: (j["age_days"], LOC_ORDER.get(j["loc_tag"], 9), j["title"]))
    today = datetime.date.today().strftime("%A, %d %B %Y")

    parts = [
        f'<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:680px;margin:auto;">',
        f'<h2 style="color:#222;">Job digest — {today}</h2>',
        f'<p style="color:#555;">{len(ml)} new ML/AI/data role(s) matching your profile. '
        f'Sorted worldwide-remote first.</p>',
        f'<table style="width:100%;border-collapse:collapse;">'
        f'{"".join(_row(j) for j in ml)}</table>',
    ]
    if support:
        parts += [
            f'<h3 style="color:#222;margin-top:32px;border-top:2px solid #ddd;padding-top:18px;">'
            f'Entry-level support &amp; sales</h3>',
            f'<p style="color:#555;font-size:13px;">{len(support)} role(s), posted in the last '
            f'{SUPPORT_FRESH_DAYS} days. Fallback / bridge income; newest first.</p>',
            f'<table style="width:100%;border-collapse:collapse;">'
            f'{"".join(_row(j, show_age=True) for j in support)}</table>',
        ]
    parts.append(
        f'<p style="color:#999;font-size:12px;margin-top:20px;">'
        f'Auto-generated. Edit keywords/sources in scrape_jobs.py. '
        f'Seniority-filtered; verify each posting is still open before applying.</p></div>')
    return "".join(parts)

def send_email(subject, body):
    frm = os.environ.get("EMAIL_FROM")
    # Google displays app passwords as 4 space-separated groups; SMTP wants the
    # bare 16 characters, so paste it either way and this normalises it.
    pw = (os.environ.get("EMAIL_APP_PASSWORD") or "").replace(" ", "")
    if not frm or not pw:
        print("EMAIL_FROM / EMAIL_APP_PASSWORD not set — cannot send.", file=sys.stderr)
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = frm
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(frm, pw)
        s.sendmail(frm, [RECIPIENT], msg.as_string())
    print(f"Email sent to {RECIPIENT}")
    return True

def main():
    dry = "--dry-run" in sys.argv
    jobs = collect()
    seen = load_seen()
    new = [j for j in jobs if j["url"] not in seen]
    print(f"\nTotal matched: {len(jobs)} | already seen: {len(jobs)-len(new)} | NEW: {len(new)}")

    if not new:
        print("Nothing new today — no email sent.")
        return

    n_ml = sum(1 for j in new if j["track"] == "ml")
    n_sup = len(new) - n_ml
    body = build_email(new)
    subject = f"[Jobs] {n_ml} new AI/ML/data role(s)"
    if n_sup:
        subject += f" + {n_sup} support/sales"
    subject += f" — {datetime.date.today():%d %b}"

    if dry:
        print("\n--- DRY RUN: email NOT sent ---")
        for track, label in (("ml", "ML / AI / DATA"),
                             ("support", f"ENTRY-LEVEL SUPPORT & SALES (≤{SUPPORT_FRESH_DAYS}d old)")):
            rows = [j for j in new if j["track"] == track]
            print(f"\n### {label} — {len(rows)}")
            for j in sorted(rows, key=lambda x: (LOC_ORDER.get(x["loc_tag"], 9), x["title"])):
                age = f"{j['age_days']}d" if j["age_days"] is not None else "  ?"
                print(f"  {j['loc_tag']:22} {age:>4} {j['title'][:50]:50} | "
                      f"{j['company'][:20]:20} | {j['source'][:12]:12} | why={j['why']}")

        # which INCLUDE terms are actually earning their keep, and which let junk in
        print("\n### matches per INCLUDE term (ML track)")
        tally = {}
        for j in new:
            if j["track"] == "ml":
                tally[j["why"]] = tally.get(j["why"], 0) + 1
        for term, n in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"  {n:4}  {term}")
    else:
        send_email(subject, body)

    # mark everything seen (even in dry-run so first real run isn't a flood — comment out to keep testing)
    if not dry:
        for j in jobs:
            seen.add(j["url"])
        save_seen(seen)
        print(f"seen.json updated: {len(seen)} URLs tracked")


if __name__ == "__main__":
    main()
