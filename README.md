# Daily Job Digest

Scrapes ML / AI / Data / LLM roles every morning from live sources, filters them
against your CV profile, drops senior and already-seen roles, and emails you a digest.

**Sources:** Remotive, RemoteOK, Himalayas, Tether, Greenhouse (Canonical, Scale,
Turing, Snorkel, Toloka), Lever (Binance), Ashby (Mercor, Weaviate), web3.career, hh.ru.

---

## One-time setup (about 10 minutes)

### 1. Create a Gmail App Password
The script sends mail through your Gmail. Gmail won't accept your normal password from
a script, so you need a 16-character **App Password**:

1. Turn on 2-Step Verification: https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords
3. Create one (name it "jobfeed"). Google shows a 16-character code — copy it.

If you don't see "App passwords", 2-Step Verification isn't fully enabled yet.

### 2. Put these files in a GitHub repo
Create a new repo (private is fine), and upload:
```
scrape_jobs.py
requirements.txt
seen.json
.gitignore
.github/workflows/daily-jobs.yml
```
Keep the `.github/workflows/` folder structure exactly as shown.

### 3. Add three secrets
In the repo: **Settings → Secrets and variables → Actions → New repository secret.**
Add:

| Name                 | Value                                    |
|----------------------|------------------------------------------|
| `EMAIL_FROM`         | your Gmail address (the sender)           |
| `EMAIL_APP_PASSWORD` | the 16-char app password from step 1      |
| `EMAIL_TO`           | `princekay145@gmail.com`                  |

`EMAIL_FROM` and `EMAIL_TO` can be the same address.

### 4. Turn it on
Go to the **Actions** tab, enable workflows if prompted, open **Daily job digest**,
and click **Run workflow** to test it now. Check your inbox.

After that it runs automatically every day at 06:00 UTC (09:00 Moscow).

---

## What to expect

- **First run** emails a large backlog (~130 roles) — everything currently open.
  That's normal and only happens once.
- **Every day after** you only get genuinely new postings, usually a handful.
- The run saves `seen.json` back to the repo so it remembers what it already sent.
- Roles are sorted **worldwide-remote first**, then US-remote, then Russia, then other.

The digest has **two sections**:

1. **ML / AI / Data** — the main list, your actual target roles.
2. **Entry-level support & sales** — a shorter fallback section at the bottom:
   customer support, tech/IT support, helpdesk, SDR/BDR and entry sales. This
   section only shows postings from the **last 7 days**; anything older, or
   anything whose posting date can't be read, is never shown. Change the window
   with `SUPPORT_FRESH_DAYS` in `scrape_jobs.py`.

   Because the freshness rule needs a real posting date, `web3.career` and
   `hh.ru` never appear in section 2 — neither exposes one. Section 1 is
   unaffected.

---

## Changing things

Open `scrape_jobs.py`. The top `CONFIG` block is the only part you normally touch:

- **`INCLUDE`** — a title must contain one of these words to show up. Add/remove freely.
- **`EXCLUDE`** — a title with any of these is dropped (this is your seniority filter).
- **`SUPPORT_INCLUDE` / `SUPPORT_EXCLUDE`** — same pair, for the support & sales
  section at the bottom of the email.
- **`SUPPORT_FRESH_DAYS`** — how recent a support/sales posting must be (default 7).
- **`GREENHOUSE` / `LEVER` / `ASHBY`** — add more companies by their board token.
- **Schedule** — edit the `cron:` line in `.github/workflows/daily-jobs.yml`.
  It's in UTC. `0 6 * * *` = 06:00 UTC daily. Moscow is UTC+3.

## Running locally (optional)
```
pip install -r requirements.txt
python scrape_jobs.py --dry-run     # prints matches, sends nothing
EMAIL_FROM=you@gmail.com EMAIL_APP_PASSWORD=xxxx python scrape_jobs.py   # sends
```

## Notes / limits
- Keyword filtering is strong but not perfect — the odd off-target role slips through,
  and an oddly-titled good one occasionally doesn't. Skim, don't trust blindly.
- Always confirm a posting is still open before applying; boards lag.
- `hh.ru` sometimes blocks datacenter IPs. If it returns nothing from GitHub's runners,
  the run still succeeds on all other sources — hh just contributes 0 that day.
- If you ever can't host the repo, tell Claude "switch to option B" and it'll run the
  pull for you on demand instead.
