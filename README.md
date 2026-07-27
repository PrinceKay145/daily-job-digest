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

### 2. Push to GitHub
The repo is already initialised and committed locally. Create the remote and push:

```bash
gh repo create daily-job-digest --public --source=. --push   # needs the gh CLI
```

Or without `gh`: create an empty repo named `daily-job-digest` at
https://github.com/new (no README, no .gitignore — this repo already has both), then:

```bash
git remote add origin https://github.com/PrinceKay145/daily-job-digest.git
git push -u origin main
```

Keep the `.github/workflows/` folder exactly where it is or Actions won't find it.

### 3. Add the three secrets
**These go in GitHub's web UI, not in a file.** In your repo:

**Settings → Secrets and variables → Actions → New repository secret.**

Add three, one at a time:

| Name                 | Where to get the value                                          |
|----------------------|-----------------------------------------------------------------|
| `EMAIL_FROM`         | The Gmail address that sends the digest — just type it.          |
| `EMAIL_APP_PASSWORD` | The 16-character code from step 1 (https://myaccount.google.com/apppasswords). Not your Google password. |
| `EMAIL_TO`           | Where the digest is delivered: `princekay145@gmail.com`.          |

`EMAIL_FROM` and `EMAIL_TO` can be the same address. Repository secrets stay
encrypted and are never visible in logs, so this is safe on a public repo — but
it is also the *only* safe place for them. Never put the app password in a file
you commit.

If you paste a secret wrong you can't read it back; just overwrite it with a new value.

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

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scrape_jobs.py --dry-run     # prints matches, sends nothing
```

`--dry-run` needs no credentials. To actually send from your machine, copy the
placeholder file and fill in the same three values from step 3:

```bash
cp .env.example .env      # then edit .env
.venv/bin/python scrape_jobs.py
```

`.env` is gitignored, so it can't be committed by accident. Real environment
variables take priority over it, which is why GitHub Actions ignores it entirely.

`--dry-run` also prints, for every role, which `INCLUDE` keyword matched it
(`why=...`) plus a tally per keyword. Use that to find keywords letting junk in
before you change them.

## Notes / limits
- Keyword filtering is strong but not perfect — the odd off-target role slips through,
  and an oddly-titled good one occasionally doesn't. Skim, don't trust blindly.
- Always confirm a posting is still open before applying; boards lag.
- `hh.ru` sometimes blocks datacenter IPs. If it returns nothing from GitHub's runners,
  the run still succeeds on all other sources — hh just contributes 0 that day.
- If you ever can't host the repo, tell Claude "switch to option B" and it'll run the
  pull for you on demand instead.
