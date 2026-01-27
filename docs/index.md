# YGO-Combo-Pipeline Documentation

Welcome to the YGO-Combo-Pipeline documentation.

## Quick Start

```bash
# Run end-to-end pipeline (sampling → parallel enumeration → ranking)
python scripts/run_pipeline.py --samples 100 --workers 4

# Run with checkpointing for long jobs
python scripts/run_pipeline.py --samples 500 --checkpoint-dir ./checkpoints

# Resume interrupted run
python scripts/run_pipeline.py --checkpoint-dir ./checkpoints --resume
```

## Quick Links

- [Getting Started](guides/GETTING_STARTED.md) - Installation and first run
- [Architecture Overview](architecture/OVERVIEW.md) - System design
- [Search Strategy](architecture/SEARCH_STRATEGY.md) - How combo enumeration works

## Documentation Structure

### Architecture
System design and technical decisions.
- [Overview](architecture/OVERVIEW.md) - High-level architecture
- [Search Strategy](architecture/SEARCH_STRATEGY.md) - IDDFS, transposition tables
- [Decision Log](architecture/DECISION_LOG.md) - Why we chose X over Y
- [Roadmap](architecture/ROADMAP.md) - Implementation priorities
- [Pipeline Roadmap](architecture/PIPELINE_ROADMAP.md) - Detailed pipeline roadmap

### Guides
Step-by-step instructions for common tasks.
- [Getting Started](guides/GETTING_STARTED.md) - Setup and installation
- [Adding Cards](guides/ADDING_CARDS.md) - How to add new card support
- [Running Enumeration](guides/RUNNING_ENUMERATION.md) - How to enumerate combos
- [Troubleshooting](guides/TROUBLESHOOTING.md) - Common issues and solutions
- [New Card Protocol](guides/NEW_CARD_PROTOCOL.md) - Protocol for adding new cards

### Reference
Technical reference documentation.
- [Game Rules](reference/GAME_RULES.md) - YGO rules reference
- [Message Handlers](reference/MESSAGE_HANDLERS.md) - MSG_* handler documentation
- [Card Data](reference/CARD_DATA.md) - Card data format reference
- [Effect Verification](reference/EFFECT_VERIFICATION_CHECKLIST.md) - Effect verification checklist
- [Project Inventory](reference/PROJECT_INVENTORY.md) - Complete file inventory

### Research
Background research and analysis.
- [Architecture Notes](research/ARCHITECTURE_NOTES.md) - Architecture research
- [YGO Agent Analysis](research/YGO_AGENT_ANALYSIS.md) - ML agent compatibility
- [Fiendsmith Audit](research/FIENDSMITH_AUDIT.md) - Card audit for test deck
- [CFFI Plan](research/CFFI_PLAN.md) - CFFI binding design (historical)

### Handoffs
Session handoff documents.
- [TODO Next Session](handoffs/TODO_NEXT_SESSION.md) - Current state and next steps

### Legacy
Historical documents (kept for reference).
- [Legacy Docs](legacy/) - Old planning documents
- [Combo Enumeration Handoff](legacy/HANDOFF_COMBO_ENUMERATION.md) - Archived
- [Enumeration Investigation](legacy/HANDOFF_ENUMERATION_INVESTIGATION.md) - Archived
