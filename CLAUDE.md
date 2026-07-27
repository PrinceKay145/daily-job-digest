# CLAUDE.md — Job Feed project context

Context and working instructions for Claude Code. Read this first every session.

---

## What this project is

An automated daily job digest for **Ridwan A. Adebayo**. A Python script scrapes
live job sources, filters roles against Ridwan's profile, drops senior and
already-seen postings, and emails a digest. It runs unattended once a day via
GitHub Actions.

The goal is a low-noise stream of **genuinely applicable** ML / AI / Data / LLM
roles — not a firehose. Precision matters more than recall: a missed role is
cheaper than eroding trust in the digest with junk.

---

## Current state

Built and tested end-to-end. **Last verified run: 27 July 2026** — 8 of 9 sources
returned data, hh.ru returned 0 (expected; see its note below). 132 roles matched:
118 ML/AI/data + 14 entry-level support/sales. `seen.json` is empty, so the first
real run emails the whole backlog once.

**Not yet deployed.** The repo is initialised locally but has no GitHub remote and
no Actions secrets set, so nothing is running on a schedule yet. Remaining steps
are in README.md: create the GitHub repo, push, add `EMAIL_FROM` /
`EMAIL_APP_PASSWORD` / `EMAIL_TO` secrets, run the workflow once manually.

---

## Repository layout

```
scrape_jobs.py                     # everything: sources, filter, email. Single file by design.
requirements.txt                   # just `requests`
seen.json                          # dedup memory; committed back after each run
.gitignore
README.md                          # human setup guide (Gmail app password, secrets, Actions)
.github/workflows/daily-jobs.yml   # daily cron + manual trigger
CLAUDE.md                          # this file
```

Keep it a single script unless it grows past ~500 lines. Don't prematurely split
into packages; the value is that Ridwan can read the whole thing in one sitting.

---

## How it works

1. Each source is a `src_*()` function returning a list of job dicts built by the
   `job()` helper. Every source is defensively wrapped so one failure can't kill
   the run.
2. `collect()` runs all sources and `classify()` sorts each job into one of **two
   tracks**, or drops it. Dedup is by URL.
3. `seen.json` (a list of URLs) is loaded; anything already seen is dropped.
4. Remaining jobs are rendered into a two-section HTML email and sent via Gmail SMTP.
5. All matched URLs are written back to `seen.json`, which the workflow commits.

Config lives in the `CONFIG` block at the top of `scrape_jobs.py`:
`INCLUDE`, `EXCLUDE`, `SUPPORT_INCLUDE`, `SUPPORT_EXCLUDE`, `SUPPORT_FRESH_DAYS`,
the Greenhouse/Lever/Ashby company maps, `HH_QUERIES`, location-hint lists, and
`RECIPIENT`.

### The two tracks

| | **ML track** (main section) | **Support track** (bottom section) |
|---|---|---|
| keywords | `INCLUDE` / `EXCLUDE` | `SUPPORT_INCLUDE` / `SUPPORT_EXCLUDE` |
| covers | ML / AI / data / LLM roles | customer support, tech & IT support, helpdesk, SDR/BDR, entry sales |
| seniority gate | intern → middle | entry level, stricter |
| freshness | none | **must** have a known posting date ≤ `SUPPORT_FRESH_DAYS` (7) |
| sort | worldwide-remote → US → Russia → other | newest first |

The ML track wins any overlap; `classify()` tries it first. The support track is
an intentional exception to the "precision over recall" rule for the main list —
it's fallback / bridge income, so it's kept small and strictly fresh rather than
strictly relevant.

**Why `SUPPORT_EXCLUDE` is a separate list and not just `EXCLUDE`:** `EXCLUDE`
contains `sales`, `sdr`, `customer success` and a bare `lead ` — those exist to
keep non-ML work out of the main list, and reusing it here would drop the entire
support track (`lead ` alone kills every "Lead Generation Specialist"). If you
add a seniority term, add it to **both** lists.

**Posting dates.** `parse_date()` handles epoch seconds, epoch milliseconds
(Lever) and ISO/`YYYY-MM-DD hh:mm:ss UTC` strings. Every JSON source supplies one:
Greenhouse `first_published`, Lever `createdAt`, Ashby `publishedAt`, Tether
`published_at`, Remotive `publication_date`, RemoteOK `epoch`, Himalayas `pubDate`.
The two HTML scrapers (web3.career, hh.ru) don't expose a date, so they can never
appear in the support section. That's by design, not a bug — don't "fix" it by
defaulting undated postings to today.

---

## Sources

| Source       | Method            | Endpoint / how                                             | Reliability |
|--------------|-------------------|------------------------------------------------------------|-------------|
| Remotive     | JSON API          | `remotive.com/api/remote-jobs?search=`                     | high |
| RemoteOK     | JSON API          | `remoteok.com/api?tag=`                                     | high |
| Himalayas    | JSON API          | `himalayas.app/jobs/api?limit=&offset=` (rolling feed)     | high, but feed rotates — some days 0 AI roles |
| Tether       | Recruitee API     | `tether.recruitee.com/api/offers/`                         | high |
| Greenhouse   | JSON API          | `boards-api.greenhouse.io/v1/boards/{token}/jobs`          | high (has 1 retry for transient non-JSON) |
| Lever        | JSON API          | `api.lever.co/v0/postings/{token}?mode=json`               | high |
| Ashby        | JSON API          | `api.ashbyhq.com/posting-api/job-board/{token}`            | high |
| web3.career  | HTML scrape       | category pages, regex over `<tr>` rows                     | medium — HTML can change; parser may need upkeep |
| hh.ru        | HTML scrape       | `hh.ru/search/vacancy?...&schedule=remote`                 | medium — **blocks datacenter IPs**, see below |

**hh.ru note:** its public API returns `403 forbidden` for unregistered clients,
so we scrape HTML with a browser User-Agent. This works from residential IPs but
GitHub Actions runners are datacenter IPs and may get blocked — on those days hh
contributes 0 and the run still succeeds. If hh reliability matters, options are:
register an hh.ru API app for a token, or run the hh source from a residential
proxy. Don't spend effort here unless Ridwan asks; the other 8 sources carry it.

When adding a company, prefer its ATS board (Greenhouse/Lever/Ashby) over HTML
scraping — just add the token to the relevant dict in CONFIG. To find the token,
check the company's careers page URL (e.g. `jobs.lever.co/{token}`,
`job-boards.greenhouse.io/{token}`, `jobs.ashbyhq.com/{token}`).

---

## Candidate profile (use this to filter and to help with applications)

**Ridwan A. Adebayo** — ML/LLM engineer, Data Science MSc at NITU MISIS Moscow
(GPA 5.0), BSc Maths & CS from RUDN (GPA 4.88). Graduates **July 2026**. Nigerian
citizen, currently living in Moscow. Currently a Senior Data Auditor-Analyst at
Sberbank (IT Audit); actively moving toward a Data Scientist / LLM / ML role.

**Core strengths:** production LLM systems, RAG pipelines, fine-tuning (LoRA/QLoRA
on LLaMA/Mixtral), multi-agent architectures (LangChain/LangGraph), SQL/analytics.
Prior roles at VK (behavioral-data pipeline, Random Forest), LLime (LLM fine-tuning
+ RAG at scale), Varsityscape (technical lead on ScapeAI, GCP).

**Research:** two published papers on LLM fine-tuning / PEFT; award-winning thesis
on domain-specific fine-tuning; ICSC 2025 bronze. Master's thesis direction:
**argumentation-driven multi-agent systems**. Actively applying to PhD programs
(UCD / Prof. Ferrari on argumentation-based requirements engineering is the focus).

**Stack:** Python, PyTorch, HuggingFace, LangChain, LangGraph, FastAPI, LoRA/PEFT,
ChromaDB/Qdrant/Pinecone, LangSmith/Langfuse, MLflow, Docker, GCP, Kafka, Postgres.
Also SQL, Power Query/M (learning), Power BI. Crypto/DeFi native (Binance, Bybit,
smart-contract auditing on Sherlock/Code4rena).

**Languages:** English C1, Russian C1, Yoruba native.

**Levels in scope:** intern / junior / middle. **Not** senior/lead/principal.
**Location:** open to Russia *and* overseas. Prefers English-language work (Russian
OK if little communication needed). Prefers remote or hybrid; not fully on-site.

---

## Hard constraints that shape job fit

These determine whether a role is *actually* applicable, beyond keyword match:

1. **Payment rails.** He's a Nigerian citizen resident in Russia. Wise/Payoneer/
   Deel/US-EU bank transfer generally don't serve Russian residents. Roles that
   can onboard him as a **Nigerian contractor** (Nigerian bank / Payoneer), or pay
   in crypto, are the frictionless ones. Crypto-native employers (Tether, Binance,
   OKX) sidestep this entirely and are the strongest structural fit.
2. **Graduation cliff, July 2026.** Anything requiring *current* student enrolment
   (many internships, some fellowships, AfDB) expires when he graduates. Flag these
   as time-sensitive.
3. **Worldwide vs geo-locked.** "Remote" often means remote-within-a-country. The
   digest tags `🌍 worldwide/remote` vs `US/remote` vs `🇷🇺 Russia` for this reason.
   US-only and EU-only roles need visa/eligibility confirmation before effort.
4. **The Sber audit angle is an asset, not just a detour.** For **model validation /
   model risk / AI governance / AI assurance** roles, his "Data Auditor doing ML"
   background is a top-decile differentiator, not a weakness. Surface these.

---

## Setup / deployment (summary; full version in README.md)

- Gmail **App Password** required (normal password won't authenticate via SMTP).
- Three GitHub Actions secrets: `EMAIL_FROM`, `EMAIL_APP_PASSWORD`,
  `EMAIL_TO` (= `princekay145@gmail.com`).
- Workflow needs `permissions: contents: write` to commit `seen.json` back.
- Runs `0 6 * * *` UTC (09:00 Moscow). cron is UTC; adjust the hour to shift.
- First run emails the full backlog once (~180 roles); every run after is incremental.

Local dev: `python scrape_jobs.py --dry-run` prints matches without sending.

---

## Conventions for working in this repo

- **Keep it one file and dependency-light.** `requests` only. Don't add heavy
  frameworks, databases, or a web UI unless explicitly asked.
- **Every new source gets its own `try/except`-wrapped `src_*()` function** and an
  entry in the `SOURCES` list. Never let one source break the run.
- **Prefer JSON APIs over HTML scraping.** HTML parsers rot; note fragility in a
  comment when you must scrape.
- **Test with `--dry-run` before claiming something works.** Print pulled vs matched
  counts per source like the existing code does.
- **Don't touch `seen.json` by hand** except to reset it (`echo "[]" > seen.json`)
  when intentionally re-flooding the backlog.
- **Filtering is precision-first.** When tuning `INCLUDE`/`EXCLUDE`, bias toward
  fewer false positives. If unsure whether a term over-matches, test it against a
  dry run and count the junk it lets in — `--dry-run` prints a per-INCLUDE-term
  tally for exactly this, and `why=` on each row shows which term fired.
  Measured 27 Jul 2026: bare `"python"` pulled 22 roles of which 19 were plain
  backend/infra Python engineering (12 from Canonical), so it was removed;
  `"prompt"` was narrowed to `"prompt engineer"`; `"quant"` was measured at 3/3
  genuine Binance fits and kept. Don't re-add bare `"python"` without re-measuring.
- No secrets in code. Ever. They come from env vars / GitHub secrets only.

---

## Good next tasks (roadmap, not committed)

- **De-dup near-identical titles** across region-suffixed postings (Tether/Binance
  post the same role many times). Group by (company, normalized title).
- **Freshness cutoff on the ML track.** Posting dates are now parsed for every
  JSON source, but only the support track uses them. The main list still carries
  genuinely stale reqs — measured 27 Jul 2026, Canonical's Greenhouse board alone
  had postings 2–5 years old (`first_published` back to 2020). A `MAX_AGE_DAYS`
  gate on the ML track would cut real noise; the catch is web3.career and hh.ru
  have no dates, so it has to be opt-in per source or it would silently delete them.
- **A "why matched" tag in the email.** Already computed — `j["why"]` holds the
  INCLUDE term that fired, and `--dry-run` prints a per-term tally. It just isn't
  surfaced in the HTML yet.
- **Model-validation / AI-governance source expansion** — add Alfa-Bank, and
  EU AI-Act-driven assurance roles; this is his under-exploited edge.
- **Application helper mode** — a command that, given a job URL, drafts a tailored
  outreach message (see writing preferences below).
- **Weekly summary** — a Sunday roll-up of the week's worldwide-remote roles.

Confirm scope with Ridwan before building any of these; don't gold-plate.

---

## Writing / application preferences (if helping draft applications)

If asked to help with cover letters, outreach, or CV edits, follow these — they're
firm preferences, not suggestions:

- **No "CV in prose" cover letters.** Lead with skills and forward-looking value,
  not a restatement of CV metrics. The opening line should hook before mentioning
  himself.
- **No em-dashes.** Use semicolons and commas instead.
- **Tone:** natural, conversational, authentic over formally polished.
- **Generate raw material first, then shape it** — or run a short interview-style
  Q&A to find his authentic voice before drafting. Don't hand over a polished final
  draft cold.
- **Gaps:** acknowledge honestly, then pivot to strength. No avoidance.
- **Research positioning:** frame on academic foundations and conceptual
  contributions, not merely as extensions of industry work.
- **CV edits:** give **specific, actionable edit instructions**, not full rewrites.
  He edits manually, in Russian and English.
- **ATS:** for platform applications, ensure keyword coverage including classical
  ML terms, standard section headers, a summary section.
- **Salary:** he historically *understates* expectations. Nudge them upward toward
  the correct band for his experience, don't anchor low.
