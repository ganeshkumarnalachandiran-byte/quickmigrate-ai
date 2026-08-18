# QuickMigrate-AI

Agentic BI-to-QuickSight migration tool. It migrates reports with a lightweight
core engine (parse → resolve datasets → AI-translate → create dashboard) and
**flags the reports it can't handle** as candidates for AWS Transform.

Verified end-to-end against live AWS: a Tableau workbook was translated by Claude
Sonnet 4.5 and created as a QuickSight dashboard that renders correctly — right
chart types, right fields, working aggregations — on the first attempt.

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
scoring, resolution, or translation.

> AWS Transform's BI agents are currently a self-service, conversational capability
> inside AWS Transform, not a documented public headless API. Verify current API
> availability with your AWS account team before building the automated fallback.

---

## The pipeline

Each report flows through these stages. Because every stage speaks a shared
intermediate representation (`ReportIR`), adding a new source format or swapping
the AI backend touches only one stage — the rest is unchanged.

1. **Extract** — read the source file into a normalized `ReportIR` (visuals,
   marks, columns, datasources). Tableau `.twb` is implemented; `.pbix`/`.qvf`
   are stubs that route to fallback.
2. **Triage (score)** — score complexity *before* any model call. Unsupported
   charts, too many visuals/datasources, calculated fields, etc. push the score
   up; over the threshold → flag for Transform. This is the cost control: no
   tokens are spent on reports that can't be finished.
3. **Resolve datasets** — discover the QuickSight datasets that *actually exist*
   in the account (via the caller's credentials) so the model references real
   dataset ARNs instead of fabricating them. No datasets present → flag (the data
   layer is a migration precondition).
4. **Translate** — the agentic loop. Send the metadata plus the real dataset ARNs
   to Bedrock; parse and validate the response; on failure, feed the error back
   and retry (self-correction), up to `QM_MAX_RETRIES`.
5. **Execute** — create the dashboard via `boto3` `create_dashboard`, with an
   idempotency check so re-running a batch doesn't duplicate.
6. **Report** — produce a report with two buckets: **migrated** and **flagged**
   (with the reason and `fallback_hint` for each flagged report).

---

## Setup

```bash
# from the repo root
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"            # runtime + test deps
cp .env.example .env               # then edit .env
```

## Run

```bash
# Offline demo — no AWS, no cost (default mode)
quickmigrate --input samples/ --output output/report.json

# Single file
quickmigrate --input samples/sales_simple.twb

# Real Bedrock + QuickSight (see "Running against real AWS" below)
export QM_MODE=bedrock
export QM_AWS_ACCOUNT_ID=<your-account-id>
export QM_AWS_REGION=<your-region>
export QM_BEDROCK_MODEL=<model-id-or-inference-profile>
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
| `QM_AWS_ACCOUNT_ID`    | Target AWS account (required in bedrock mode)       |
| `QM_AWS_REGION`        | Target region (e.g. `ap-southeast-1`)               |
| `QM_BEDROCK_MODEL`     | Bedrock model id **or inference profile** (see below)|
| `QM_MAX_RETRIES`       | Agent self-correction attempts                      |
| `QM_MAX_VISUALS` etc.  | Triage thresholds — what the engine claims it can do |
| `QM_FALLBACK_SCORE`    | Score at/above which a report is routed to Transform |
| `QM_LOG_JSON`          | `true` for structured logs (prod aggregation)       |

Tuning what the core engine handles = changing the `QM_MAX_*` / `QM_FALLBACK_SCORE`
values, or adding chart-type mappings in `extractors/tableau.py` +
`translation/backends/mock.py`. No other pipeline changes needed to widen scope.

---

## Running against real AWS

A few operational notes so you don't re-hit avoidable walls. These are properties
of AWS/Bedrock account provisioning, not the tool.

- **Cross-region inference profiles.** Newer models (e.g. Claude Sonnet 4.5) are
  not invocable by their bare model id — they require a cross-region *inference
  profile*, whose id carries a region-scope prefix (`global.` or `apac.`, e.g.
  `global.anthropic.claude-sonnet-4-5-<date>-v1:0`). Set `QM_BEDROCK_MODEL` to the
  profile id, not the bare model id. List available profiles with
  `aws bedrock list-inference-profiles`. If a run errors that on-demand throughput
  isn't supported, this is why.
- **New-account rate limits.** Fresh AWS accounts start with very low Bedrock
  quotas (as low as 1 request/minute for some models, sometimes non-adjustable
  until the account matures). Because the agentic loop makes multiple calls per
  migration, a too-low quota will throttle it. Check Service Quotas for your model;
  raise it (where adjustable) or let the account age.
- **Anthropic use-case form.** The first call to an Anthropic model on an account
  may require submitting a one-time use-case form in the Bedrock console, and can
  take a few minutes to propagate. This is per-model.
- **Datasets must exist.** The resolve step references datasets that already exist
  in QuickSight. Create (or migrate) the datasets first; the tool discovers them,
  it does not create them.
- **Dashboard permissions.** The tool creates the dashboard but does not grant
  viewing permissions (see Scope). After creation, the QuickSight administrator
  grants access to the relevant users/groups.

---

## Project layout

```
src/quickmigrate/
  config.py              # one typed Settings object, loaded from env
  errors.py              # typed exception hierarchy (stage-aware)
  logging.py             # plain or JSON structured logging
  models.py              # the IR + all result/report dataclasses
  resolver.py            # credentials-driven QuickSight dataset discovery
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

## Scope

The tool's job is to **translate a BI report and create the QuickSight dashboard**.
It deliberately does **not** manage dashboard viewing permissions — granting access
is an account-governance decision left to the QuickSight administrator. Baking
access-control into a migration tool would be overreach; keeping it out is a
deliberate separation of concerns. (A future enhancement could optionally grant a
configured principal on creation.)

---

## Status: what is and isn't proven

- **Proven end-to-end against live AWS.** A Tableau `.twb` was extracted,
  translated by Claude Sonnet 4.5, and created in QuickSight as a dashboard that
  **renders correctly** — correct chart types (bar + line), correct field
  mappings, working aggregations, populated with real data — on the first attempt
  (`CREATION_SUCCESSFUL`, zero errors).
- **Proven offline.** Extraction, triage, dataset resolution (mocked), the
  self-correcting retry loop, reporting, and the QuickSight calls (via stubbed
  AWS). Full test suite passes.
- **Not yet implemented.** `.pbix` (PowerBI) and `.qvf` (Qlik) extraction are stubs
  that route to fallback.
- **Not yet built.** Run observability (see Known gaps).

---

## Known gaps / next steps

Surfaced by real-run testing. In rough priority:

1. **Observability of the run.** The tool should surface (a) the exact dashboard
   definition it created and (b) the full LLM interaction trail — each prompt,
   response, validation result, and correction across the agentic loop, plus token
   usage and timing. Today only inter-attempt *errors* are captured (`error_trail`);
   the created artifact and full prompt/response chain require a manual
   `describe-dashboard`. Highest-value enhancement for auditability and debugging.
2. **Schema-aware dataset resolution.** The resolver currently lists the
   available datasets and relies on the model to map each visual to a dataset by
   field-name inference. This is reliable for a single dataset (the mapping is
   unambiguous) but becomes guesswork with several, and the model cannot verify
   its choice because it can't see inside the datasets. It should fetch each
   dataset's columns (`describe_data_set`) and deterministically bind each visual
   to the dataset that actually contains its fields — and reconcile the source's
   datasource names (e.g. Tableau "federated.sales") against the target dataset
   names by schema rather than label, since they will not match. This is the most
   important correctness gap for multi-dataset reports.
3. **Throttle backoff.** The retry loop currently retries immediately on any
   failure, which turns one Bedrock `ThrottlingException` into several. Throttling
   is an infrastructure condition (not agentic self-correction) and should trigger
   exponential backoff, or use boto3's adaptive retry mode. Keep the two retry
   mechanisms distinct.
4. **Failure classification.** Transient failures (throttling, timeouts) are
   currently bucketed with genuine "route to Transform" flags. They warrant a
   third category — *retryable* — separate from both migrated and out-of-scope.
5. **PowerBI `.pbix` extraction.** The `Report/Layout` (visuals) is parseable
   (UTF-16 JSON, with nested JSON-as-strings); the compiled data model is best left
   to Transform. Because extraction emits the shared `ReportIR`, a working `.pbix`
   extractor slots into the existing pipeline with no other changes.
6. **Wider chart coverage** to shrink the flagged bucket.
7. **Real QuickSight validation loop.** Feed live `create_dashboard` rejections
   back into the agent for another self-correction round (today the loop validates
   against a structural stand-in before the real API call).
8. **Automated Transform fallback.** POST `fallback_hint` to a Transform API,
   pending headless API availability. The payload is already emitted today.

---

## Create the git repository

```bash
cd quickmigrate-ai
git init
git add .
git commit -m "Initial commit: QuickMigrate-AI"

# push to an EMPTY GitHub repo:
git remote add origin https://github.com/<you>/quickmigrate-ai.git
git branch -M main
git push -u origin main
```

`.env` and `output/` are gitignored — secrets and artifacts stay out of the repo.