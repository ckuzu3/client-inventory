# Client Inventory

A small service that collects inventory reports from managed Windows clients and measures
each one against a configurable baseline: operating system build, disk encryption, patch
age, last check-in and free disk space. A FastAPI backend and an Angular dashboard that
reads it.

All data in this repository is synthetic. Nothing here comes from a real environment.

## Problem

In support work I keep answering the same question in a different form: which of our
clients are not where they should be right now? Not "are they enrolled", but concretely
which build they run, whether encryption is on, when they were last patched, and whether
they are still checking in at all.

The data exists, spread across several consoles, and each console answers one part. What
is missing is one place that holds the facts over time and states clearly which rule a
device fails and why. Exports to a spreadsheet answer it once and are stale the next
morning.

## Solution

A REST API that takes reports from a collector and evaluates each client against a
baseline, with the history of every submission kept.

The design decision I would defend first: compliance is not stored. It is derived from
the current facts and the active baseline every time it is asked for. Raise the minimum
build in the configuration and the whole fleet is re-measured on the next request, with
no migration and no recalculation job. The cost is that compliance cannot be filtered in
SQL, which is why that filter is an explicit, bounded pass in the application rather than
something that quietly degrades.

The rules live in one module of plain functions with no database or HTTP in them, so each
one is a single function call in a test. The API layer validates, queries and serialises,
and contains no policy.

## Features

- `POST /api/v1/reports` takes a submission, updates the client's current state and keeps
  the report as history. An unknown hostname is created, so a collector rollout needs no
  registration step.
- `GET /api/v1/clients` lists clients with pagination, filtering by operating system and
  an `only_with_findings` switch. The longest-silent client comes first.
- `GET /api/v1/clients/{hostname}` returns one client with its findings and its recent
  submissions.
- `GET /api/v1/compliance/summary` returns fleet-wide counts per rule and per severity.
- `GET /api/v1/baseline` states what is being measured, so a frontend does not hard-code
  the thresholds a second time.
- `GET /healthz` answers even when the database does not, and says which part is
  unhealthy.
- Five baseline rules: OS build below minimum, encryption off, patch level unknown or
  outdated, no recent check-in, low disk space. Each carries a stable code and a severity.
- Alembic migrations, with a test that asserts the migration produces the schema the
  models describe.
- A seeded generator for synthetic sample data, so the project can be demonstrated
  without a fleet.
- An Angular dashboard: fleet tiles, a worklist of clients with their findings, a filter
  for clients that need attention, and paging. It states the active baseline in words,
  read from the API rather than repeated in the frontend.
- 93 backend tests and 40 frontend tests. Backend coverage is 99 percent with the floor
  enforced at 90; ruff, mypy strict, ESLint and the Angular strict template checks are
  clean.

## Architecture

```text
collector (not in this repository)
     |
     | POST /api/v1/reports
     v
  api/routes.py          validate, call, serialise - no policy here
     |         \
     |          \ api/deps.py   session per request, commit on success
     v           v
repository.py           compliance.py          schemas.py
  upsert current state    five rules,            request and response
  append history         pure functions          contract
     |                        ^
     v                        | baseline from config.py
  models.py  ->  client, client_report
     |
     v
  SQLite (development, tests) | PostgreSQL (docker-compose, CI)


frontend/
  app.ts                  shell, one page, so no router
    |
  pages/dashboard.ts      owns all state and all loading
    |              `-- services/inventory-api.ts   the only place that knows HTTP exists
    v              v
  components/summary-cards.ts   components/client-table.ts
    presentational: take inputs, render, fetch nothing
```

Two tables, on purpose. `client` holds the current state and is updated in place, which
is what every list view needs. `client_report` keeps each submission, which is what makes
"when did this device lose encryption" answerable at all.

## Setup

Requires Python 3.12 or newer. The test suite needs no database and no container.

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Linux and macOS: source .venv/bin/activate
pip install -e ".[dev]"

ruff check . && ruff format --check . && mypy && pytest --cov
```

A running service on SQLite, with sample data:

```bash
cd backend
python -m client_inventory.seed --count 40 --seed 20261027 \
  --database-url "sqlite+pysqlite:///./demo.sqlite3" --create-schema

CLIENT_INVENTORY_DATABASE_URL="sqlite+pysqlite:///./demo.sqlite3" \
  uvicorn client_inventory.main:app --port 8000
```

The interactive API documentation is then at `http://127.0.0.1:8000/docs`.

The dashboard, against that API:

```bash
cd frontend
npm install
npm start                     # http://localhost:4200
```

On PostgreSQL, with the schema applied by Alembic:

```bash
docker compose up --build
```

Configuration is environment driven; `.env.example` lists every variable. Nested values
use a double underscore, so the encryption rule is
`CLIENT_INVENTORY_BASELINE__REQUIRE_ENCRYPTION`.

## Example

Submitting a report:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/reports \
  -H 'Content-Type: application/json' \
  -d '{"hostname":"WS-0001","os_name":"Windows","os_version":"10.0.19045.4529",
       "agent_version":"1.4.2","encryption_enabled":false,
       "disk_total_gb":512,"disk_free_gb":256}'
```

The response is the client as it now stands, already evaluated:

```json
{
  "hostname": "ws-0001",
  "os_version": "10.0.19045.4529",
  "free_disk_percent": 50.0,
  "compliant": false,
  "findings": [
    { "code": "encryption_disabled", "severity": "high",
      "detail": "Disk encryption is off while the baseline requires it." },
    { "code": "os_version_below_baseline", "severity": "high",
      "detail": "Build 10.0.19045.4529 is below the baseline of 10.0.26100." }
  ]
}
```

The hostname came back lowercased: `WS-0001` and `ws-0001` are one machine, and treating
them as two would make the fleet appear to grow.

The fleet summary, taken from a run against 40 generated clients:

```json
{
  "evaluated_at": "2026-10-26T23:18:52.993011Z",
  "total_clients": 40,
  "compliant_clients": 3,
  "noncompliant_clients": 37,
  "findings_by_code": {
    "disk_space_low": 16,
    "encryption_disabled": 8,
    "not_seen_recently": 12,
    "os_version_below_baseline": 20,
    "patch_level_outdated": 11,
    "patch_level_unknown": 4
  },
  "findings_by_severity": { "high": 32, "low": 16, "medium": 23 }
}
```

One worklist entry from the same run, worst finding first:

```json
{
  "hostname": "ws-0039",
  "os_version": "10.0.19045.4529",
  "last_seen_at": "2026-09-11T00:18:47.082470Z",
  "compliant": false,
  "findings": [
    { "code": "os_version_below_baseline", "severity": "high",
      "detail": "Build 10.0.19045.4529 is below the baseline of 10.0.26100." },
    { "code": "not_seen_recently", "severity": "medium",
      "detail": "Last seen 46 days ago, the baseline allows 14." }
  ]
}
```

The dashboard rendered against the 40 generated clients, read out of the running page:

```text
HOSTNAME   OPERATING SYSTEM         LAST SEEN     FREE DISK  FINDINGS
ws-0039    Windows 10.0.19045.4529  45 days ago   60%        HIGH os version below baseline
                                                             MEDIUM not seen recently
mac-0036   macOS 14.7               45 days ago   35%        MEDIUM not seen recently
mac-0018   macOS 14.7               45 days ago   18%        MEDIUM not seen recently
```

The two Macs carry no build finding, because the baseline's build number is a Windows
one and the rule is skipped for anything else. That decision is visible in the UI rather
than only in a test.

## Tests

```bash
cd backend
pytest --cov                  # 93 tests on in-memory SQLite, no services needed

# The same suite against a real PostgreSQL, which is what CI does
CLIENT_INVENTORY_TEST_DATABASE_URL="postgresql+psycopg://inventory:inventory@localhost:5432/inventory" pytest
```

```bash
cd frontend
npm test                      # 40 tests on Vitest with jsdom, no browser needed
npm run lint && npm run typecheck && npm run build
```

CI runs lint, format check, mypy and the backend suite on Python 3.12 and 3.13, runs that
suite again against a PostgreSQL service container, and runs the frontend's lint, format
check, type check, tests and build. The PostgreSQL job is what turns "it also works on
PostgreSQL" from a claim into something that was actually run.

## What I learned

- **Deriving a value is a trade, not a free choice.** Not storing compliance made the
  baseline instantly changeable and made one filter impossible to express in SQL. I would
  rather have that boundary visible, bounded by a configured scan limit, than discover it
  as a slow query later.
- **A build number is neither a number nor a string.** `10.0.9600` is greater than
  `10.0.26100` as text, which would have passed an outdated client. There is a test that
  asserts the string comparison is wrong, next to the one that asserts the parser is
  right.
- **SQLite lies about two things.** It accepts foreign keys and ignores them unless a
  pragma is set per connection, and it has no time zone, so a timestamp written as
  timezone-aware comes back naive. Both would have made a suite pass on SQLite and fail
  on PostgreSQL. One pragma and one normalisation function, both with tests.
- **A migration and a model drift apart silently.** The suite creates tables from the
  models, a deployment runs the migration; nothing connects the two unless a test does. It
  took twenty lines and it is the test I would keep if I could keep only one.
- **Out-of-order data is the normal case, not the edge case.** A laptop that was offline
  submits last week's facts today. Writing them as current state would overwrite this
  morning's truth, so a late report updates the history and not the current state.
- **A dependency decision belongs in writing.** Starlette's test client now asks for a
  different HTTP library. I scoped the warning instead of adding a second HTTP client for
  the test suite alone, and wrote down when I decided it, so the next person sees a
  decision rather than a suppressed warning.

## Possible extensions

- A detail view per client. The API already returns the report history; the dashboard
  does not show it yet.
- A collector. The agent that produces these reports is deliberately not in this
  repository: on Windows it is a PowerShell scheduled task, and that is a separate
  project with a separate release cycle.
- Authentication. Reports are unauthenticated, which is fine on a closed network and not
  fine anywhere else. A per-device token checked in a dependency is the smallest honest
  step.
- Trend queries over the stored history, such as how many clients left the baseline in a
  given week. The data is already there; it needs an endpoint and an index.
- Materialising compliance on write, if the fleet ever outgrew the scan limit.

## Known limits

- **The frontend talks to one hard-coded origin.** `API_BASE_URL` is provided in
  `app.config.ts`. Served from the same origin as the API it becomes an empty string; a
  real deployment would inject it at build time.
- **The Docker setup is unverified.** `docker-compose.yml` and `backend/Dockerfile` are
  written but have never been built: there is no Docker on the machine I developed this
  on. Everything else in this README was run.
- **The PostgreSQL path has not run on my machine either.** The code is written for it and
  CI is configured to prove it; until that pipeline has run, SQLite is what I have
  evidence for.
- **No authentication, no rate limiting.** See the extensions above.

## License

MIT, see [LICENSE](LICENSE).
