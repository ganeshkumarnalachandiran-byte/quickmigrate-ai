# QuickMigrate-AI

Agentic BI-to-QuickSight migration tool. It attempts to migrate reports with a
lightweight core engine (parse → AI-translate → create dashboard) and **flags the
reports it can't handle** as candidates for AWS Transform.

---

## Frugal architecture, in one paragraph

The core engine runs locally (or in Lambda/CloudShell) and pays only per-token
Amazon Bedrock costs plus trivial QuickSight calls — no migration infrastructure,
no subscription floor. A complexity scorer triages every report **before** any
model call, so tokens are spent only on reports the engine can actually finish.
The translator is a self-correcting agent: when a payload is rejected, the error
is fed back and the model fixes its own JSON. Reports beyond the engine's scope
are flagged for AWS Transform with a ready-to-send metadata payload.

---

## Core engine vs. AWS Transform (the hybrid)

The core engine handles the cheap, common cases. The long tail — exotic visuals,
custom SQL, many datasources, PowerBI `.pbix`, Qlik `.qvf`, calculated fields — is
**flagged for AWS Transform** (the Wavicle/EZConvertBI agents that run inside AWS
Transform).

Today the fallback is **manual**: the tool lists which reports need Transform and
why. Each flagged entry also carries a `fallback_hint` — the assembled metadata a
future version could POST to a Transform API to **automate** the hand-off, *if/when*
a headless API is available. That upgrade lives in one place
(`fallback/transform.py::submit_to_transform`) and needs no change to parsing,
scoring, or translation.

> AWS Transform's BI agents are currently a self-service, conversational capability
> inside AWS Transform, not a documented public headless API. Verify current API
> availability with your AWS account team before building the automated fallback.

---

## Setup

```bash
# from the repo root
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # runtime + test deps
cp .env.example .env               # then edit .env
```

## Run

```bash
# Offline demo — no AWS, no cost (default mode)
quickmigrate --input samples/ --output output/report.json

# Single file
quickmigrate --input samples/sales_simple.twb

# Real Bedrock + QuickSight
export QM_MODE=bedrock
export QM_AWS_ACCOUNT_ID=123456789012
export QM_BEDROCK_MODEL=<verify-current-model-id>
quickmigrate --input samples/ -o output/report.json
```

Exit code is `0` if everything migrated cleanly, `1` if any report was flagged
(handy in CI).

## Test

```bash
pytest                    # all tests
pytest tests/unit         # fast, offline
pytest tests/integration  # AWS calls via botocore Stubber (no real AWS)
```

---

## Configuration

All config is environment-driven and documented in `.env.example`. Highlights:

| Var                    | Purpose                                             |
|------------------------|-----------------------------------------------------|
| `QM_MODE`              | `mock` (offline, default) or `bedrock` (real AWS)   |
| `QM_BEDROCK_MODEL`     | Bedrock model id — **verify current model**         |
| `QM_MAX_RETRIES`       | Agent self-correction attempts                      |
| `QM_MAX_VISUALS` etc.  | Triage thresholds — what the engine claims it can do |
| `QM_LOG_JSON`          | `true` for structured logs (prod aggregation)       |

Tuning what the core engine handles = changing the `QM_MAX_*` / `QM_FALLBACK_SCORE`
values, or adding chart-type mappings in `extractors/tableau.py` +
`translation/backends/mock.py`. No other code changes needed to widen scope.

---

## Project layout

```
src/quickmigrate/
  config.py              # one typed Settings object, loaded from env
  errors.py              # typed exception hierarchy (stage-aware)
  logging.py             # plain or JSON structured logging
  models.py              # the IR + all result/report dataclasses
  extractors/            # one module per source; registry maps suffix -> extractor
    base.py  tableau.py  powerbi.py  qlik.py  __init__.py (registry)
  triage/complexity.py   # scorer; policy comes from config thresholds
  translation/
    agent.py             # the agentic retry loop (backend-agnostic)
    prompts.py  validation.py
    backends/            # swappable model backends
      base.py  bedrock.py  mock.py  __init__.py (factory)
  execution/quicksight.py  # boto3 create_dashboard + idempotency
  fallback/transform.py    # builds fallback_hint; future API hook
  reporting.py           # assembles + renders the migration report
  orchestrator.py        # wires the pipeline
  cli.py                 # argparse entrypoint
tests/
  unit/                  # extractors, complexity, translation, reporting
  integration/           # QuickSight via botocore Stubber
  fixtures/              # sample .twb / .pbix
samples/                 # demo inputs
```

---

## Create the git repository

```bash
cd quickmigrate-ai
git init
git add .
git commit -m "Initial commit: QuickMigrate-AI production skeleton"

# push to an EMPTY GitHub repo:
git remote add origin https://github.com/<you>/quickmigrate-ai.git
git branch -M main
git push -u origin main
```

`.env` and `output/` are gitignored — secrets and artifacts stay out of the repo.

---

## What is and isn't production-proven

- **Proven offline:** extraction, triage, the retry loop, reporting, and the
  QuickSight calls (via stubbed AWS). Full test suite passes.
- **Not yet proven:** the self-correction against the *real* QuickSight API
  contract. In mock mode the loop validates against a structural stand-in; run one
  real batch in your AWS account before claiming live parity.
- **Stubs:** `.pbix` and `.qvf` extraction route straight to fallback — implement
  or leave to Transform.

## Roadmap

1. **Automated Transform fallback** — POST `fallback_hint` to a Transform API
   (pending headless API availability). Payload already emitted today.
2. **PowerBI `.pbix` extraction** — layout JSON is feasible; the data model is best
   left to Transform.
3. **Wider chart coverage** to shrink the flagged bucket.
4. **Real QuickSight validation loop** — feed live `create_dashboard` rejections
   back into the agent.
