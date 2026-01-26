#!/usr/bin/env python3
"""
Patch for combo_enumeration.py to support configurable starting hands.

This script modifies create_duel() to accept a starting_hand parameter
and implements enumerate_from_hand() properly.

Usage:
    # Apply patch automatically
    python scripts/patch_configurable_hand.py --apply
    
    # Preview changes only
    python scripts/patch_configurable_hand.py --preview
    
    # Revert to backup
    python scripts/patch_configurable_hand.py --revert
"""

import re
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime


TARGET_FILE = Path("src/cffi/combo_enumeration.py")
BACKUP_SUFFIX = ".pre_hand_patch.bak"


# =============================================================================
# PATCH DEFINITIONS
# =============================================================================

PATCHES = [
    {
        "name": "Add starting_hand parameter to create_duel",
        "description": "Modify create_duel() signature to accept starting_hand",
        "search": r"def create_duel\(main_deck: List\[int\], extra_deck: List\[int\]\)",
        "replace": "def create_duel(main_deck: List[int], extra_deck: List[int], starting_hand: List[int] = None)",
    },
    {
        "name": "Replace hardcoded hand setup",
        "description": "Use starting_hand parameter instead of hardcoded Engraver + Holactie",
        "search": r"# === HAND: 1 Engraver \+ 4 Holactie ===\s*\n\s*hand_cards = \[ENGRAVER, HOLACTIE, HOLACTIE, HOLACTIE, HOLACTIE\]",
        "replace": """# === HAND: Use provided hand or default ===
    if starting_hand is not None:
        hand_cards = list(starting_hand)
        # Pad with HOLACTIE if less than 5 cards
        while len(hand_cards) < 5:
            hand_cards.append(HOLACTIE)
        # Truncate if more than 5 cards
        hand_cards = hand_cards[:5]
    else:
        # Default: 1 Engraver + 4 Holactie (original behavior)
        hand_cards = [ENGRAVER, HOLACTIE, HOLACTIE, HOLACTIE, HOLACTIE]""",
    },
]

# New enumerate_from_hand implementation
ENUMERATE_FROM_HAND_IMPL = '''
    def enumerate_from_hand(self, hand: List[int]) -> List["TerminalState"]:
        """
        Enumerate combos from a specific starting hand.
        
        Args:
            hand: List of up to 5 card passcodes for starting hand.
                  Will be padded with HOLACTIE if less than 5 cards.
                  
        Returns:
            List of terminal states (completed combo boards).
            
        Example:
            # Test Engraver + Terrortop opener
            hand = [60764609, 81275020, 14558127, 14558127, 14558127]
            results = engine.enumerate_from_hand(hand)
        """
        if not hand:
            raise ValueError("Hand cannot be empty")
        
        if len(hand) > 5:
            print(f"Warning: Hand has {len(hand)} cards, truncating to 5")
            hand = hand[:5]
        
        # Store original terminals to return only new ones
        original_terminal_count = len(self.terminals)
        
        # Create duel with this specific hand
        duel = create_duel(
            main_deck=self.main_deck,
            extra_deck=self.extra_deck,
            starting_hand=hand,
        )
        
        # Reset transposition table for fresh exploration
        self.transposition_table.clear()
        self.paths_explored = 0
        
        try:
            # Get initial state and run enumeration
            initial_state = self._get_current_state(duel)
            self._enumerate_recursive(duel, depth=0, path=[], state=initial_state)
        except Exception as e:
            print(f"Enumeration error: {e}")
            raise
        finally:
            # Clean up duel
            try:
                end_duel(duel)
            except Exception:
                pass
        
        # Return terminals found in this run
        new_terminals = list(self.terminals)[original_terminal_count:]
        return new_terminals
'''


# =============================================================================
# PATCH APPLICATION
# =============================================================================

def read_file(path: Path) -> str:
    """Read file contents."""
    with open(path, 'r') as f:
        return f.read()


def write_file(path: Path, content: str):
    """Write file contents."""
    with open(path, 'w') as f:
        f.write(content)


def backup_file(path: Path) -> Path:
    """Create backup of file."""
    backup_path = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    shutil.copy(path, backup_path)
    return backup_path


def apply_regex_patch(content: str, patch: dict) -> tuple[str, bool]:
    """Apply a single regex patch, return (new_content, success)."""
    pattern = patch["search"]
    replacement = patch["replace"]
    
    # Check if pattern exists
    if not re.search(pattern, content):
        return content, False
    
    # Apply replacement
    new_content = re.sub(pattern, replacement, content, count=1)
    return new_content, True


def find_enumerate_from_hand_stub(content: str) -> tuple[int, int]:
    """Find the enumerate_from_hand stub to replace."""
    # Look for the stub implementation
    pattern = r'def enumerate_from_hand\(self, hand: List\[int\]\)[^}]+?raise NotImplementedError\([^)]+\)'
    
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.start(), match.end()
    
    # Alternative: look for TODO marker
    pattern2 = r'def enumerate_from_hand\(self, hand: List\[int\]\).*?# TODO: Implement.*?(?=\n    def |\nclass |\Z)'
    match2 = re.search(pattern2, content, re.DOTALL)
    if match2:
        return match2.start(), match2.end()
    
    return -1, -1


def apply_patches(content: str, preview: bool = False) -> tuple[str, list]:
    """Apply all patches to content."""
    results = []
    
    for patch in PATCHES:
        new_content, success = apply_regex_patch(content, patch)
        results.append({
            "name": patch["name"],
            "success": success,
            "description": patch["description"],
        })
        if success:
            content = new_content
            if preview:
                print(f"  ✓ {patch['name']}")
        else:
            if preview:
                print(f"  ✗ {patch['name']} - pattern not found")
    
    # Handle enumerate_from_hand separately (more complex)
    start, end = find_enumerate_from_hand_stub(content)
    if start >= 0:
        # Replace the stub with full implementation
        content = content[:start] + ENUMERATE_FROM_HAND_IMPL.strip() + content[end:]
        results.append({
            "name": "Implement enumerate_from_hand()",
            "success": True,
            "description": "Replace stub with working implementation",
        })
        if preview:
            print(f"  ✓ Implement enumerate_from_hand()")
    else:
        results.append({
            "name": "Implement enumerate_from_hand()",
            "success": False,
            "description": "Could not find stub to replace",
        })
        if preview:
            print(f"  ✗ Implement enumerate_from_hand() - stub not found")
    
    return content, results


def preview_patches():
    """Preview what patches would be applied."""
    print("=" * 60)
    print("PATCH PREVIEW")
    print("=" * 60)
    
    if not TARGET_FILE.exists():
        print(f"ERROR: Target file not found: {TARGET_FILE}")
        return False
    
    content = read_file(TARGET_FILE)
    print(f"\nTarget: {TARGET_FILE}")
    print(f"Size: {len(content)} bytes")
    print(f"\nPatches to apply:")
    
    _, results = apply_patches(content, preview=True)
    
    success_count = sum(1 for r in results if r["success"])
    print(f"\n{success_count}/{len(results)} patches would succeed")
    
    return success_count == len(results)


def apply_patches_to_file():
    """Apply patches to the target file."""
    print("=" * 60)
    print("APPLYING PATCHES")
    print("=" * 60)
    
    if not TARGET_FILE.exists():
        print(f"ERROR: Target file not found: {TARGET_FILE}")
        return False
    
    # Backup
    print(f"\nBacking up {TARGET_FILE}...")
    backup_path = backup_file(TARGET_FILE)
    print(f"  Backup: {backup_path}")
    
    # Read and patch
    content = read_file(TARGET_FILE)
    new_content, results = apply_patches(content, preview=False)
    
    # Check results
    success_count = sum(1 for r in results if r["success"])
    
    print(f"\nPatch results:")
    for r in results:
        status = "✓" if r["success"] else "✗"
        print(f"  {status} {r['name']}")
    
    if success_count == 0:
        print("\nNo patches applied. File unchanged.")
        return False
    
    # Write patched file
    write_file(TARGET_FILE, new_content)
    print(f"\n✓ Patched {TARGET_FILE}")
    print(f"  {success_count}/{len(results)} patches applied")
    
    return True


def revert_patches():
    """Revert to backup."""
    backup_path = TARGET_FILE.with_suffix(TARGET_FILE.suffix + BACKUP_SUFFIX)
    
    if not backup_path.exists():
        print(f"ERROR: No backup found at {backup_path}")
        return False
    
    print(f"Reverting {TARGET_FILE} from backup...")
    shutil.copy(backup_path, TARGET_FILE)
    print(f"✓ Reverted to {backup_path}")
    
    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Patch combo_enumeration.py for configurable starting hands"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preview", action="store_true", help="Preview patches without applying")
    group.add_argument("--apply", action="store_true", help="Apply patches to file")
    group.add_argument("--revert", action="store_true", help="Revert to backup")
    
    args = parser.parse_args()
    
    if args.preview:
        success = preview_patches()
    elif args.apply:
        success = apply_patches_to_file()
    elif args.revert:
        success = revert_patches()
    else:
        parser.print_help()
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
