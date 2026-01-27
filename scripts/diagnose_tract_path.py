#!/usr/bin/env python3
"""
Diagnose why enumeration doesn't explore Tract path.

This script:
1. Sets up a duel with Engraver in hand
2. Activates Engraver
3. Shows all selectable spell/traps
4. Verifies Tract is among them
"""

import os
import sys
from pathlib import Path
import io

# Setup paths
sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "cffi"))

# Set environment
if not os.environ.get("YGOPRO_SCRIPTS_PATH"):
    os.environ["YGOPRO_SCRIPTS_PATH"] = "/Users/zacharyhartley/ygopro-scripts"

import struct
import json

from engine_interface import EngineContext
from ocg_bindings import MSG_SELECT_CARD, MSG_IDLE, MSG_SELECT_CHAIN
from combo_enumeration import (
    create_duel, parse_idle, parse_select_card, parse_select_chain,
    read_u8, read_u32
)

# Import ffi for message handling
from cffi import FFI
ffi = FFI()


def load_library():
    """Load locked library."""
    lib_path = Path(__file__).parents[1] / "config" / "locked_library.json"
    with open(lib_path) as f:
        return json.load(f)


def build_deck():
    """Build main and extra deck from library."""
    lib = load_library()
    main_deck = []
    extra_deck = []

    for code_str, info in lib["cards"].items():
        code = int(code_str)
        count = info.get("count", 1)
        is_extra = info.get("is_extra_deck", False)

        for _ in range(count):
            if is_extra:
                extra_deck.append(code)
            else:
                main_deck.append(code)

    return main_deck, extra_deck


def get_messages(lib, duel):
    """Get and parse all pending messages."""
    messages = []

    length = ffi.new("uint32_t*")
    buf = lib.OCG_DuelGetMessage(duel, length)

    if length[0] == 0:
        return messages

    data = bytes(ffi.buffer(buf, length[0]))
    stream = io.BytesIO(data)

    while stream.tell() < len(data):
        if stream.tell() + 4 > len(data):
            break
        msg_len = read_u32(stream)
        if msg_len == 0:
            break

        msg_type = read_u8(stream)
        remaining = msg_len - 1
        msg_body = stream.read(remaining)

        if msg_type == MSG_IDLE:
            msg_data = parse_idle(msg_body)
            messages.append((MSG_IDLE, msg_data))
        elif msg_type == MSG_SELECT_CARD:
            msg_data = parse_select_card(msg_body)
            messages.append((MSG_SELECT_CARD, msg_data))
        elif msg_type == MSG_SELECT_CHAIN:
            msg_data = parse_select_chain(msg_body)
            messages.append((MSG_SELECT_CHAIN, msg_data))
        else:
            messages.append((msg_type, None))

    return messages


# Card IDs
ENGRAVER = 60764609
TRACT = 98567237
SANCT = 35552985
PARADISE = 99989863
LURRIE = 97651498
KYRIE = 26434972

NAME_MAP = {
    ENGRAVER: "Fiendsmith Engraver",
    TRACT: "Fiendsmith's Tract",
    SANCT: "Fiendsmith's Sanct",
    PARADISE: "Fiendsmith in Paradise",
    LURRIE: "Fabled Lurrie",
    KYRIE: "Fiendsmith Kyrie",
}


def main():
    print("=" * 70)
    print("TRACT PATH DIAGNOSTIC")
    print("=" * 70)

    main_deck, extra_deck = build_deck()
    print(f"\nDeck size: {len(main_deck)} main, {len(extra_deck)} extra")

    # Check Tract is in deck
    tract_count = main_deck.count(TRACT)
    sanct_count = main_deck.count(SANCT)
    paradise_count = main_deck.count(PARADISE)
    engraver_count = main_deck.count(ENGRAVER)

    print(f"\nRelevant cards in deck:")
    print(f"  Engraver (60764609): {engraver_count}")
    print(f"  Tract (98567237): {tract_count}")
    print(f"  Sanct (35552985): {sanct_count}")
    print(f"  Paradise (99989863): {paradise_count}")

    if tract_count == 0:
        print("\nERROR: Tract not in deck!")
        return 1

    print("\n" + "=" * 70)
    print("STEP 1: Create duel and find Engraver in hand")
    print("=" * 70)

    with EngineContext() as ctx:
        lib = ctx.lib

        # Create duel
        duel = create_duel(lib, main_deck, extra_deck)
        lib.OCG_StartDuel(duel)

        # Process to first idle
        idle_data = None
        for _ in range(100):
            status = lib.OCG_DuelProcess(duel)
            messages = get_messages(lib, duel)

            for msg_type, msg_data in messages:
                if msg_type == MSG_IDLE:
                    idle_data = msg_data
                    break
            if idle_data:
                break
            if status == 0:
                break

        if not idle_data:
            print("ERROR: No IDLE message found")
            lib.OCG_DestroyDuel(duel)
            return 1

        # Check activatable cards
        activatable = idle_data.get("activatable", [])
        print(f"\nActivatable cards: {len(activatable)}")

        engraver_idx = None
        for i, card in enumerate(activatable):
            code = card["code"]
            loc = card.get("loc", 0)
            loc_name = {2: "hand", 4: "field", 16: "GY"}.get(loc, f"loc{loc}")
            name = NAME_MAP.get(code, f"Card_{code}")
            print(f"  [{i}] {name} ({code}) @ {loc_name}")
            if code == ENGRAVER and loc == 2:  # Hand
                engraver_idx = i

        if engraver_idx is None:
            print("\nWARNING: Engraver not activatable from hand")
            print("(This depends on random draw - may need to retry)")
            lib.OCG_DestroyDuel(duel)
            return 1

        print(f"\nEngraver found at index {engraver_idx}")

        print("\n" + "=" * 70)
        print("STEP 2: Activate Engraver and see SELECT_CARD options")
        print("=" * 70)

        # Activate Engraver (IDLE_RESPONSE_ACTIVATE = 5)
        IDLE_RESPONSE_ACTIVATE = 5
        value = (engraver_idx << 16) | IDLE_RESPONSE_ACTIVATE
        response = struct.pack("<I", value)
        lib.OCG_DuelSetResponse(duel, response, len(response))

        # Process to see what cards can be searched
        select_card_data = None
        from ocg_bindings import MSG_SELECT_CHAIN
        from combo_enumeration import parse_select_chain

        for _ in range(200):
            status = lib.OCG_DuelProcess(duel)
            messages = get_messages(lib, duel)

            print(f"  Iteration: status={status}, messages={len(messages)}")
            for msg_type, msg_data in messages:
                print(f"    Message type: {msg_type}")
                if msg_type == MSG_SELECT_CARD:
                    select_card_data = msg_data
                    break
                elif msg_type == MSG_SELECT_CHAIN:
                    # Decline chain
                    decline_response = struct.pack("<I", 0xFFFFFFFF)
                    lib.OCG_DuelSetResponse(duel, decline_response, len(decline_response))
                    print("    -> Declined chain")
            if select_card_data:
                break
            if status == 0:
                print("  Duel ended")
                break

        if not select_card_data:
            print("ERROR: No SELECT_CARD message (Engraver should search)")
            lib.OCG_DestroyDuel(duel)
            return 1

        cards = select_card_data["cards"]
        print(f"\nSelectable cards for search: {len(cards)}")
        print(f"Min select: {select_card_data['min']}, Max: {select_card_data['max']}")

        tract_idx = None
        sanct_idx = None
        paradise_idx = None

        for i, card in enumerate(cards):
            code = card["code"]
            name = NAME_MAP.get(code, f"Card_{code}")
            print(f"  [{i}] {name} ({code})")

            if code == TRACT:
                tract_idx = i
            elif code == SANCT:
                sanct_idx = i
            elif code == PARADISE:
                paradise_idx = i

        print(f"\nIndices: Tract={tract_idx}, Sanct={sanct_idx}, Paradise={paradise_idx}")

        if tract_idx is None:
            print("\nERROR: Tract not among searchable cards!")
            lib.OCG_DestroyDuel(duel)
            return 1

        print("\n" + "=" * 70)
        print("FINDING: Tract IS available to search!")
        print("=" * 70)

        # Show card order by list index
        print("\nCards in list order (DFS enumeration order):")
        for i, card in enumerate(cards):
            code = card["code"]
            name = NAME_MAP.get(code, f"Card_{code}")
            print(f"  Position {i}: {name} ({code})")

        print("\n" + "=" * 70)
        print("ANALYSIS")
        print("=" * 70)

        print("""
The issue is NOT that Tract is missing. Tract IS searchable.

Key observation: The SELECT_CARD list order determines DFS exploration order.
If Sanct appears BEFORE Tract in the list, DFS will fully explore all Sanct
branches before even starting to explore Tract branches.

With 50,000 paths budget, if the Sanct subtree is very large, the enumeration
may exhaust its budget before reaching the Tract branch at all.

Possible fixes:
1. RANDOMIZE: Shuffle the card order in _handle_select_card
2. PRIORITIZE: Sort cards by strategic importance (Tract > Sanct for Lurrie line)
3. BREADTH-FIRST: Use BFS instead of DFS to explore all branches at each depth
4. TARGETED: Add must_use_cards filter to only record combos using Tract
5. BUDGET: Increase max_paths significantly (may need 500K+)
""")

        lib.OCG_DestroyDuel(duel)

    return 0


if __name__ == "__main__":
    sys.exit(main())
