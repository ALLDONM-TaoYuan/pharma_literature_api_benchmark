# Pharmaceutical Literature Interface Selection Benchmark

An **interface selection benchmark** for the "medical information" module of an AI agent.

Goal: run every publicly available medical literature interface over the same set of research objects, then compare **what each interface recalls, how much it recalls, and how good the recall is** — so the medical information module has an evidence base for *which interfaces to use and how the query strings should be written*.

This repository only does benchmarking and selection. It **does not** contain the agent's medical module itself — that comes after the selection conclusions are settled.

---

## Scope

### Three kinds of object

| Board | Directory | Research objects | Input workbook | Dimensions |
|---|---|---|---|---|
| Disease | `disease/` | HIV-1 AIDS, ischemic heart disease, … | `disease.xlsx` | Basic Information / Clinical Studies / Pre-Clinical Studies |
| Drug | `drug/` | KT-621, BNT327, NTLA-2002, … | `unapproved drugs.xlsx`, `approved drugs.xlsx` | Basic Information / Clinical Studies / Non-Clinical Studies |
| Target | `target/` | BRIP1/DHX9, HIV-1 capsid, JAK1, … | `target.xlsx` | Basic Information / Clinical Studies / Pre-Clinical Studies / Druggability Feasibility Study |

The drug board splits its objects into two workbooks: `unapproved drugs.xlsx` holds drugs seen at conferences but not yet approved, `approved drugs.xlsx` holds drugs that are already approved (or in late-stage trials).

The input workbook of each board sits at the root of that board's directory, so editing a workbook never requires touching code.

### Eight interfaces

| Interface | Description | Needs a key | disease | drug | target |
|---|---|---|---|---|---|
| `Europe_PMC` | European literature database; takes the top N by relevance, then fetches full-text XML separately | no | ✓ | ✓ | ✓ |
| `PMC` | US NCBI literature database; supports batched abstract and full-text retrieval | no | ✓ | ✓ | ✓ |
| `ClinicalTrials` | Clinical trial registry | no | ✓ | ✓ | ✓ |
| `openFDA` | US FDA drug label database | no | ✓ | — | ✓ |
| `arxiv` | Preprint server | no | ✓ | ✓ | ✓ |
| `tavily` | General web search | yes | ✓ | ✓ | ✓ |
| `tavily_guideline` | Targeted guideline search | yes | ✓ | — | — |
| `ES` | Local literature database (Elasticsearch) on the internal network | needs the intranet | ✓ | ✓ | ✓ |

The `tavily` family is enabled only when a key is configured in `.env`; without one it is skipped automatically during collection and the other interfaces are unaffected.

`ES` is the only interface that must reach the internal network. It works as soon as `ES_URL` is set; without it, collection reports a connection error while the other interfaces are unaffected.

---

## Directory layout

```
main.py                      Root controller: pick a mode -> pick a board -> pick interfaces -> start

src/                         Every script lives here
├─ paths.py                  The single source of relative paths (board data dirs, variant result dirs, …)
├─ interfaces.py             Interface registry: settings, description, supported boards, required credentials
├─ settings.py               Shared settings: timeouts, retries, fetch counts, output directories
├─ credentials.py            Credentials: read only from the environment and .env, no real values stored
├─ console.py                Console encoding adaptation
├─ boards/                   The three board implementations
│  ├─ disease/
│  │  ├─ main.py             Board controller: read workbook -> per dimension, per interface -> write -> aggregate
│  │  ├─ config/
│  │  │  ├─ settings.py      Board-specific parameters only; shared settings come from src/
│  │  │  ├─ __init__.py      Dimensions, keyword groups, text helpers
│  │  │  └─ *_query.py       Per-interface query construction (tavily / PMC / ES …)
│  ├─ drug/                  Query building and the fill tool live in main.py; config/ holds the other interfaces
│  └─ target/
└─ advance/                  Interface comparison area: each board x 12 interface variants
   ├─ main.py                Top-level controller: list / run / check / digest / verify-md
   └─ <board>/
      ├─ main.py             Baseline controller for this board inside the advance area
      ├─ config/             Word lists and query construction for this board
      ├─ literature_variants/  Drug board's query-strategy comparison engine (original name / manual alias / original+info / alias+info)
      └─ <variant>/run_*.py   Collector for running a single interface variant

disease/ drug/ target/      Data directories of the three boards (not committed)
├─ ES/ PMC/ Europe_PMC/ …  Per-interface results (output/)
├─ ALL_result/              Aggregated results of all interfaces + the run log run_log.json
└─ *.xlsx                   The object workbook for this round

advance/                    Data directory of the advance area (per-variant output/ and input workbooks)
```

**Code and data are separate**: every `.py` lives under `src/`, while result data and input workbooks stay in the board directories. Every path between the two is obtained through `src/paths.py`; no script hard-codes an absolute path, so running from any working directory points at the same place.

Each board in `src/advance/` has 12 modules (ES1–ES4, Europe_PMC with 2/3/4, PMC1–PMC4) used to compare how different query formulations perform. They only use the Europe_PMC, PMC and ES interfaces.

Interface-related settings are centralized in `src/`. Each board's `config/settings.py` keeps only what differs (workbook names, column conventions, dimension keywords) and imports the rest from `src/`. All credentials are read from environment variables in `src/credentials.py`; no real value ever appears in the code.

---

## Setup

```bash
pip install -r requirements.txt

copy .env.example .env      # Windows; use cp on Linux/macOS
```

Edit `.env` and fill in the keys and internal addresses you need:

| Variable | Purpose |
|---|---|
| `TAVILY_API_KEY` | Key for tavily and tavily_guideline; leave empty to skip both interfaces |
| `ES_URL` / `ES_INDEX` / `ES_USER` / `ES_PASSWORD` | Connection details of the local literature database (Elasticsearch); all four are required |
| `OPENFDA_API_KEY` | openFDA key; optional, the interface works without it |
| `HTTPS_PROXY` | Proxy used to reach interfaces outside the intranet; leave empty for a direct connection |

The code only reads keys from environment variables and the repository never holds real values. `.env` is excluded by `.gitignore`. All the loading logic lives in `src/credentials.py`; neither `src/settings.py` nor `src/interfaces.py` contains any credential.

---

## How to run

### Through the root controller (recommended)

The `main.py` at the repository root is the entry point of the whole project. It asks three questions in order: **run mode** (normal / advance) → **test object** (disease / drug / target) → **which interfaces** (press Enter to select all).

```bash
python main.py
```

If you would rather not interact, pass the arguments directly:

```bash
python main.py --mode normal --board drug                        # run every interface of the drug board
python main.py --mode normal --board drug --sources Europe_PMC,PMC # run only the listed interfaces
python main.py --mode advance --board drug --variant PMC2          # run one variant in the advance area
python main.py list                                              # interface overview and credential status
python main.py check                                             # structure check
python main.py --mode normal --board drug --dry-run              # print the command that would run, without running it
```

Arguments after `--` are passed through to the underlying script, for example to switch the drug workbook:

```bash
python main.py --mode normal --board drug -- --table "approved drugs.xlsx"
```

### Running a whole board

Board scripts live in `src/boards/<board>/`, so change into the code directory first:

```bash
cd src/boards/disease
python main.py                    # run every object in the workbook
python main.py HIV-1 AIDS         # run a single object (the sheet name)
python main.py --sources Europe_PMC,PMC   # only the listed interfaces
python main.py --rebuild-all      # no requests; just re-aggregate the results already on disk
```

`drug` and `target` work the same way (neither has `--rebuild-all`). The drug board can switch workbooks:

```bash
cd src/boards/drug
python main.py --table "approved drugs.xlsx"
```

The workbook name contains a space, so it must be quoted on the command line.

Results are still written to the board's data directory (`disease/`, `drug/`, `target/`), separate from the code.

### Filling in missing tavily data

The drug board's `main.py` carries a fill tool: it scans the tavily results corresponding to `approved drugs.xlsx` and lists the **missing or failed** entries (successful ones are never re-run). Add `--fill` to actually fetch them:

```bash
cd src/boards/drug
python main.py --tavily-fill          # report only, sends no requests
python main.py --tavily-fill --fill   # really fetch the missing and failed entries
```

Filling only re-runs the tavily interface; it does not touch the results of the other interfaces and does not overwrite entries that already succeeded.

### Running a single interface variant

```bash
cd src/advance/disease
python ES3/run_es3.py             # one variant
```

### Other tools in the advance area

The advance controller has two more commands:

```bash
cd src/advance
python main.py list                       # overview of every variant (script, result count, size, status)
python main.py check                      # structure check (complete, no duplicates)
python main.py digest drug ES2            # compress a variant's results into compact evidence digests
python main.py verify-md drug ES2         # validate the md distillation files (DOI traceability, section length, format)
```

`digest` compresses the JSON returned by each interface into one txt section per article, marking the sentences that carry data, and writes them to `advance/_digest/<board>/<variant>/<object>/`.

### Running the interface comparison area

```bash
cd src/advance
python main.py list                # overview of every module (script, result count, size, status)
python main.py check               # structure check (directories complete, no duplicates)
python main.py run drug ES2        # run one interface variant of one board
```

---

## What the results look like

Each interface gets its own directory, and results land in `<interface>/output/<object>/<object>_<dimension>.json`:

```json
{
  "source": "Europe_PMC",
  "object": "HIV-1 AIDS",
  "dimension": "Clinical Studies",
  "ok": true,
  "total_results": 1043,
  "returned_results": 20,
  "results": [
    {
      "rank": 1,
      "title": "…",
      "content": "…",
      "content_type": "full_text",
      "doi": "10.…",
      "url": "https://…",
      "match_ratio": 0.714,
      "matched_keywords": ["clinical trial", "efficacy"]
    }
  ],
  "metrics": { "…": "…" }
}
```

- `content_type` states how complete the recalled record is: `full_text` (full text retrieved) / `abstract_only` (abstract only) / `metadata_only` (metadata only).
- `match_ratio` is the hit rate of **title plus abstract** against the dimension's keyword groups; `content_match_ratio` is the hit rate over the **entire body** (including full text). Both are recorded so that interfaces can be compared fairly.

Aggregated results are under `ALL_result/output/<object>/`, and `run_log.json` records the outcome, duration and error of every unit.

---

## About testing

This repository does not keep unit test directories. After changing collection logic, run a small scoped check through the root controller:

```bash
python main.py --mode normal --board disease --sources Europe_PMC --dry-run
python main.py --mode normal --board drug --sources Europe_PMC
```

`--dry-run` prints the command and the query strings without sending any request.

---

## Notes

- **The controllers print nothing to the console.** All logging lands in `run_log.json`, so a batch run can be judged by reading results instead of watching a screen.
- **To change how a query is written**, edit the keyword groups in `src/boards/<board>/config/__init__.py` and the query construction in `config/*_query.py`; the controller does not need to change.
- **Do not hard-code paths.** When adding or moving a directory, go through the functions in `src/paths.py` instead of stitching together `Path(__file__).parent.parent`.
- **The repository holds no collected results.** The returned literature runs to several GB, and `.gitignore` already excludes `output/` and `ALL_result/`; regenerate results with the commands above when needed.
- **Input workbooks (`*.xlsx`) are in `.gitignore` too**, because they contain drug names, competitors and internal therapeutic areas. Keep each workbook at the root of the matching board's data directory, with the file name matching `config/settings.py`.
- The three board implementations are independent and overlap in code, so **change only the three copies under `src/boards/`**. `src/advance/` is the comparison area copied out during the earlier interface study; use it to check query formulations, and do not change both sides at once.
