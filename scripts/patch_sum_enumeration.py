#!/usr/bin/env python3
"""
Full Sum Enumeration Implementation for MSG_SELECT_SUM

This patch adds comprehensive combinatorial search for valid sum combinations,
enabling exploration of all Xyz/Synchro material selection paths.

Apply with:
    python scripts/patch_sum_enumeration.py --apply

Revert with:
    python scripts/patch_sum_enumeration.py --revert
"""

import argparse
import shutil
from pathlib import Path
from datetime import datetime


# =============================================================================
# NEW CODE TO INSERT
# =============================================================================

SUM_ENUMERATION_HELPER = '''
def find_valid_sum_combinations(
    must_select: List[Dict],
    can_select: List[Dict],
    target_sum: int,
    min_select: int = 1,
    max_select: int = 5,
) -> List[List[int]]:
    """Find all valid combinations of cards that sum to target value.
    
    Used for Xyz summon material selection, Synchro tuning, ritual tributes, etc.
    
    Args:
        must_select: Cards that MUST be included (from must_select in message)
        can_select: Cards that CAN be selected (from can_select in message)
        target_sum: Target sum value (e.g., 6 for Rank 6 Xyz, 12 for 2x Level 6)
        min_select: Minimum total cards to select
        max_select: Maximum total cards to select
        
    Returns:
        List of valid index lists. Each inner list contains indices into can_select
        that form a valid sum when combined with must_select cards.
        
    Example:
        For Xyz summon of Rank 6 with two Level 6 monsters available:
        - must_select = []
        - can_select = [{"value": 6, ...}, {"value": 6, ...}]
        - target_sum = 12 (6 + 6)
        - Returns: [[0, 1]] (select both cards)
    """
    from itertools import combinations
    
    # Calculate sum from must_select cards (these are always included)
    must_sum = sum(card.get("value", 0) for card in must_select)
    must_count = len(must_select)
    
    # Remaining sum needed from can_select cards
    remaining_sum = target_sum - must_sum
    
    # Adjust selection bounds for can_select
    remaining_min = max(0, min_select - must_count)
    remaining_max = max(0, max_select - must_count)
    
    valid_combos = []
    
    # Edge case: if must_select already meets target
    if remaining_sum == 0 and remaining_min == 0:
        valid_combos.append([])  # Empty selection from can_select is valid
    
    # Try all combination sizes from remaining_min to remaining_max
    for size in range(remaining_min, min(remaining_max + 1, len(can_select) + 1)):
        if size == 0:
            continue  # Already handled above
            
        for combo_indices in combinations(range(len(can_select)), size):
            combo_sum = sum(can_select[i].get("value", 0) for i in combo_indices)
            
            # Check if this combination achieves the target sum
            # Note: Some mechanics allow "at least" target sum, but Xyz is exact
            if combo_sum == remaining_sum:
                valid_combos.append(list(combo_indices))
    
    return valid_combos


def find_sum_combinations_flexible(
    must_select: List[Dict],
    can_select: List[Dict], 
    target_sum: int,
    min_select: int = 1,
    max_select: int = 5,
    exact: bool = True,
) -> List[List[int]]:
    """Find combinations with flexible matching (exact or at-least).
    
    Some Yu-Gi-Oh mechanics require exact sum (Xyz), others require at-least
    (some ritual tributes). This function supports both modes.
    
    Args:
        exact: If True, sum must equal target. If False, sum must be >= target.
    """
    from itertools import combinations
    
    must_sum = sum(card.get("value", 0) for card in must_select)
    must_count = len(must_select)
    remaining_sum = target_sum - must_sum
    remaining_min = max(0, min_select - must_count)
    remaining_max = max(0, max_select - must_count)
    
    valid_combos = []
    
    # Handle edge case
    if exact and remaining_sum == 0 and remaining_min == 0:
        valid_combos.append([])
    elif not exact and remaining_sum <= 0 and remaining_min == 0:
        valid_combos.append([])
    
    for size in range(max(1, remaining_min), min(remaining_max + 1, len(can_select) + 1)):
        for combo_indices in combinations(range(len(can_select)), size):
            combo_sum = sum(can_select[i].get("value", 0) for i in combo_indices)
            
            if exact:
                if combo_sum == remaining_sum:
                    valid_combos.append(list(combo_indices))
            else:
                if combo_sum >= remaining_sum:
                    valid_combos.append(list(combo_indices))
    
    return valid_combos

'''

UPDATED_HANDLE_SELECT_SUM = '''
    def _handle_select_sum(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_SUM - select cards whose levels sum to target.

        Used for Xyz summon material selection, Synchro tuning, and similar mechanics.

        Response format (per ygopro-core playerop.cpp parse_response_cards):
        - int32_t type: -1 to cancel (if allowed), 0 for 32-bit indices
        - uint32_t count: number of selected cards (if type != -1)
        - uint32_t indices[count]: 0-indexed positions in the selectable cards

        This handler enumerates ALL valid sum combinations to explore all possible
        Xyz/Synchro lines, not just the first valid selection.
        """
        depth = len(action_history)
        
        # Extract parsed data
        must_select = msg_data.get("must_select", [])
        can_select = msg_data.get("can_select", [])
        target_sum = msg_data.get("target_sum", 0)
        must_count = msg_data.get("must_count", 0)
        can_count = msg_data.get("can_count", 0)
        
        self.log(f"SELECT_SUM: target={target_sum}, must={must_count}, can={can_count}", depth)
        
        # Debug: show available cards
        if self.verbose:
            for i, card in enumerate(must_select):
                name = get_card_name(card.get("code", 0))
                self.log(f"  must[{i}]: {name} (value={card.get('value', 0)})", depth)
            for i, card in enumerate(can_select):
                name = get_card_name(card.get("code", 0))
                self.log(f"  can[{i}]: {name} (value={card.get('value', 0)})", depth)

        # Branch 1: Cancel the selection (valid for optional effects)
        # Many Fiendsmith effects are optional, so canceling is a valid path
        cancel_response = struct.pack("<i", -1)
        cancel_action = Action(
            action_type="SELECT_SUM_CANCEL",
            message_type=MSG_SELECT_SUM,
            response_value=-1,
            response_bytes=cancel_response,
            description="Cancel sum selection",
        )
        self.log(f"Branch: Cancel sum selection", depth)
        self._recurse(action_history + [cancel_action])

        # Branch 2+: Find and explore all valid sum combinations
        # For Xyz: need cards whose levels sum to target (e.g., 2x Level 6 = 12)
        valid_combos = find_valid_sum_combinations(
            must_select=must_select,
            can_select=can_select,
            target_sum=target_sum,
            min_select=1,  # At least 1 card
            max_select=len(can_select),  # At most all available
        )
        
        self.log(f"  Found {len(valid_combos)} valid sum combinations", depth)
        
        # Deduplicate combinations by card codes to avoid redundant branches
        # (selecting Token A + Requiem vs Token B + Requiem with same codes)
        seen_code_combos = set()
        
        for combo_indices in valid_combos:
            # Get card codes for this combination
            combo_codes = tuple(sorted(can_select[i].get("code", 0) for i in combo_indices))
            
            if combo_codes in seen_code_combos:
                continue  # Skip duplicate code combination
            seen_code_combos.add(combo_codes)
            
            # Build response: type(0) + count + indices
            # Note: indices are relative to can_select list, but response expects
            # indices into the FULL selectable list (must + can concatenated)
            # Since must cards are auto-included, we just send can_select indices
            full_indices = list(combo_indices)  # Indices into can_select
            
            response = struct.pack("<iI", 0, len(full_indices))
            for idx in full_indices:
                response += struct.pack("<I", idx)
            
            # Build description
            card_names = [get_card_name(can_select[i].get("code", 0)) for i in combo_indices]
            total_sum = sum(can_select[i].get("value", 0) for i in combo_indices)
            desc = f"Sum select: {', '.join(card_names)} (sum={total_sum})"
            
            action = Action(
                action_type="SELECT_SUM",
                message_type=MSG_SELECT_SUM,
                response_value=full_indices,
                response_bytes=response,
                description=desc,
            )
            
            self.log(f"Branch: {desc}", depth)
            self._recurse(action_history + [action])
        
        # If no valid combinations found and cancel didn't work, try index 0 as fallback
        if not valid_combos and can_select:
            self.log(f"  No valid combos, trying fallback (index 0)", depth)
            fallback_response = struct.pack("<iII", 0, 1, 0)
            fallback_action = Action(
                action_type="SELECT_SUM_FALLBACK",
                message_type=MSG_SELECT_SUM,
                response_value=[0],
                response_bytes=fallback_response,
                description="Sum select fallback: card 0",
            )
            self._recurse(action_history + [fallback_action])

'''


# =============================================================================
# PATCH APPLICATION
# =============================================================================

def find_combo_enumeration_path():
    """Find the combo_enumeration.py file."""
    possible_paths = [
        Path("src/ygo_combo/combo_enumeration.py"),
        Path("combo_enumeration.py"),
        Path(__file__).parent.parent / "src" / "ygo_combo" / "combo_enumeration.py",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError("Could not find combo_enumeration.py")


def create_backup(path: Path) -> Path:
    """Create a timestamped backup of the file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(f".py.backup_{timestamp}")
    shutil.copy(path, backup_path)
    print(f"Created backup: {backup_path}")
    return backup_path


def apply_patch(path: Path, preview: bool = False):
    """Apply the sum enumeration patch."""
    
    content = path.read_text()
    
    # Check if already patched
    if "find_valid_sum_combinations" in content:
        print("WARNING: Patch appears to already be applied (find_valid_sum_combinations exists)")
        if not preview:
            return False
    
    # === PATCH 1: Add helper function after imports ===
    # Find the end of imports section (after CONFIGURATION section header)
    config_marker = "# =============================================================================\n# CONFIGURATION"
    if config_marker not in content:
        print("ERROR: Could not find CONFIGURATION section marker")
        return False
    
    # Insert helper function before CONFIGURATION
    insert_pos = content.find(config_marker)
    new_content = (
        content[:insert_pos] +
        "\n# =============================================================================\n"
        "# SUM ENUMERATION HELPERS\n"
        "# =============================================================================\n" +
        SUM_ENUMERATION_HELPER +
        "\n" +
        content[insert_pos:]
    )
    
    # === PATCH 2: Replace _handle_select_sum method ===
    # Find the existing method
    old_method_start = "    def _handle_select_sum(self, duel, action_history, msg_data):"
    old_method_marker = old_method_start
    
    if old_method_marker not in new_content:
        print("ERROR: Could not find _handle_select_sum method")
        return False
    
    # Find method boundaries
    method_start = new_content.find(old_method_marker)
    
    # Find the next method (starts with "    def _")
    next_method_pos = new_content.find("\n    def _", method_start + len(old_method_marker))
    if next_method_pos == -1:
        # Maybe it's the last method before a class ends or file ends
        next_method_pos = new_content.find("\n    def ", method_start + len(old_method_marker))
    if next_method_pos == -1:
        print("ERROR: Could not find end of _handle_select_sum method")
        return False
    
    # Replace the method
    new_content = (
        new_content[:method_start] +
        UPDATED_HANDLE_SELECT_SUM +
        new_content[next_method_pos:]
    )
    
    if preview:
        print("\n" + "=" * 60)
        print("PREVIEW: New _handle_select_sum method")
        print("=" * 60)
        print(UPDATED_HANDLE_SELECT_SUM[:2000] + "\n...")
        print("\n" + "=" * 60)
        print("PREVIEW: Helper functions to be added")
        print("=" * 60)
        print(SUM_ENUMERATION_HELPER[:1500] + "\n...")
        return True
    
    # Write the patched file
    path.write_text(new_content)
    print(f"Patched: {path}")
    return True


def revert_patch(path: Path):
    """Revert to most recent backup."""
    backups = sorted(path.parent.glob(f"{path.stem}.py.backup_*"), reverse=True)
    
    if not backups:
        print("ERROR: No backup files found")
        return False
    
    latest_backup = backups[0]
    print(f"Reverting to: {latest_backup}")
    
    shutil.copy(latest_backup, path)
    print(f"Reverted: {path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Apply sum enumeration patch")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply", action="store_true", help="Apply the patch")
    group.add_argument("--revert", action="store_true", help="Revert to backup")
    group.add_argument("--preview", action="store_true", help="Preview changes without applying")
    
    args = parser.parse_args()
    
    try:
        path = find_combo_enumeration_path()
        print(f"Found: {path}")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1
    
    if args.preview:
        apply_patch(path, preview=True)
        return 0
    
    if args.apply:
        create_backup(path)
        if apply_patch(path):
            print("\n✅ Patch applied successfully!")
            print("\nTest with:")
            print("  python scripts/test_hands.py --hand engraver --verbose")
        else:
            print("\n❌ Patch failed")
            return 1
    
    elif args.revert:
        if revert_patch(path):
            print("\n✅ Reverted successfully!")
        else:
            return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
