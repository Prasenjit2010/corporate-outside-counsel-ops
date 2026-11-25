# CounselGrid Data Dictionary

Types are shown as PostgreSQL / SQLite. Every table has a surrogate integer primary key.

## outside_firms

| Column | Type | Notes |
|---|---|---|
| firm_id | integer identity / integer PK | |
| firm_name | text, unique | Legal name of the firm |
| hq_city, state | text, char(2) | Headquarters location |
| am_law_tier | text | `AmLaw 50`, `AmLaw 100`, `Regional Boutique` |
| diversity_certified | boolean / 0-1 | Holds a recognized diversity certification |
| msa_status | text | `Active`, `Under Review`, `Expired`. Only `Active` firms can be ranked |
| msa_expiration_date | date / ISO text | Drives MSA expiration alerts |
| blended_hourly_rate_usd | numeric(8,2) / real | Partner–associate blended rate agreed in the MSA |
| alternative_fee_arrangement_available | boolean / 0-1 | Firm offers capped or fixed fees |
| cyber_compliance_score | smallint 1–100 | Result of the outside-counsel security assessment; the panel floor is 75 |

## firm_practice_capabilities

| Column | Type | Notes |
|---|---|---|
| capability_id | integer PK | |
| firm_id | FK → outside_firms | Cascades on delete |
| corporate_domain | text | One of seven domains; unique per firm |
| partner_bench_depth | smallint ≥ 0 | Partners practicing in the domain |
| jurisdiction_coverage | text | States, federal circuits, agencies and international offices |

## conflict_registry (append-only)

| Column | Type | Notes |
|---|---|---|
| conflict_id | integer PK | |
| firm_id | FK → outside_firms | Restrict on delete |
| adverse_entity_name | text, non-blank | As disclosed by the firm. Matching is fuzzy, so variants are expected |
| matter_type | text | Nature of the relationship |
| conflict_severity | text | `Hard Block - Active Representation`, `Soft Check - Historical/Waivable`, `Clear` |
| logged_date | date | Defaults to today |

## matter_engagements

| Column | Type | Notes |
|---|---|---|
| matter_id | integer PK | |
| internal_department | text | `Supply Chain`, `Corporate Affairs`, `M&A`, `HR`, `Engineering` |
| matter_title | text | |
| corporate_domain | text | Same domain list as capabilities |
| opposing_or_counterparty_entity | text | The name screened by the conflict gate |
| estimated_budget_usd | numeric(14,2) > 0 | Budget cap at intake |
| selected_firm_id | FK → outside_firms, nullable | |
| fee_structure | text | `Hourly`, `Capped Fee`, `Fixed Retainer` |
| status | text | `Intake`, `Active`, `On Hold`, `Closed` |
| estimated_hours | integer ≥ 0 | Hourly-equivalent baseline: budget ÷ blended rate at intake |
| actual_spend_usd | numeric(14,2) ≥ 0 | Billed to date |
| created_at | timestamptz / ISO text | |

## conflict_screening_log

| Column | Type | Notes |
|---|---|---|
| screening_id | integer PK | |
| matter_id | FK → matter_engagements | |
| firm_id | FK → outside_firms | One row per panel firm per assignment |
| gate_outcome | text | `Hard Block`, `Soft Check - Waiver Required`, `Eligible`, `Ineligible - MSA`, `Ineligible - No Domain Capability` |
| matched_entity | text, nullable | Strongest registry match |
| match_score | numeric(5,1), nullable | Fuzzy similarity, 0–100 |
| governance_score | numeric(5,1), nullable | Ranking score, for rankable firms only |
| screened_at | timestamptz | |

## Derived metrics

| Metric | Definition |
|---|---|
| Hourly-equivalent cost | `estimated_hours × blended_hourly_rate_usd` |
| Realized AFA savings | Hourly-equivalent cost − actual spend, on **closed** Capped Fee and Fixed Retainer matters only |
| Effective rate | `actual_spend_usd ÷ estimated_hours` on closed matters |
| MSA alert | Expired (status Expired or past date) · Critical (≤ 30 days) · Renewal Due (≤ 90 days or Under Review) · Current |
