# Research Log

> Last Updated: 2026-01-25
> Purpose: Technical research, experiments, and architectural decisions

This document contains research findings and decision records extracted from the main roadmap.
For current project status, see [COMBO_PIPELINE_ROADMAP.md](COMBO_PIPELINE_ROADMAP.md).

---

## Table of Contents

1. [ygo-agent Analysis](#ygo-agent-analysis)
2. [Problem Structure Analysis](#problem-structure-analysis)
3. [Key Discovery: Tract vs Sanct Ordering](#key-discovery-tract-vs-sanct-ordering)
4. [Experimental Data](#experimental-data)
5. [Decision Log](#decision-log)

---

## ygo-agent Analysis

**Date:** 2026-01-24
**Repository:** https://github.com/sbl1996/ygo-agent

### Key Findings

1. **State Representation** (41 features per card):
   - Card ID (16-bit), Location, Sequence, Controller
   - Position, Overlay status, Attribute, Race, Level
   - Counter, Negated flag, ATK/DEF (16-bit float transform)
   - 25 type flags (monster/spell/trap subtypes)

2. **Global Features** (23 dimensions):
   - LP (both players), Turn count, Phase ID
   - Is first player, Is my turn
   - Card counts per location (14 zones)

3. **Key Insight**: ygo-agent does NOT hash/cache intermediate states. They rely on neural network generalization instead.

4. **Relevance to our project:**
   - Proves ygopro-core can be wrapped effectively
   - Their approach optimizes for winning games; we optimize for board quality
   - They need generalization across all cards; we have fixed 26-card library
   - We need exact state hashing; they use learned embeddings

---

## Problem Structure Analysis

Our problem differs from typical game AI:

| Aspect | Typical Game AI | Our Problem |
|--------|-----------------|-------------|
| Players | Adversarial (2+) | Single-player optimization |
| Information | Hidden cards | Known information (goldfish) |
| Tree structure | Infinite/very deep | Finite (OPT bounds depth) |
| Objective | Win/loss | Board quality metric |
| Generalization | Many decks/cards | Fixed 26-card library |

**Conclusion:** This is closer to **puzzle solving** than game playing:
- Find shortest/best path to target state
- Dynamic programming / memoization applicable
- Could potentially solve exactly for small libraries
- State space is finite and enumerable

---

## Key Discovery: Tract vs Sanct Ordering

### Problem

Depth-first search explores actions in order returned by engine:
- Index 2: Sanct - creates token
- Index 3: Tract - searches and discards

**Sanct is explored before Tract**, leading to:
- 1000+ paths through Token → Requiem line
- Tract line (stronger) never reached within path limits

### Evidence

At Depth 30:

| Search Target | Terminals | % |
|---------------|-----------|---|
| Tract | 117 | 81.2% |
| Sanct | 24 | 16.7% |

**Tract leads to 4.9x more terminals than Sanct** - it enables the Lurrie line which is the strongest combo path.

### Recommended Solutions

1. **Action ordering heuristic** - Prioritize Tract over Sanct
2. **Round-robin exploration** - One level of each branch before deeper
3. **Breadth-first at low depths** - BFS until depth 5, then DFS

---

## Experimental Data

### Verification Run (2026-01-24)

| Metric | Value |
|--------|-------|
| Depth Limit | 25 |
| Paths Explored | 1,000 |
| Terminals Found | 150 |
| Transposition Hit Rate | **39.3%** |
| Max Depth Reached | 24 |

### Board Quality Distribution

| Tier | Count | Percentage |
|------|-------|------------|
| S-tier | 5 | 3.3% |
| A-tier | 9 | 6.0% |
| C-tier | 61 | 40.7% |
| Brick | 75 | 50.0% |

### Cards Never Reached (Extra Deck)

- A Bao A Qu (Link-4) - needs too many materials at depth 25
- Desirae - needs Engraver + 2 LIGHT Fiends
- Rextremende - two-step Fusion
- Luce - GY-based Fusion, needs setup

**Observation:** Depth 25 is insufficient for full combo.

### State Growth Pattern

| Depth | Unique States | Growth |
|-------|---------------|--------|
| 5 | 4 | - |
| 10 | 12 | 3x |
| 15 | 36 | 3x |
| 20 | 341 | 9.5x |

**Insight:** State explosion happens after depth 15 when multiple combo paths diverge.

---

## Decision Log

### D001: CFFI over Subprocess ✅
- **Decision:** CFFI direct binding to ocgcore
- **Rationale:** 100% rule accuracy with good performance
- **Status:** Implemented, working

### D002: Holactie as Dead Card ✅
- **Decision:** Use passcode 10000040 (internal EDOPro ID)
- **Rationale:** Requires tributing 3 Egyptian Gods, impossible in our setup

### D003: Position Collapse (ATK Only) ✅
- **Decision:** Always choose ATK position, don't branch
- **Rationale:** 35% path reduction; no effects care about position

### D004: Zone Collapse (First Available) ✅
- **Decision:** Always use first available zone
- **Rationale:** 170 zone selections × 5 zones would massively increase paths

### D005: Trust Engine for OPT ✅
- **Decision:** Don't track OPT ourselves; observe via legal actions
- **Rationale:** Engine already tracks internally

### D006: Zone-Agnostic Board Hashing ✅
- **Decision:** Hash by card presence, not exact zone position
- **Rationale:** Most terminals equivalent regardless of zone

### D007: Card Deduplication Strategy ✅
- **Decision:** When selecting cards, deduplicate by passcode
- **Rationale:** Selecting Holactie #1 vs #2 produces identical outcomes

### D008: Legal Actions in State Hash ✅
- **Decision:** Include activatable effects in intermediate state hash
- **Rationale:** Engine is authoritative; simpler than parsing hints

### D009: Card Identity Tracking ✅
- **Decision:** Use just passcode, not instance ID
- **Rationale:** All copies of same card are functionally equivalent

### D010: Terminal Board Equivalence ✅
- **Decision:** Zone-agnostic - same passcodes = same board
- **Risk:** May need revisiting if Cross-Sheep line becomes important

### D011: Three-Layer State Model ✅
- **Decision:** Separate BoardSignature / IntermediateState / ActionSequence
- **Rationale:** Different use cases need different granularity

### D012: Transposition Table Eviction Policy ✅
- **Decision:** Depth-prioritized eviction when full (updated 2026-01-25)
- **Rationale:** Keeps entries closer to good boards; evicts shallow states first

---

*Document version: 1.0*
*Created: 2026-01-25*
