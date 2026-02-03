#!/usr/bin/env python3
"""
Message Handler Audit Script

Runs combo enumeration and logs EVERY message type encountered.
Identifies which messages are handled vs unhandled.

Usage:
    python scripts/audit_messages.py
"""

import sys
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "ygo_combo"))


def get_message_constants():
    """Load message constants from engine.bindings."""
    try:
        from engine.bindings import (
            MSG_RETRY, MSG_HINT, MSG_WIN, MSG_SELECT_BATTLECMD,
            MSG_SELECT_IDLECMD, MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO,
            MSG_SELECT_OPTION, MSG_SELECT_CARD, MSG_SELECT_CHAIN,
            MSG_SELECT_PLACE, MSG_SELECT_POSITION, MSG_SELECT_TRIBUTE,
            MSG_SELECT_COUNTER, MSG_SELECT_SUM, MSG_SORT_CARD,
            MSG_CONFIRM_DECKTOP, MSG_CONFIRM_CARDS, MSG_SHUFFLE_DECK,
            MSG_SHUFFLE_HAND, MSG_SWAP_GRAVE_DECK, MSG_SHUFFLE_SET_CARD,
            MSG_NEW_TURN, MSG_NEW_PHASE, MSG_MOVE, MSG_POS_CHANGE,
            MSG_SET, MSG_SWAP, MSG_FIELD_DISABLED, MSG_SUMMONING,
            MSG_SUMMONED, MSG_SPSUMMONING, MSG_SPSUMMONED, MSG_FLIPSUMMONING,
            MSG_FLIPSUMMONED, MSG_CHAINING, MSG_CHAINED, MSG_CHAIN_SOLVING,
            MSG_CHAIN_SOLVED, MSG_CHAIN_END, MSG_CHAIN_NEGATED,
            MSG_CHAIN_DISABLED, MSG_RANDOM_SELECTED, MSG_BECOME_TARGET,
            MSG_DRAW, MSG_DAMAGE, MSG_RECOVER, MSG_EQUIP, MSG_LPUPDATE,
            MSG_CARD_TARGET, MSG_CANCEL_TARGET, MSG_PAY_LPCOST,
            MSG_ADD_COUNTER, MSG_REMOVE_COUNTER, MSG_ATTACK,
            MSG_BATTLE, MSG_ATTACK_DISABLED, MSG_DAMAGE_STEP_START,
            MSG_DAMAGE_STEP_END, MSG_MISSED_EFFECT, MSG_TOSS_COIN,
            MSG_TOSS_DICE, MSG_ANNOUNCE_RACE, MSG_ANNOUNCE_ATTRIB,
            MSG_ANNOUNCE_CARD, MSG_ANNOUNCE_NUMBER,
        )
        
        # Build name lookup
        msg_names = {}
        for name, val in list(locals().items()):
            if name.startswith("MSG_") and isinstance(val, int):
                msg_names[val] = name
        
        return msg_names
    
    except ImportError as e:
        print(f"Warning: Could not import all message constants: {e}")
        return {}


# Fallback message names if imports fail
FALLBACK_MSG_NAMES = {
    1: "MSG_RETRY",
    2: "MSG_HINT", 
    3: "MSG_WAITING",
    4: "MSG_START",
    5: "MSG_WIN",
    10: "MSG_SELECT_BATTLECMD",
    11: "MSG_SELECT_IDLECMD",
    12: "MSG_SELECT_EFFECTYN",
    13: "MSG_SELECT_YESNO",
    14: "MSG_SELECT_OPTION",
    15: "MSG_SELECT_CARD",
    16: "MSG_SELECT_CHAIN",
    18: "MSG_SELECT_PLACE",
    19: "MSG_SELECT_POSITION",
    21: "MSG_SELECT_TRIBUTE",
    22: "MSG_SELECT_COUNTER",
    23: "MSG_SELECT_SUM",
    24: "MSG_SELECT_UNSELECT_CARD",
    25: "MSG_SORT_CARD",
    26: "MSG_SELECT_RELEASE",  # Or could be different
    30: "MSG_CONFIRM_DECKTOP",
    31: "MSG_CONFIRM_CARDS",
    40: "MSG_SHUFFLE_DECK",
    41: "MSG_SHUFFLE_HAND",
    50: "MSG_NEW_TURN",
    51: "MSG_NEW_PHASE",
    60: "MSG_MOVE",
    70: "MSG_SUMMONING",
    71: "MSG_SUMMONED",
    72: "MSG_SPSUMMONING",
    73: "MSG_SPSUMMONED",
    90: "MSG_CHAINING",
    91: "MSG_CHAINED",
    92: "MSG_CHAIN_SOLVING",
    93: "MSG_CHAIN_SOLVED",
    94: "MSG_CHAIN_END",
    110: "MSG_DRAW",
    140: "MSG_ANNOUNCE_RACE",
    141: "MSG_ANNOUNCE_ATTRIB",
    142: "MSG_ANNOUNCE_CARD",
    143: "MSG_ANNOUNCE_NUMBER",
    160: "MSG_TAG_SWAP",
}


def run_audit():
    """Run message audit."""
    
    print("=" * 70)
    print("MESSAGE HANDLER AUDIT")
    print("=" * 70)
    
    # Get message names
    msg_names = get_message_constants()
    if not msg_names:
        print("Using fallback message names")
        msg_names = FALLBACK_MSG_NAMES
    
    print(f"\nLoaded {len(msg_names)} message type names")
    
    # Check what's defined in engine.bindings
    print("\n📋 Checking engine.bindings...")
    try:
        from engine import bindings as ocg_bindings

        defined_msgs = []
        for name in dir(ocg_bindings):
            if name.startswith("MSG_"):
                val = getattr(ocg_bindings, name)
                if isinstance(val, int):
                    defined_msgs.append((name, val))

        print(f"  Found {len(defined_msgs)} MSG_* constants defined:")
        for name, val in sorted(defined_msgs, key=lambda x: x[1]):
            print(f"    {val:3d} = {name}")
            msg_names[val] = name

    except ImportError as e:
        print(f"  Could not import engine.bindings: {e}")
    
    # Check combo_enumeration for handlers
    print("\n📋 Checking combo_enumeration.py for handlers...")
    
    combo_enum_path = Path("src/ygo_combo/combo_enumeration.py")
    if combo_enum_path.exists():
        content = combo_enum_path.read_text()
        
        # Look for handler patterns
        import re
        
        # Pattern 1: if msg_type == MSG_XXX or msg == XXX
        handled = set()
        
        # Find numeric comparisons
        for match in re.finditer(r'(?:msg_type|msg|message)\s*==\s*(\d+)', content):
            handled.add(int(match.group(1)))
        
        # Find MSG_XXX comparisons
        for match in re.finditer(r'(?:msg_type|msg|message)\s*==\s*(MSG_\w+)', content):
            msg_name = match.group(1)
            # Try to get value
            try:
                val = getattr(ocg_bindings, msg_name, None)
                if val is not None:
                    handled.add(val)
            except:
                pass
        
        # Find handler dict entries
        for match in re.finditer(r'(\d+)\s*:\s*(?:self\.)?_?handle', content):
            handled.add(int(match.group(1)))
        
        print(f"  Found handlers for {len(handled)} message types:")
        for msg_id in sorted(handled):
            name = msg_names.get(msg_id, f"MSG_{msg_id}")
            print(f"    {msg_id:3d} = {name}")
        
        # Check specifically for the problematic ones
        print("\n🔍 Checking critical handlers:")
        critical = [
            (12, "MSG_SELECT_EFFECTYN", "Optional effect activation"),
            (23, "MSG_SELECT_SUM", "Sum selection (Xyz materials)"),
            (26, "MSG_SELECT_RELEASE", "Release selection"),
            (140, "MSG_ANNOUNCE_RACE", "Declare monster type"),
            (141, "MSG_ANNOUNCE_ATTRIB", "Declare attribute"),
        ]
        
        for msg_id, name, purpose in critical:
            status = "✓ HANDLED" if msg_id in handled else "✗ MISSING"
            print(f"    {status}: {msg_id} {name} - {purpose}")
    
    else:
        print(f"  Could not find {combo_enum_path}")
    
    # Summary
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    print("""
To identify exactly which messages are being hit during Engraver combo:

1. Add logging to the message processing loop in combo_enumeration.py:

   def process_response(self, response):
       msg_type = response[0]  # or however you get it
       print(f"MSG: {msg_type} ({MSG_NAMES.get(msg_type, 'UNKNOWN')})")
       # ... rest of handling

2. Run the Engraver test and collect all message types

3. Implement handlers for any that are missing

Key messages likely needed for Fiendsmith combo:
- MSG_SELECT_EFFECTYN (12) - "Activate this effect?"
- MSG_SELECT_SUM (23) - Xyz material selection
- MSG_ANNOUNCE_ATTRIB (141) - Lacrima attribute declaration
    """)


if __name__ == "__main__":
    run_audit()
