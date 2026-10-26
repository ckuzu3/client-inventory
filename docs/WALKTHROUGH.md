# Walkthrough

Why the backend is built this way, written so I can defend each decision rather than
recite it. The README says what it does; this says why, and where it stops.

## 1. The shape of the thing

Four layers, each with one job, and the dependency arrows only point one way:

| Layer | File | Knows about |
|---|---|---|
| Rules | `compliance.py` | facts, a baseline, a point in time |
| Contract | `schemas.py` | JSON in and out |
| Queries | `repository.py` | a session and ORM objects |
| HTTP | `api/routes.py`, `api/deps.py` | all of the above, and nothing else knows about it |

`compliance.py` imports no database and no web framework. That is not tidiness for its
own sake: it is why every rule is a plain function call in a test, with a small stub
instead of a session and a fixture tree.

`ClientFacts` in that module is a `Protocol`, not the ORM model. The evaluator states
what it needs — seven attributes — and both the real `Client` row and a four-line
dataclass in the tests satisfy it. Structural typing instead of an import.

## 2. The decision everything else follows from: compliance is derived

No column stores whether a client is compliant. Every response computes it from the
current facts and the active baseline.

**What that buys.** Raising `CLIENT_INVENTORY_BASELINE__MINIMUM_OS_VERSION` re-measures
the whole fleet on the next request. No migration, no backfill, no recalculation job, and
no window in which the stored verdict and the stored facts disagree. The baseline is also
returnable as an endpoint, so a frontend can say what it is showing instead of repeating
the thresholds.

**What it costs.** `WHERE compliant = false` does not exist. `only_with_findings` is
therefore an explicit pass in the application:

```python
candidates = repository.list_clients_for_evaluation(session, settings.compliance_filter_scan_limit)
matching = [client for client in candidates if evaluate(client, baseline, now)]
page = matching[offset : offset + limit]
```

That is a sequential scan with a ceiling, and I would rather have the ceiling visible in
the configuration than discover the cost as a slow endpoint. At a few thousand clients it
is milliseconds. If the fleet outgrew it, the fix is to materialise the findings on write
and reconcile when the baseline changes — at which point the baseline stops being free to
change, which is the trade I am choosing not to make yet.

## 3. Two tables, because history is the point

`client` is the current state, updated in place. `client_report` is append-only.

Keeping only the current state would have been less code and a worse tool: "when did this
device lose encryption" and "how long has it been drifting" are the questions that follow
the first one, and no amount of current state answers them.

### Out-of-order reports

This is the part I would raise in a review myself. A laptop that was offline for a week
submits last week's facts today. Written naively, that overwrites this morning's state
with stale data and moves `last_seen_at` backwards, making a healthy client look
abandoned.

```python
if reported_at >= ensure_utc(client.last_seen_at):
    client.last_seen_at = reported_at
    _apply_current_state(client, report, last_patched_at)
```

A late report always lands in the history and only updates the current state if it is
actually the newest. `first_seen_at` can move backwards, because learning about an earlier
sighting is new information. Two tests cover exactly this.

## 4. Things SQLite is not honest about

Both of these would have produced a green suite on SQLite and a broken service on
PostgreSQL. Both are now one function and one test.

**Foreign keys.** SQLite parses foreign key constraints and ignores them unless
`PRAGMA foreign_keys=ON` is set, per connection. Without it the cascade from `client` to
`client_report` silently does nothing. `database.py` registers a `connect` listener, and
`test_foreign_keys_are_enforced_on_a_sqlite_connection` reads the pragma back.

**Time zones.** SQLite has no timestamp type. A value written as timezone-aware comes back
naive; PostgreSQL returns it aware. Any age computed from the raw value is therefore right
in one environment and off by the local offset in the other. `timeutils.ensure_utc`
normalises on every read, a naive value being treated as UTC because that is the only
thing this application writes. `test_timeutils.py` deliberately mixes a naive value from
the database with an aware value from the clock.

**In-memory databases need the right pool.** `sqlite:///:memory:` gives each connection
its own empty database, so the fixture would create tables that the request never sees.
`create_db_engine` switches to `StaticPool` when it sees an in-memory URL, and
`_is_in_memory_sqlite` is tested against four URL shapes including
`?mode=memory&cache=shared`.

## 5. Build numbers

`versioning.py` exists for one bug:

```python
assert "10.0.9600" > "10.0.26100"            # true, as text
assert is_at_least("10.0.9600", "10.0.26100") is False
```

Compared as strings, an old Windows 8.1 build beats a current Windows 11 build, and an
outdated client passes the check. The parser splits on dots, rejects anything that is not
numeric, and pads the shorter version with zeros so `10.0` and `10.0.0` are equal. That
first assertion is in the test suite on purpose: it documents the bug the module prevents.

An unparsable version does not raise out of a report. `_check_os_version` catches it and
returns `OS_VERSION_UNREADABLE` as a medium finding, because one odd value should not fail
the whole evaluation.

## 6. The rules, and the judgement in them

Five rules, and four of them involved a decision rather than a threshold.

**The OS rule only applies to the OS it was written for.** The baseline holds a Windows
build number. Measuring macOS `15.1` against `10.0.26100` reports every Mac as hopelessly
out of date. A client whose `os_name` does not match `os_version_applies_to` is skipped
entirely, and the generated sample fleet contains Macs so this is visible rather than
theoretical.

**An unknown patch date outranks a late one.** `PATCH_LEVEL_UNKNOWN` is high,
`PATCH_LEVEL_OUTDATED` is medium. A late patch is a date in the plan. A client that has
never reported a patch date cannot be planned at all, and in practice it means something
stopped working that nobody has looked at. This mirrors a decision I made in another
project: a state that cannot be determined is not evidence of health.

**Encryption is a column, not a verdict.** Whether an unencrypted device breaks policy
depends on the tenant, so `require_encryption` is configurable and the fact is always
reported. Baking my assumption into the rule would make the tool wrong somewhere else.

**A zero-sized disk is not a division.** `free_disk_percent` returns `None` rather than
raising, and the rule is skipped. A client reporting nonsense about its disk should not
take the endpoint down with it.

Findings come back sorted by severity, so the first line of a worklist is the worst thing
about that machine. The sort is tested rather than incidental.

## 7. The contract at the edge

`ClientReportIn` is where a wrong assumption becomes a wrong row, so it is strict.

**Hostnames are lowercased.** Hostnames are case-insensitive, so `WS-0001` and `ws-0001`
are one machine. Without normalisation a collector that changes its capitalisation creates
a second row, and the fleet appears to grow while half the reports go to a ghost.

**Unknown fields are rejected.** `extra="forbid"`. A collector that sends
`encryption_enbaled` gets a 422 instead of having the value dropped, which is the failure
mode that makes an inventory quietly wrong. The cost is real: an older server rejects a
newer agent that added a field. I take that trade because a loud failure at rollout is
cheaper than a column of silently missing data, and because the API is versioned.

**A report dated far in the future is rejected.** Clock skew of minutes is normal on
managed clients and is accepted. A year is a broken clock, and storing it would keep that
device out of every staleness report forever. The boundary is one day, named as
`MAXIMUM_CLOCK_SKEW`, and both sides of it are tested.

**Free space larger than the disk is rejected** by a model validator, because it means the
collector is confused and the row would poison the disk rule.

## 8. Wiring, sessions and health

`create_app(settings)` takes its settings as an argument. The engine and the session
factory live on `app.state`. A test builds its own application against its own database,
and nothing is monkeypatched or overridden.

The session dependency commits when the handler returns and rolls back when it raises, so
a handler cannot forget either, and a failed request cannot leave half a submission
behind.

`/healthz` takes the engine, not a session. With a session dependency, a database outage
would fail the dependency before the handler ran and the endpoint would answer 500 — the
one situation the endpoint exists for. Taking the engine lets it answer
`{"status": "degraded", "database": "unreachable"}`, and there is a test that points an
app at an unwritable path to prove it.

The application never creates tables. Schema changes go through Alembic, so a process
start cannot silently alter a production database.

## 9. Testing strategy

93 tests, 99 percent of statements, floor enforced at 90 through
`fail_under` rather than a number in a README. Warnings are errors.

**Layered on purpose.** Rules are tested as pure functions against a stub. The repository
is tested against a real database. The API is tested through the real application with
`TestClient`. The same behaviour is not asserted at three levels.

**One fixed clock.** `FIXED_NOW` in `conftest.py` is a literal in the past, and every age
assertion is a literal number. It sits in the past so a test can add a day to it without
tripping the clock-skew validation, which is a constraint I found by writing a test that
failed.

**The migration test is the one I would keep.** It migrates a throwaway database, then
compares the tables and columns against `Base.metadata`. Without it the models and the
migration drift apart in silence, because the suite creates tables from the models and
never runs the migration at all. The downgrade is checked too.

**One switch runs everything against PostgreSQL.** `CLIENT_INVENTORY_TEST_DATABASE_URL`
replaces the in-memory SQLite for the whole suite, which is what the second CI job sets.
The schema is dropped and recreated per test, because a shared PostgreSQL keeps what the
last test left behind.

### What is not tested, and why

- **Docker.** `docker-compose.yml` and the `Dockerfile` have never been built. There is no
  Docker on the machine I wrote this on. They are my best reading of the documentation,
  not something I ran, and the README says so.
- **PostgreSQL, locally.** The code paths are written for it and CI is configured to prove
  it, but until that pipeline runs, SQLite is the evidence I have. The two uncovered
  branches in `database.py` are precisely the non-SQLite path.
- **Concurrency.** Two reports for the same new hostname arriving at once would both try
  to insert. The unique index makes the second one fail rather than duplicate, but there
  is no retry and no test. On PostgreSQL the honest fix is an upsert with
  `ON CONFLICT DO UPDATE`.
- **Authentication and rate limiting.** Neither exists. Reports are unauthenticated, which
  is acceptable on a closed network and nowhere else.
- **The collector.** Not in this repository, by choice: on Windows it is a PowerShell
  scheduled task with its own release cycle, and the API's contract is the boundary
  between them.

## 10. Tooling decisions

**Ruff for both lint and format**, with a wide rule set including `ANN` (annotations),
`D` (docstrings), `DTZ` (naive datetimes) and `ARG` (unused arguments). `DTZ` is the one
that pays for itself here: it catches `datetime.now()` without a time zone, which is the
bug `timeutils` exists to prevent, and the two deliberate naive values in the tests carry
a `noqa` that says why.

**mypy in strict mode over `src`, `tests` and `migrations`.** The suite is code too; a
test that type-checks is a test that still compiles after a refactor. Strict mode cost me
exactly one suppression: pydantic-settings accepts `_env_file` at runtime but does not
advertise it, so `build_settings` in `conftest.py` owns the single `type: ignore` and
every test goes through it.

For deliberately invalid payloads the tests call `ClientReportIn.model_validate(payload)`
rather than `ClientReportIn(**payload)`. `model_validate` accepts `Any`, which is exactly
right when the point of the test is that the input is wrong, and it removed a row of
ignores.

Instead of annotating the SQLite pragma listener's arguments as `Any`, `database.py`
declares two one-method protocols for the DBAPI connection and cursor. Three lines, no
`Any`, and the code now states what it expects of the driver object.

**A dependency I chose not to add.** Starlette's `TestClient` warns that it wants a
different HTTP library. With warnings as errors the suite stopped. I scoped that one
warning in `pyproject.toml` with a comment and a date, rather than pulling a second HTTP
client into the test environment for a message that does not change behaviour. If that
deprecation becomes a removal, the comment is where the next person starts.

## 11. If I had to extend this tomorrow

A new rule is a function in `compliance.py`, a member of `FindingCode`, and a test. A new
field is a column, a migration, a schema field, and the migration test catches it if I
forget one. A frontend needs no backend change: the baseline and the summary are already
endpoints.

The two things I would do before this ran anywhere real: per-device authentication on the
report endpoint, and an upsert on conflict instead of read-then-insert.
