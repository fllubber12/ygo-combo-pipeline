#!/usr/bin/env python3
"""
Test creating a duel with actual Fiendsmith cards.

This test validates that we can:
1. Load card data from CDB via callback
2. Load Lua scripts via callback
3. Create a duel with Fiendsmith deck
4. Start the duel and process initial game state
5. Parse MSG_IDLE to extract legal actions
"""

import sys
from pathlib import Path

# Add src/ygo_combo to path for imports
sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "ygo_combo"))

# Import all shared functionality from engine
from engine.interface import (
    init_card_database, load_library, preload_utility_scripts,
    py_card_reader, py_card_reader_done, py_script_reader, py_log_handler,
    ffi, get_card_name, set_lib, location_name, process_messages,
    parse_msg_idle, clear_setcode_cache,
)
from engine.bindings import (
    LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_MZONE,
    POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
)
from engine.paths import CDB_PATH


# Fiendsmith card IDs (verified from cards.cdb)
ENGRAVER = 60764609      # Level 6 monster, hand effect to search
TRACT = 98567237         # Fiendsmith's Tract - Spell card
REQUIEM = 2463794        # Fiendsmith's Requiem - Link-1 monster
DESIRAE = 82135803       # Fiendsmith's Desirae - Level 9 Synchro
KYRIE = 26434972         # Fiendsmith Kyrie - Level 4 tuner
LACRIMA = 46640168       # Fiendsmith's Lacrima - Continuous Spell

# Standardized filler card
FILLER = 32864  # The 13th Grave - Normal monster


def print_legal_actions(idle_data):
    """Pretty print legal actions from MSG_IDLE."""
    print(f"\n=== Legal Actions for Player {idle_data['player']} ===")

    if idle_data["summonable"]:
        print("\nNormal Summonable:")
        for card in idle_data["summonable"]:
            code, con, loc, seq = card[:4]
            print(f"  - {get_card_name(code)} ({location_name(loc)} #{seq})")

    if idle_data["spsummon"]:
        print("\nSpecial Summonable:")
        for card in idle_data["spsummon"]:
            code, con, loc, seq = card[:4]
            print(f"  - {get_card_name(code)} ({location_name(loc)} #{seq})")

    if idle_data["activatable"]:
        print("\nActivatable Effects:")
        for card in idle_data["activatable"]:
            code, con, loc, seq, effect_desc, client_mode = card
            # Decode effect description - low 32 bits are string ID, high 32 bits are card code
            desc_id = effect_desc & 0xFFFFFFFF
            desc_card = (effect_desc >> 32) & 0xFFFFFFFF
            print(f"  - {get_card_name(code)} ({location_name(loc)} #{seq}) [desc: {desc_id}, mode: {client_mode}]")

    if idle_data["mset"]:
        print("\nMonster Settable:")
        for card in idle_data["mset"]:
            code, con, loc, seq = card[:4]
            print(f"  - {get_card_name(code)}")

    if idle_data["sset"]:
        print("\nSpell/Trap Settable:")
        for card in idle_data["sset"]:
            code, con, loc, seq = card[:4]
            print(f"  - {get_card_name(code)}")

    print(f"\nPhase options: to_bp={idle_data['to_bp']}, to_ep={idle_data['to_ep']}")


def create_fiendsmith_duel():
    """Create and run a duel with Fiendsmith deck."""
    print("\n" + "=" * 60)
    print("Testing Fiendsmith Duel")
    print("=" * 60 + "\n")

    # Initialize
    has_cdb = init_card_database()
    if not has_cdb:
        print("Cannot proceed without card database")
        return False

    lib = load_library()
    set_lib(lib)  # Set library reference for callbacks
    print("Library loaded")

    # Create duel options
    options = ffi.new("OCG_DuelOptions*")

    # Set seed
    options.seed[0] = 12345
    options.seed[1] = 67890
    options.seed[2] = 11111
    options.seed[3] = 22222

    # Set flags (MR5)
    options.flags = (5 << 16)

    # Set player info
    options.team1.startingLP = 8000
    options.team1.startingDrawCount = 2  # Draw 2 more (we put 3 in hand already)
    options.team1.drawCountPerTurn = 1

    options.team2.startingLP = 8000
    options.team2.startingDrawCount = 5
    options.team2.drawCountPerTurn = 1

    # Set callbacks
    options.cardReader = py_card_reader
    options.payload1 = ffi.NULL
    options.scriptReader = py_script_reader
    options.payload2 = ffi.NULL
    options.logHandler = py_log_handler
    options.payload3 = ffi.NULL
    options.cardReaderDone = py_card_reader_done
    options.payload4 = ffi.NULL
    options.enableUnsafeLibraries = 0

    # Create duel
    duel_ptr = ffi.new("OCG_Duel*")
    result = lib.OCG_CreateDuel(duel_ptr, options)

    if result != 0:
        error_names = [
            "SUCCESS", "NO_OUTPUT", "NOT_CREATED",
            "NULL_DATA_READER", "NULL_SCRIPT_READER",
            "INCOMPATIBLE_LUA_API", "NULL_RNG_SEED"
        ]
        error_name = error_names[result] if result < len(error_names) else "UNKNOWN"
        print(f"Failed to create duel: {error_name} ({result})")
        return False

    duel = duel_ptr[0]
    print("Duel created successfully")

    # Preload utility scripts
    if not preload_utility_scripts(lib, duel):
        print("Warning: Failed to load utility scripts")

    # Add cards to Player 0's deck
    print("\nAdding Fiendsmith deck to Player 0...")

    # Put Fiendsmith cards directly in hand for testing (deck gets shuffled)
    hand_cards = [
        ENGRAVER, ENGRAVER,  # 2x Fiendsmith Engraver in hand
        TRACT,               # 1x Fiendsmith's Tract in hand
    ]

    for i, code in enumerate(hand_cards):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_HAND
        card_info.seq = i
        card_info.pos = POS_FACEUP_ATTACK  # Face-up in hand
        lib.OCG_DuelNewCard(duel, card_info)

    print(f"  Added {len(hand_cards)} cards to hand")

    # Build deck with some Fiendsmith Spells/Traps (for Engraver to search)
    main_deck = [
        TRACT, TRACT,     # 2x more Fiendsmith's Tract in deck
        KYRIE, KYRIE,     # 2x Fiendsmith Kyrie in deck
        LACRIMA,          # 1x Fiendsmith's Lacrima (Continuous Spell)
    ]
    # Fill rest with normal monsters
    while len(main_deck) < 40:
        main_deck.append(FILLER)

    for i, code in enumerate(main_deck):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        lib.OCG_DuelNewCard(duel, card_info)

    print(f"  Added {len(main_deck)} cards to deck")

    # Extra deck (Link and Synchro monsters)
    extra_deck = [
        REQUIEM,    # Fiendsmith's Requiem (Link-1)
        DESIRAE,    # Fiendsmith's Desirae (Level 9 Synchro)
    ]

    for i, code in enumerate(extra_deck):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_EXTRA
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        lib.OCG_DuelNewCard(duel, card_info)

    print(f"  Added {len(extra_deck)} cards to extra deck")

    # Player 1 also needs a deck (minimum 40)
    print("\nAdding filler deck to Player 1...")
    for i in range(40):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 1
        card_info.duelist = 0
        card_info.code = FILLER  # Normal monster
        card_info.con = 1
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        lib.OCG_DuelNewCard(duel, card_info)

    print("  Added 40 cards to main deck")

    # Start duel
    print("\n" + "-" * 40)
    lib.OCG_StartDuel(duel)
    print("Duel started!")

    # Process until we get MSG_IDLE or hit max iterations
    max_iterations = 100
    found_idle = False

    for i in range(max_iterations):
        status = lib.OCG_DuelProcess(duel)
        status_names = ["END", "AWAITING", "CONTINUE"]
        status_name = status_names[status] if status < len(status_names) else "UNKNOWN"

        messages = process_messages(lib, duel)

        for msg_type, msg_data in messages:
            if msg_type == "IDLE":
                print("\n" + "-" * 40)
                print("Received MSG_IDLE - extracting legal actions")
                print_legal_actions(msg_data)
                found_idle = True
                break
            elif msg_type == "DRAW":
                player = msg_data["player"]
                count = msg_data["count"]
                cards = msg_data["cards"]
                card_names = [get_card_name(c) for c in cards]
                print(f"Player {player} drew {count} card(s): {', '.join(card_names)}")
            elif msg_type == "NEW_TURN":
                print(f"Turn start: Player {msg_data['player']}")
            elif msg_type == "NEW_PHASE":
                phase = msg_data["phase"]
                phase_names = {0x01: "Draw", 0x02: "Standby", 0x04: "Main1",
                               0x08: "Battle", 0x10: "Main2", 0x20: "End"}
                print(f"Phase: {phase_names.get(phase, phase)}")

        if found_idle:
            break

        if status == 0:  # OCG_DUEL_STATUS_END
            print("Duel ended unexpectedly")
            break
        elif status == 1:  # OCG_DUEL_STATUS_AWAITING
            # Need to provide a response - for now just continue
            print(f"Awaiting response at iteration {i}")
            break

    # Cleanup
    lib.OCG_DestroyDuel(duel)
    print("\n" + "=" * 60)
    if found_idle:
        print("Fiendsmith duel test completed successfully!")
    else:
        print("Test completed but MSG_IDLE not found")
    print("=" * 60)

    return found_idle


if __name__ == "__main__":
    success = create_fiendsmith_duel()
    exit(0 if success else 1)
