# CounselGrid

**Enterprise Outside Counsel & Conflict Governance System**

CounselGrid is an internal legal-operations platform for an in-house legal department. It runs matter intake, screens every outside firm on the panel against a conflict registry, ranks the eligible firms with a published weighting, and records each engagement decision in an audit log. It runs on Supabase (PostgreSQL with Row-Level Security) or, with no setup, on a local SQLite file.

> **Governance boundary.** CounselGrid is a B2B legal-operations tool. It does not provide legal advice, does not predict case outcomes and is not offered to the public. Conflict findings, waivers and engagement decisions remain the responsibility of licensed attorneys and the organization's ethics counsel.

All firm names, counterparties, conflicts and matters in the seed data are fictional.

---

## (a) The enterprise legal operations and governance problem

A large company's legal department sends work to dozens of outside firms. Three failures recur:

1. **Conflicts are found late.** A firm is engaged and only then discovers it represents the counterparty. Under ABA Model Rule 1.7 that firm usually has to withdraw, which wastes weeks and money and can disclose strategy. Former-client relationships (Model Rule 1.9) need an informed-consent waiver before work starts, and that step is easy to skip when intake happens over email.
2. **Firm selection is informal.** Matters go to the firm a business leader already knows, not to the panel firm with the deepest bench at the best rate, an active Master Service Agreement and acceptable data-security controls.
3. **Spend and compliance are opaque.** Nobody can quickly answer which departments drive spend, whether alternative fee arrangements (AFAs) actually save money, which MSAs expire next quarter, or which firms holding company data fall below the security floor.

CounselGrid replaces that informal process with one controlled intake path: every new matter passes the same gates, every decision is scored the same way, and every outcome is written to an append-only record.

## (b) Relational schema and conflict-gate algorithm

### Schema

```
outside_firms (1) ──< firm_practice_capabilities      one row per firm × corporate domain
      │
      ├──────────< conflict_registry                  append-only adverse-party disclosures
      │
      ├──────────< matter_engagements >───────────┐   selected_firm_id
      │                                           │
      └──────────< conflict_screening_log >───────┘   gate decision for every firm, per matter
```

| Table | Purpose | Key constraints |
|---|---|---|
| `outside_firms` | Panel firm master: tier, MSA status and expiry, blended rate, AFA availability, diversity certification, cyber score | `msa_status` ∈ {Active, Under Review, Expired}; cyber score 1–100 |
| `firm_practice_capabilities` | Partner bench depth and jurisdiction coverage per corporate domain | `UNIQUE (firm_id, corporate_domain)`; seven allowed domains |
| `conflict_registry` | Adverse-party relationships disclosed by each firm | Severity ∈ {Hard Block – Active Representation, Soft Check – Historical/Waivable, Clear}; no UPDATE/DELETE grants, so it is append-only |
| `matter_engagements` | Every matter: department, counterparty, budget, selected firm, fee structure, status, hours and spend | FK to `outside_firms`; status ∈ {Intake, Active, On Hold, Closed} |
| `conflict_screening_log` | What the gate decided for each panel firm when a matter was assigned | FK to the matter and firm; written in the same transaction as the matter |

Seed data covers 30 firms across New York, Chicago, Dallas, Washington D.C., Bentonville/Little Rock and San Francisco; 79 practice capabilities; 45 conflict entries (16 hard blocks, 19 soft checks, 10 cleared); and 25 matters. The full column reference is in [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md).

### Conflict gate

1. **Normalize** both the proposed counterparty and every registry entry: case-fold, transliterate to ASCII, change `&` to `and`, strip punctuation, and drop a leading "The" and trailing legal suffixes (Inc., LLC, Corp., Ltd., Co., LLP …).
2. **Score similarity** from 0 to 100 as the best of the full-string ratio and the token-sort ratio, plus the token-set ratio when the shorter name has at least five characters. The token-set ratio lets "ApexCart" match "ApexCart Technologies, Inc."; the length floor stops a bare "Co" from matching everything.
3. **Classify** each firm: any match ≥ 88 against a Hard Block entry disqualifies the firm. Otherwise a Soft Check match keeps the firm eligible but requires a waiver. Entries already marked Clear never block.

The gate is deliberately over-inclusive. A false positive costs an ethics reviewer a few minutes; a false negative can force counsel off a live matter. Every match is shown with the registry entry, the nature of the relationship and the score, so a person makes the final call.

### Gates, then the governance and value score

A firm is ranked only if it passes, in order: the conflict gate (no Hard Block), the MSA gate (status Active) and the capability gate (it has a practice in the matter's domain). Survivors receive a score out of 100:

| Component | Weight | Calculation (normalized 0–1 within the eligible pool) |
|---|---|---|
| Domain bench depth | 35% | partners in the domain ÷ deepest bench in the pool |
| Cost efficiency vs. budget | 30% | lowest blended rate in the pool ÷ this firm's rate. This equals the hours the budget buys at this firm relative to the best-value firm |
| Cyber / compliance | 20% | cyber compliance score ÷ 100 |
| AFA & diversity governance | 15% | AFA availability and diversity certification, weighted 60/40 toward AFA when the requested fee structure is Capped Fee or Fixed Retainer, and 40/60 when it is Hourly |

The UI shows the points each component contributes, and they sum to the total. The ranking also raises flags: an ethics waiver is required, the budget buys fewer than 150 hours at the firm's rate, the requested AFA is not offered, or the cyber score is below the panel floor of 75. Assigning counsel writes the matter and one screening-log row per panel firm in a single transaction.

## (c) Regulatory and UPL compliance design

| Risk | Design response |
|---|---|
| Unauthorized practice of law (Model Rule 5.5 and state UPL statutes) | The system only processes the organization's own operational data: who is conflicted, which firm, what it costs. It produces no legal conclusions, no advice to anyone outside the legal department and no outcome predictions. Every page shows a governance notice saying so. |
| Conflicts of interest (Model Rules 1.7, 1.9, 1.10) | Active representation is a hard block. Historical relationships need an explicit confirmation that ethics counsel has approved proceeding subject to an executed waiver before the engagement can be logged. Firm-level conflicts apply to the whole firm, which reflects imputation. |
| Tampering with conflict records | The registry is append-only. In PostgreSQL the application role has no UPDATE or DELETE privilege on it; in SQLite, triggers abort any update or delete. Corrections are new entries, so the history survives. |
| Auditability | Each assignment stores the gate outcome, the matched entity, the match score and the governance score for every panel firm. The disclosure register exports to CSV. |
| Data access (Supabase) | RLS is enabled on every table. `anon` has no access. Signed-in users can read; only users whose JWT `app_metadata.role` is `legal_ops` or `gc_admin` can write. The Streamlit server switches to the `counselgrid_app` role after connecting, so its own queries are governed by RLS too. |
| Data residency (local mode) | With no Supabase URL, all data lives in `data/counselgrid.db` on the host. Streamlit binds to `localhost` only, usage statistics are disabled and the UI loads no external fonts or scripts. |
| Credentials | Connection strings come only from environment variables or an untracked `.env`. `.env.example` documents them, and `.gitignore` excludes `.env` and the local database. |

These are product design controls. They are not a legal opinion about any jurisdiction's rules, and each deploying organization should have its own counsel review them.

## (d) Setup guide

Requires Python 3.10 or later.

### Local mode (no cloud)

```bash
./run.sh          # macOS / Linux
run.bat           # Windows
```

The first run creates a private virtual environment, installs dependencies, creates `data/counselgrid.db`, seeds it and opens http://localhost:8501.

Manual equivalent:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Supabase mode

1. Create a Supabase project and copy the connection string from **Project Settings → Database → Connection string (URI)**. The session pooler is recommended.
2. `cp .env.example .env` and set `SUPABASE_DB_URL`. Leave `SUPABASE_DB_ROLE=counselgrid_app`.
3. Apply the schema, RLS policies and seed data:
   ```bash
   PYTHONPATH=src python -m counselgrid.bootstrap
   ```
   This runs `sql/schema.sql`, then `sql/seed.sql`, then `sql/post_seed.sql`. Re-running it is safe; data is seeded only into an empty database. You can also paste the three files into the Supabase SQL editor in that order.
4. `streamlit run app.py`. The masthead shows which backend is active.

Set `COUNSELGRID_BACKEND=sqlite` to force local mode even when a Supabase URL is configured.

### A quick demo

On the first tab, enter the counterparty **Ironbridge Packaging** with domain *Supply Chain & Commercial Contracts*. One firm is disqualified for active representation, one is flagged for an ethics waiver and eleven are ranked. To see fuzzy matching, try **apexcart** (domain *IP & Patent Litigation*) or **greenleaf pet supply** (domain *M&A / Corporate Governance*).

### Verification

```bash
pip install pytest ruff
ruff check . && ruff format --check .
pytest                                     # 48 tests: gate, scoring, repository, analytics, Streamlit UI
COUNSELGRID_TEST_PG_DSN=postgresql://postgres@localhost/counselgrid_test pytest tests/test_postgres_rls.py
```

The PostgreSQL suite applies the real migration to a disposable database. It verifies the seed counts, runs the application end to end as `counselgrid_app`, and checks the RLS policies: `anon` is denied, viewers are read-only, `legal_ops` can write, and nobody can update or delete a conflict entry.

## Project layout

```
app.py                       Streamlit entry point
src/counselgrid/
  config.py                  backend selection from environment
  db.py                      SQLite and PostgreSQL backends, one interface
  conflict_gate.py           entity normalization and fuzzy conflict screening
  scoring.py                 eligibility gates and the weighted ranking
  repository.py              all SQL access
  analytics.py               spend, AFA savings, MSA alerts, KPIs
  bootstrap.py               Supabase provisioning command
  ui/                        theme and one module per tab
sql/
  schema.sql                 PostgreSQL / Supabase migration with RLS
  seed.sql                   portable seed data (PostgreSQL and SQLite)
  post_seed.sql              PostgreSQL identity-sequence reset
  sqlite_schema.sql          local fallback schema with append-only triggers
docs/                        architecture and data dictionary
tests/                       pytest suite
```

## License

MIT
