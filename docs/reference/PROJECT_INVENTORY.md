# Project Inventory Report

> Generated: 2026-01-25
> Working Directory: `src/cffi`
> Total Size: 18 MB (cffi dir) | ~930 MB (full Testing dir)

---

## Table of Contents

1. [Summary](#summary)
2. [Large Files (>1MB)](#large-files-1mb)
3. [Source Code Files](#source-code-files)
4. [Generated Output Files](#generated-output-files)
5. [Dependencies](#dependencies)
6. [Configuration Files](#configuration-files)
7. [Documentation](#documentation)
8. [Hidden Files](#hidden-files)
9. [Potential Duplicates/Backups](#potential-duplicatesbackups)
10. [Full File Listing](#full-file-listing)

---

## Summary

### Directory Structure Overview

```

├── src/cffi/           # Current working directory (18 MB)
│   ├── build/          # Compiled binaries (2.7 MB)
│   ├── deps/           # Lua 5.3.5 source (2.3 MB)
│   └── .pytest_cache/  # Test cache (20 KB)
├── config/             # Configuration JSON files
├── docs/               # Documentation
├── scripts/            # Utility scripts
├── tests/              # Test files
└── [various handoff/backup zips]
```

### File Type Distribution (cffi directory)

| Type | Count | Total Size |
|------|-------|------------|
| Python (.py) | 13 | ~300 KB |
| JSON (.json) | 5 | ~14.8 MB |
| C source (.c) | 28 | ~510 KB |
| C headers (.h) | 28 | ~150 KB |
| Object files (.o) | 28 | ~280 KB |
| Binary executables | 3 | ~3.2 MB |
| Other | 15 | ~400 KB |

---

## Large Files (>1MB)

| File | Size | Type | Purpose |
|------|------|------|---------|
| `enumeration_depth20.json` | 3.7 MB | JSON | Enumeration output (depth 20) |
| `enumeration_depth25.json` | 3.6 MB | JSON | Enumeration output (depth 25) |
| `enumeration_depth30.json` | 3.0 MB | JSON | Enumeration output (depth 30) |
| `build/libygo.dylib` | 2.7 MB | Binary | ygopro-core shared library |
| `verification_run.json` | 1.7 MB | JSON | Latest verification results |

### Large Files in Parent Directory

| File | Size | Type | Purpose |
|------|------|------|---------|
| `testing.zip` | 512 MB | Archive | Full project backup |
| `full_folder_20260120_100347.zip` | 279 MB | Archive | Older full backup |
| `full_folder_20260119_182207.zip` | 93 MB | Archive | Older full backup |
| `cards.cdb` | 7.1 MB | SQLite | Card database |

---

## Source Code Files

### Core Implementation (Active Development)

| File | Size | Modified | Purpose |
|------|------|----------|---------|
| `combo_enumeration.py` | 49.6 KB | Jan 24 20:48 | Main enumeration engine - explores combo paths |
| `state_representation.py` | 17.8 KB | Jan 24 20:42 | BoardSignature, IntermediateState, ActionSpec classes |
| `transposition_table.py` | 2.0 KB | Jan 24 20:36 | Memoization cache for explored states |
| `ocg_bindings.py` | 5.7 KB | Jan 24 08:50 | CFFI FFI interface to ygopro-core |
| `test_fiendsmith_duel.py` | 21.9 KB | Jan 24 09:14 | Duel creation and card loading utilities |
| `__init__.py` | 1.2 KB | Jan 24 08:51 | Package initialization |

### Test Files

| File | Size | Modified | Purpose |
|------|------|----------|---------|
| `test_state.py` | 15.7 KB | Jan 24 20:42 | 19 unit tests for state representation |
| `test_full_combo.py` | 46.7 KB | Jan 24 10:22 | Full combo line tests |
| `verify_all_cards.py` | 46.2 KB | Jan 24 10:49 | Card verification scripts |
| `test_opt_tracking.py` | 14.2 KB | Jan 24 17:50 | OPT (once-per-turn) tracking tests |
| `test_activate_engraver.py` | 19.4 KB | Jan 24 09:21 | Engraver activation tests |
| `test_create_duel.py` | 6.7 KB | Jan 24 08:51 | Duel creation tests |

### Build/Utility Scripts

| File | Size | Modified | Purpose |
|------|------|----------|---------|
| `build/smoke_test_ctypes.py` | 601 B | Jan 24 00:00 | ctypes library loading test |
| `build/smoke_test_edo9300.py` | 2.2 KB | Jan 24 08:50 | edo9300 core test |

---

## Generated Output Files

All JSON files in this category are **outputs from enumeration runs** - not source code.

| File | Size | Modified | MD5 Hash | Notes |
|------|------|----------|----------|-------|
| `enumeration_depth20.json` | 3.7 MB | Jan 24 15:58 | `db4839cd...` | Depth 20 run |
| `enumeration_depth25.json` | 3.6 MB | Jan 24 16:26 | `6b681bd0...` | Depth 25 run |
| `enumeration_depth30.json` | 3.0 MB | Jan 24 16:27 | `f0880eed...` | Depth 30 run |
| `enumeration_results.json` | 255 KB | Jan 24 15:45 | `feeb2249...` | Earlier results |
| `verification_run.json` | 1.7 MB | Jan 24 20:48 | `7b8ed3d0...` | Latest verification |

**Note:** All hashes are unique - no duplicate content detected.

---

## Dependencies

### Lua 5.3.5 (`deps/lua-5.3.5/`)

Third-party dependency for ygopro-core scripting engine.

| Component | Files | Size | Modified |
|-----------|-------|------|----------|
| Source code (.c) | 28 | ~510 KB | 2017-2018 |
| Headers (.h) | 28 | ~150 KB | 2013-2018 |
| Object files (.o) | 28 | ~280 KB | Jan 23 23:38 |
| Static library (`liblua.a`) | 1 | 327 KB | Jan 23 23:38 |
| Executables (`lua`, `luac`) | 2 | 418 KB | Jan 23 23:38 |
| Documentation | 10 | ~380 KB | 2006-2018 |

### Build Artifacts (`build/`)

| File | Size | Modified | Purpose |
|------|------|----------|---------|
| `libygo.dylib` | 2.7 MB | Jan 24 08:57 | Compiled ygopro-core (macOS) |
| `smoke_test_ctypes.py` | 601 B | Jan 24 00:00 | Library load test |
| `smoke_test_edo9300.py` | 2.2 KB | Jan 24 08:50 | Core functionality test |

---

## Configuration Files

Located in `config/`:

| File | Size | Modified | Purpose |
|------|------|----------|---------|
| `locked_library.json` | 23.8 KB | Jan 24 11:11 | 26-card library definition |
| `verified_effects.json` | 26.0 KB | Jan 23 21:19 | Verified card effect data |
| `lua_ground_truth_cases.json` | 7.3 KB | Jan 23 20:58 | Lua script test cases |
| `card_tags_schema.json` | 3.6 KB | Jan 19 14:50 | Card tagging schema |
| `endboard_piece_buckets.json` | 1.8 KB | Jan 21 21:09 | End board categorization |
| `cdb_aliases.json` | 727 B | Jan 23 22:30 | Card database aliases |

---

## Documentation

Located in `docs/`:

| File | Size | Modified | Purpose |
|------|------|----------|---------|
| `COMBO_PIPELINE_ROADMAP.md` | 60.0 KB | Jan 24 21:32 | **Primary roadmap document** |
| `ARCHITECTURE_RESEARCH.md` | 50.8 KB | Jan 23 23:25 | Architecture research notes |
| `EFFECT_VERIFICATION_CHECKLIST.md` | 22.8 KB | Jan 23 19:09 | Effect verification status |
| `GAME_RULES_REFERENCE.md` | 11.8 KB | Jan 23 22:48 | YGO rules reference |
| `CARD_DATA.md` | 11.4 KB | Jan 23 12:32 | Card data documentation |
| `CFFI_PROTOTYPE_PLAN.md` | 11.6 KB | Jan 23 23:31 | CFFI implementation plan |
| `EFFECT_VERIFICATION_REMAINING.md` | 10.1 KB | Jan 23 19:15 | Remaining verifications |
| `YGO_AGENT_ANALYSIS.md` | 7.6 KB | Jan 24 20:00 | ygo-agent reference analysis |
| `NEW_CARD_PROTOCOL.md` | 7.3 KB | Jan 23 19:44 | Protocol for adding cards |
| `HANDOFF_COMBO_ENUMERATION.md` | 7.1 KB | Jan 24 11:46 | Handoff documentation |
| Other docs | 7 files | ~15 KB | Various specifications |

---

## Hidden Files

### `.pytest_cache/` (cffi directory)

| File | Size | Purpose |
|------|------|---------|
| `CACHEDIR.TAG` | 191 B | Cache directory marker |
| `README.md` | 302 B | pytest cache documentation |
| `.gitignore` | 37 B | Git ignore rules |
| `v/cache/nodeids` | 2 B | Test node IDs |
| `v/cache/lastfailed` | 27 B | Last failed test info |

### Parent Directory Hidden Files

| File | Size | Purpose |
|------|------|---------|
| `.DS_Store` | 10.0 KB | macOS Finder metadata |
| `.gitignore` | 107 B | Git ignore rules |
| `.git/` | - | Git repository |
| `.venv/` | - | Python virtual environment |
| `.claude/` | - | Claude Code project settings |
| `.pytest_cache/` | - | Test cache |

---

## Potential Duplicates/Backups

### Handoff Archives (Parent Directory)

Multiple timestamped handoff archives exist. These are **intentional backups** for session continuity:

| Pattern | Count | Total Size | Latest |
|---------|-------|------------|--------|
| `handoff_context_*.zip` | 10 | ~1.5 MB | Jan 23 21:04 |
| `handoff_min_*.zip` | 10 | ~400 KB | Jan 23 21:04 |
| `handoff_*.zip` | 4 | ~910 KB | Jan 23 18:36 |
| `updates_*.zip` | 10 | ~130 KB | Jan 23 21:23 |
| `full_folder_*.zip` | 2 | ~372 MB | Jan 20 10:03 |

**Recommendation:** Consider archiving or removing older handoff files to save ~370 MB.

### Enumeration Results (cffi directory)

| File | Description | Recommended Action |
|------|-------------|-------------------|
| `enumeration_depth20.json` | Depth 20 test run | Keep for comparison |
| `enumeration_depth25.json` | Depth 25 test run | Keep for comparison |
| `enumeration_depth30.json` | Depth 30 test run | Keep for comparison |
| `enumeration_results.json` | Earlier results | **Consider removing** - superseded |
| `verification_run.json` | Latest verification | Keep as primary |

### Excel Duplicates (Parent Directory)

| File | Size | Notes |
|------|------|-------|
| `Fiendsmith_Card_Library_CLEAN_TEMPLATE.xlsx` | 9.7 KB | Template |
| `Fiendsmith_Master_Card_Library_CLEAN.xlsx` | 9.7 KB | **Identical size** - likely duplicate |

---

## Full File Listing

### `src/cffi/` (Sorted by Size)

```
SIZE       MODIFIED         FILE
─────────────────────────────────────────────────────────────
3,860,122  2026-01-24 15:58  enumeration_depth20.json
3,781,972  2026-01-24 16:26  enumeration_depth25.json
3,164,897  2026-01-24 16:27  enumeration_depth30.json
2,790,560  2026-01-24 08:57  build/libygo.dylib
1,789,547  2026-01-24 20:48  verification_run.json
  334,904  2026-01-23 23:38  deps/lua-5.3.5/src/liblua.a
  327,398  2018-06-26        deps/lua-5.3.5/doc/manual.html
  260,613  2026-01-24 15:45  enumeration_results.json
  242,448  2026-01-23 23:38  deps/lua-5.3.5/src/lua
  185,208  2026-01-23 23:38  deps/lua-5.3.5/src/luac
   50,804  2026-01-24 20:48  combo_enumeration.py
   47,815  2026-01-24 10:22  test_full_combo.py
   47,310  2026-01-24 10:49  verify_all_cards.py
   22,440  2026-01-24 09:14  test_fiendsmith_duel.py
   19,901  2026-01-24 09:21  test_activate_engraver.py
   18,210  2026-01-24 20:42  state_representation.py
   16,058  2026-01-24 20:42  test_state.py
   14,564  2026-01-24 17:50  test_opt_tracking.py
    6,879  2026-01-24 08:51  test_create_duel.py
    5,851  2026-01-24 08:50  ocg_bindings.py
    2,259  2026-01-24 08:50  build/smoke_test_edo9300.py
    2,069  2026-01-24 20:36  transposition_table.py
    1,206  2026-01-24 08:51  __init__.py
      601  2026-01-24 00:00  build/smoke_test_ctypes.py
```

### Lua Source Files (deps/lua-5.3.5/src/)

```
28 .c files  (~510 KB total)  - Lua interpreter source
28 .h files  (~150 KB total)  - Lua headers
28 .o files  (~280 KB total)  - Compiled object files
 1 .a file   (327 KB)         - Static library
 2 binaries  (418 KB)         - lua, luac executables
```

---

## Classification Summary

### Source Code (Active)
- `combo_enumeration.py` - Main engine
- `state_representation.py` - State classes
- `transposition_table.py` - Memoization
- `ocg_bindings.py` - CFFI bindings
- `test_fiendsmith_duel.py` - Duel utilities
- `__init__.py` - Package init
- `test_state.py` - Unit tests

### Source Code (Test/Development)
- `test_*.py` files (6 files)
- `verify_all_cards.py`
- `build/smoke_test_*.py` (2 files)

### Generated Output
- `enumeration_*.json` (4 files)
- `verification_run.json`

### Third-Party Dependencies
- `deps/lua-5.3.5/` (entire directory)
- `build/libygo.dylib`

### Cache/Temporary
- `.pytest_cache/` (entire directory)
- `__pycache__/` (excluded from inventory)

---

## Disk Usage Summary

| Directory | Size | % of Total |
|-----------|------|------------|
| cffi/enumeration JSON files | 12.6 MB | 70% |
| cffi/build/libygo.dylib | 2.7 MB | 15% |
| cffi/deps/lua-5.3.5/ | 2.3 MB | 13% |
| cffi/Python source | 0.3 MB | 2% |
| **Total cffi/** | **18 MB** | **100%** |

### Parent Directory Large Items

| Item | Size |
|------|------|
| testing.zip | 512 MB |
| full_folder backups | 372 MB |
| cards.cdb | 7.1 MB |
| Handoff archives | ~2 MB |
| **Potential savings from cleanup** | **~380 MB** |

---

*Report generated by Claude Code*
*Path: docs/PROJECT_INVENTORY.md*
