# Yu-Gi-Oh Analysis Pipeline — Rules & Standards

## 0) Purpose
This repo produces repeatable, auditable Yu-Gi-Oh analyses (deck stats, consistency/probability, matchup notes, and meta summaries) from well-defined inputs using a versioned pipeline.

Non-goals (for now):
- Real-time “live” scraping without permission
- Proprietary datasets without explicit rights
- Unverifiable claims without citing a source

## 1) Core Principles
1. Reproducibility: same inputs + same version = same outputs.
2. Traceability: every derived artifact links back to raw inputs + parameters.
3. Minimal assumptions: any assumption must be documented in “Assumptions”.
4. Deterministic defaults: randomness must be seeded and recorded.
5. Fail-closed: if key inputs are missing or malformed, stop with a clear error.

## 2) Project Structure (Conceptual)
- /docs: specs, glossary, analysis definitions
- /data_raw: immutable raw inputs (event results, decklists, banlists snapshots)
- /data_cache: cached card database snapshots (source + timestamp)
- /data_processed: normalized canonical datasets used by analyses
- /reports: generated outputs (markdown/html/pdf), never hand-edited
- /src: pipeline code (Codex writes this), organized by stages
- /tests: unit/integration tests for each stage

## 3) Data Sources & Licensing Rules
1. Prefer sources with explicit permission for programmatic access and caching.
2. Record for each source:
   - Name + URL
   - Retrieval date/time
   - License/terms notes
   - Fields used
3. Do not redistribute assets that violate terms (e.g., images) unless permitted.
4. If a source asks to cache locally and limit calls, comply by default.

## 4) Canonical Entities & Normalization
### 4.1 Card identity
- Canonical key: (card_id) when available; otherwise normalized card name.
- Maintain a “name_normalization” rule:
  - Trim whitespace, normalize punctuation, handle alternate spellings when needed.
- Store both: display name and canonical normalized name.

### 4.2 Deck identity
- Deck = main + extra + side, each a multiset of cards with counts.
- Deck input formats supported must be explicitly listed in docs (e.g., YDK, plain text).

### 4.3 Format context
Every analysis MUST declare:
- Game: TCG / OCG / Master Duel / custom
- Banlist snapshot identifier + date
- Set of rules (e.g., current Master Rule) if relevant
No context → no analysis output.

## 5) Pipeline Stages (Definitions of Done)
### Stage A — Ingest
- Inputs: decklists, event results, banlist snapshot, card database snapshot
- Output: raw copies + manifest.json describing what was ingested

DoD:
- Every input file hashed (sha256) and recorded in a manifest
- Validation: required fields present

### Stage B — Normalize
- Output: canonical tables (cards, decks, events) with stable schemas

DoD:
- No duplicate canonical IDs
- All card references resolved (or explicitly listed as unresolved)

### Stage C — Analyze
Analyses are modular “reports” with fixed inputs/outputs.
Each analysis must specify:
- Required inputs
- Parameters (with defaults)
- Output artifacts produced

DoD:
- Writes outputs only to /reports (or /data_processed if it’s an intermediate)
- Logs key parameters and dataset versions used

### Stage D — QA & Publishing
DoD:
- Unit tests for parsing/normalization edge cases
- A single command (documented) produces a full run
- Reports include a footer: dataset versions + git commit hash

## 6) Standard Analyses (Initial Set)
1. Deck profile:
   - Counts by type (monster/spell/trap), extra deck breakdown
   - Engine/staple detection (rule-based, documented)
2. Consistency:
   - Opening hand odds for defined “combo pieces” (hypergeometric)
   - “Sees starter by turn N” calculations
3. Matchup notes (optional, manual+structured):
   - Side patterns, key choke points (must be tagged as “opinion”)
4. Meta summary (if event results available):
   - Top decks frequency, trend over time windows
   - Regional segmentation if provided

## 7) Reporting Rules
- Every number in a report must be reproducible from stored inputs.
- Every chart/table states:
  - population (what decks/events)
  - filter rules
  - date range
- Separate “facts” vs “interpretation” sections.

## 8) Logging & Debuggability
- Each stage logs:
  - start/end timestamps
  - input manifest IDs
  - output file list
  - warnings (non-fatal) and errors (fatal)

## 9) Codex Workflow Rules (No hand coding)
Codex is the implementation agent. Humans provide specs + review.
For every Codex task:
1. Provide the exact file targets and acceptance criteria.
2. Require: tests added/updated, and a short “what changed” summary.
3. Prefer small PR-sized changes.
4. If behavior changes, update docs first or in the same change.

## 10) Assumptions (Maintain This List)
- (Add assumptions here as they arise; each dated and justified.)

## 11) Glossary (Maintain This List)
- Starter, Extender, Brick, Engine, Staple, Choke point, etc.

## 12) Card Library Contract (Single Source of Truth)
### Purpose
The Card Library is the canonical, versioned dataset of official TCG card text (PSCT) + provenance.
All downstream systems (deck odds, hand-trap resilience sims, combo search) MUST read from this library and MUST NOT embed card text elsewhere.

### Source & Provenance
- Primary source: Konami official TCG database (db.yugioh-card.com)
- Every populated row MUST include:
  - Official DB URL
  - CID
  - Verified Date (YYYY-MM-DD)
- Raw HTML used for extraction MUST be cached per CID for reproducibility.

### Required Columns (Minimum)
- Name (official formatting)
- Card Type / Subtype/Icon
- Attribute / Typing / Level-Rank-Link / ATK / DEF (where applicable)
- Summoning Requirements / Materials (Extra Deck only)
- Official Card Text (Exact, TCG) — verbatim PSCT, preserving line breaks
- Official DB URL, CID, Verified Date
- Lookup Notes (only for exceptions)

### Normalization Rules
- Stored Name MUST match official DB formatting.
- Normalize only for lookup purposes (curly quotes/hyphens → ASCII); after match, overwrite Name with the official spelling/punctuation.
- No “helpful edits” to PSCT. Store exactly what the official DB displays.

### Separation of Concerns
- Official text + metadata live in the Card Library only.
- Any human judgments (Starter/Extender/Brick tags, “engine” membership, combo notes, choke points, etc.) MUST live in a separate curated layer (e.g., card_tags.*) keyed by CID.

### Canonical Location
- The canonical clean card library lives at `data_processed/Fiendsmith_Master_Card_Library_CLEAN.xlsx` and `data_processed/Fiendsmith_Master_Card_Library_CLEAN.json`.
- Root-level wrapper scripts are convenience entrypoints only; they must not redefine canonical data paths.

### Update & Release Procedure
1. Run the population script (reproducible) against the current spreadsheet.
2. Cache HTML per CID.
3. Run QA gates (below).
4. Commit outputs + cache manifest together (same commit).

### QA Gates (Fail-Closed)
- Row count preserved and stable ordering
- No duplicate Names after official-name replacement
- No blank Official Card Text (must be full text or NOT FOUND)
- All populated rows must have URL + CID + Verified Date
- Extra Deck monsters must have requirements/materials captured correctly
- Export both XLSX + JSON successfully

## 13) Card Tags Contract (Curated Layer)
### Purpose
card_tags.* is the curated, human-judgment layer keyed by CID. It MUST NOT contain PSCT text or near-verbatim effect language.

### Required Files
- card_tags.xlsx
- card_tags.jsonl (one JSON object per row)

### Canonical Key
- CID is required for every row and MUST match a CID in the Card Library.

### Required Columns + Formatting
- CID (string)
- Name (Official formatting; must match Card Library after normalization)
- Role (optional; semicolon-separated)
- OPT (optional; single value)
- Lock (optional; semicolon-separated)
- Primary Actions (optional; semicolon-separated)
- Resource Delta (optional; semicolon-separated)
- Combo Relevance Notes (optional; short free text, no PSCT)
- Role_Suggested / OPT_Suggested / PrimaryActions_Suggested / Locks_Suggested (optional; machine-generated)
- NeedsReview (TRUE/FALSE; set TRUE when suggestions are present)

### Controlled Vocab
- Allowed values, schema_version, and formatting rules live in `config/card_tags_schema.json` and MUST be treated as the single source of truth.
- Multi-value fields are semicolon-separated and case-insensitive.

### QA Gates (Fail-Closed)
- CID missing or duplicated
- CID not present in Card Library
- Name mismatch vs Card Library (after normalization)
- Values outside controlled vocab
- PSCT leakage detected in any tag field
- XLSX ↔ JSONL mismatch row-for-row (by CID and order)

### How to Fill Tags Without PSCT Leakage
- Use abbreviations (SS, NS, GY, OPT) and short categorical tags.
- Prefer role/action tags over verbatim effect wording.
- Suggested fields are machine-generated; final fields are curated and must be reviewed.

## 14) QA Tooling (Spot-Check Report)
Run the spot-check report after every card library refresh and before any release. A PASS means the extracted PSCT in the clean library matches the cached official Konami HTML byte-for-byte (after normalizing line endings to \n), including punctuation normalization edge cases.

Validator command: run `python scripts/qa/validate_card_tags.py` to fail-closed on CID/name integrity, vocab violations, PSCT leakage, and XLSX/JSONL mismatches.
Tag review command: run `python scripts/qa/tag_review_report.py` to produce `tag_review_report.md`.
QA stage command: run `python scripts/qa/run_qa.py` to produce `reports/spot_check_report.md`, validate `card_tags.*`, and write `tag_review_report.md`.

## 15) Decklist Ingest + Normalize
### Supported Deck Formats
- YDK files with #main / #extra / !side sections (CID lines supported)
- Plain text lists with flexible counts (e.g., `3 Card Name`, `Card Name x3`, `x3 Card Name`)

### Canonical Deck Schema
The normalized deck JSON is written to `data_processed/decks/<deck_name>.json`:
- deck_name
- format_context (game, banlist_id, banlist_date, rules)
- main / extra / side: [{cid, name, count}]
- unresolved: [] (must be empty for success)

### Ingest Outputs
- Raw manifest: `data_raw/<deck_name>/manifest.json` (sha256 + parse metadata)
- Deck JSON: `data_processed/decks/<deck_name>.json`

## 16) Deck Profile Report
Run `python scripts/deck_pipeline.py --input <deck_file> --deck-name <name>` to produce:
- `data_raw/<deck_name>/manifest.json`
- `data_processed/decks/<deck_name>.json`
- `reports/deck_profile_<deck_name>.md`

## 17) Simulation Rules Contract (Combo Engine)
The simulator must follow the TCG rules baseline: `docs/tcg_rules_baseline.md`.

### Combo-first implementation order
Phase 1: goldfish combo engine
Phase 2: interaction/hand-trap resilience
Phase 3: full duel completeness

### Acceptance Criteria
- No simulator work starts until `docs/tcg_rules_baseline.md` exists.
- Phase 1 invariants are written and reviewed before implementation begins.

## 18) Simulation Rules
Kernel contract: `docs/simulation_kernel_contract.md`
Rules coverage matrix: `docs/rules_coverage_matrix.md`
Acceptance tests plan: `docs/acceptance_tests_plan.md`
