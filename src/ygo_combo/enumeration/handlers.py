"""
Message handlers for combo enumeration.

This module contains the MessageHandlerMixin class that provides all
message handling methods for the EnumerationEngine. These methods
process different message types from the ygopro-core engine.

The mixin expects the following attributes/methods from the host class:
    Attributes:
        - lib: The CFFI library handle
        - dedupe_intermediate: bool - Whether to dedupe intermediate states
        - transposition_table: TranspositionTable instance
        - intermediate_states_pruned: int - Counter for pruned states
        - verbose: bool - Enable verbose logging
        - prioritize_cards: set - Card codes to prioritize
        - prioritize_order: list - Order of prioritized cards
        - failed_at_context: dict - Context hash -> set of failed card codes

    Methods:
        - log(msg, depth): Log a message at given depth
        - _recurse(action_history): Continue enumeration with action history
        - _record_terminal(action_history, reason): Record a terminal state
        - _compute_select_card_context(select_data): Compute context hash
        - _mark_card_failed_at_context(context_hash, card_code): Mark card failed
"""

import struct
from itertools import combinations
from typing import List, TYPE_CHECKING

# Import shared types
try:
    from ..types import Action
    from ..engine.interface import get_card_name
    from ..engine.state import IntermediateState
    from ..engine.board_capture import capture_board_state
    from ..engine.bindings import (
        MSG_IDLE, MSG_SELECT_CARD, MSG_SELECT_PLACE, MSG_SELECT_POSITION,
        MSG_SELECT_OPTION, MSG_SELECT_UNSELECT_CARD, MSG_SELECT_SUM,
        MSG_SELECT_TRIBUTE,
    )
    from ..search.transposition import TranspositionEntry
    from .responses import (
        build_activate_response, build_pass_response, build_select_card_response,
        build_select_tribute_response,
    )
    from .sum_utils import find_valid_sum_combinations
    from .parsers import find_valid_tribute_combinations
except ImportError:
    # Fallback for direct execution (sys.path includes src/ygo_combo)
    # Note: Must import from src.ygo_combo.types, not types (collision with Python stdlib)
    from src.ygo_combo.types import Action
    from engine.interface import get_card_name
    from engine.state import IntermediateState
    from engine.board_capture import capture_board_state
    from engine.bindings import (
        MSG_IDLE, MSG_SELECT_CARD, MSG_SELECT_PLACE, MSG_SELECT_POSITION,
        MSG_SELECT_OPTION, MSG_SELECT_UNSELECT_CARD, MSG_SELECT_SUM,
        MSG_SELECT_TRIBUTE,
    )
    from search.transposition import TranspositionEntry
    from enumeration.responses import (
        build_activate_response, build_pass_response, build_select_card_response,
        build_select_tribute_response,
    )
    from enumeration.sum_utils import find_valid_sum_combinations
    from enumeration.parsers import find_valid_tribute_combinations


class MessageHandlerMixin:
    """Mixin class providing message handling methods for EnumerationEngine.

    This mixin defines all _handle_* methods that process different message
    types from the ygopro-core engine. It expects certain attributes and
    methods to be provided by the host class.

    Message Types Handled:
        - MSG_IDLE: Main phase actions (activate, summon, pass)
        - MSG_SELECT_CARD: Card selection prompts
        - MSG_SELECT_PLACE: Zone selection
        - MSG_SELECT_POSITION: ATK/DEF position selection
        - MSG_SELECT_EFFECTYN/MSG_SELECT_YESNO: Yes/No prompts
        - MSG_SELECT_OPTION: Multiple choice options
        - MSG_SELECT_UNSELECT_CARD: Select/unselect card interface
        - MSG_SELECT_SUM: Sum-based selection (Xyz/Synchro materials)
        - MSG_SELECT_TRIBUTE: Tribute selection
    """

    def _handle_idle(self, duel, action_history: List[Action], idle_data: dict):
        """Handle MSG_IDLE - branch on all actions + PASS.

        With intermediate state pruning enabled, we check if this exact game state
        (board + available actions) has been explored before. If so, we skip it
        since all future paths from this state are identical.
        """
        depth = len(action_history)

        # Intermediate state pruning using transposition table
        if self.dedupe_intermediate:
            # Compute intermediate state hash
            state = IntermediateState.from_engine(self.lib, duel, idle_data, capture_board_state)
            state_hash = state.hash()

            # Check transposition table
            cached = self.transposition_table.lookup(state_hash)
            if cached is not None:
                self.intermediate_states_pruned += 1
                self.log(f"PRUNED: duplicate intermediate state at depth {depth}", depth)
                return  # Already explored from this state

            # Store in transposition table
            self.transposition_table.store(state_hash, TranspositionEntry(
                state_hash=state_hash,
                best_terminal_hash="",
                best_terminal_value=0.0,
                creation_depth=depth,
                visit_count=1,
            ))

        self.log(f"IDLE: {len(idle_data.get('activatable', []))} activatable, "
                 f"{len(idle_data.get('spsummon', []))} spsummon", depth)

        # Enumerate all activatable effects
        for i, card in enumerate(idle_data.get("activatable", [])):
            code = card["code"]
            name = get_card_name(code)
            loc = card.get("loc", 0)
            desc = card.get("desc", 0)
            effect_idx = desc & 0xF
            value, response = build_activate_response(i)

            loc_name = {2: "hand", 4: "field", 8: "S/T", 16: "GY", 64: "Extra"}.get(loc, f"loc{loc}")

            action = Action(
                action_type="ACTIVATE",
                message_type=MSG_IDLE,
                response_value=value,
                response_bytes=response,
                description=f"Activate {name} ({loc_name} eff{effect_idx})",
                card_code=code,
                card_name=name,
            )

            self.log(f"Branch: Activate {name} ({loc_name} eff{effect_idx}) (idx {i})", depth)
            self._recurse(action_history + [action])

        # Enumerate special summons
        for i, card in enumerate(idle_data.get("spsummon", [])):
            code = card["code"]
            name = get_card_name(code)
            value = (i << 16) | 1
            response = struct.pack("<I", value)

            action = Action(
                action_type="SPSUMMON",
                message_type=MSG_IDLE,
                response_value=value,
                response_bytes=response,
                description=f"Special Summon {name}",
                card_code=code,
                card_name=name,
            )

            self.log(f"Branch: SpSummon {name} (idx {i})", depth)
            self._recurse(action_history + [action])

        # Enumerate normal summons
        for i, card in enumerate(idle_data.get("summonable", [])):
            code = card["code"]
            name = get_card_name(code)
            value = (i << 16) | 0
            response = struct.pack("<I", value)

            action = Action(
                action_type="SUMMON",
                message_type=MSG_IDLE,
                response_value=value,
                response_bytes=response,
                description=f"Normal Summon {name}",
                card_code=code,
                card_name=name,
            )

            self.log(f"Branch: Summon {name} (idx {i})", depth)
            self._recurse(action_history + [action])

        # PASS option (terminal)
        if idle_data.get("to_ep"):
            value, response = build_pass_response()
            action = Action(
                action_type="PASS",
                message_type=MSG_IDLE,
                response_value=value,
                response_bytes=response,
                description="Pass (End Phase)",
            )

            self.log(f"Branch: PASS (terminal)", depth)
            self._record_terminal(action_history + [action], "PASS")

    def _handle_select_card(self, duel, action_history: List[Action], select_data: dict):
        """Handle MSG_SELECT_CARD - branch on unique card codes only.

        Optimization: Selecting Holactie #1 vs Holactie #2 produces identical outcomes,
        so we deduplicate by card code and only branch on the first instance of each.

        Card Prioritization: If prioritize_cards is set, those cards are explored first
        in the order specified.

        SELECT_SUM_CANCEL Backtracking: If a SELECT_CARD choice led to SELECT_SUM_CANCEL,
        we exclude that card from subsequent SELECT_CARD prompts in the same path.
        """
        depth = len(action_history)
        cards = select_data["cards"]
        min_sel = select_data["min"]
        max_sel = select_data["max"]

        self.log(f"SELECT_CARD: {len(cards)} cards, select {min_sel}-{max_sel}", depth)

        # Compute context hash for this SELECT_CARD prompt
        context_hash = self._compute_select_card_context(select_data)

        # Find cards that led to SELECT_SUM_CANCEL in this path
        failed_codes = set()
        for i in range(len(action_history) - 1):
            action = action_history[i]
            next_action = action_history[i + 1]
            if (action.action_type == "SELECT_CARD" and
                next_action.action_type == "SELECT_SUM_CANCEL" and
                action.card_code is not None):
                failed_codes.add(action.card_code)

        if failed_codes:
            failed_names = [get_card_name(c) for c in failed_codes]
            self.log(f"  Excluding failed SELECT_SUM cards: {failed_names}", depth)

        # Single selection case
        if min_sel == 1 and max_sel == 1:
            unique_cards = []
            seen_codes = set()
            for i, card in enumerate(cards):
                code = card["code"]
                if code in seen_codes:
                    continue
                if code in failed_codes:
                    continue
                seen_codes.add(code)
                unique_cards.append((i, code))

            # Sort to put prioritized cards first
            if self.prioritize_cards:
                def priority_key(item):
                    idx, code = item
                    if code in self.prioritize_cards:
                        try:
                            return (0, self.prioritize_order.index(code))
                        except ValueError:
                            return (0, 999)
                    return (1, idx)
                unique_cards.sort(key=priority_key)

            for i, code in unique_cards:
                name = get_card_name(code)
                indices, response = build_select_card_response([i])

                action = Action(
                    action_type="SELECT_CARD",
                    message_type=MSG_SELECT_CARD,
                    response_value=indices,
                    response_bytes=response,
                    description=f"Select {name}",
                    card_code=code,
                    card_name=name,
                    context_hash=context_hash,
                )

                self.log(f"Branch: Select {name} (idx {i}, {len(unique_cards)} unique)", depth)
                self._recurse(action_history + [action])
        else:
            # Multi-select: enumerate combinations of unique card codes
            code_to_indices = {}
            for i, card in enumerate(cards):
                code = card["code"]
                if code in failed_codes:
                    continue
                if code not in code_to_indices:
                    code_to_indices[code] = []
                code_to_indices[code].append(i)

            unique_codes = list(code_to_indices.keys())

            for r in range(min_sel, max_sel + 1):
                for code_combo in combinations(unique_codes, r):
                    combo = [code_to_indices[code][0] for code in code_combo]
                    indices, response = build_select_card_response(combo)
                    names = [get_card_name(code) for code in code_combo]

                    action = Action(
                        action_type="SELECT_CARD",
                        message_type=MSG_SELECT_CARD,
                        response_value=combo,
                        response_bytes=response,
                        description=f"Select {', '.join(names)}",
                    )

                    self.log(f"Branch: Select {names}", depth)
                    self._recurse(action_history + [action])

    def _handle_select_place(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_PLACE - select zone for card."""
        depth = len(action_history)

        player = msg_data.get("player", 0)
        flag = msg_data.get("flag", 0)

        self.log(f"SELECT_PLACE: flag=0x{flag:08x}", depth)

        # Find first available zone
        location = 0x08  # S/T zone first
        sequence = 0
        for i in range(5):
            if not (flag & (1 << (8 + i))):
                sequence = i
                break
        else:
            location = 0x04
            for i in range(5):
                if not (flag & (1 << i)):
                    sequence = i
                    break

        response = struct.pack("<BBB", player, location, sequence)
        action = Action(
            action_type="SELECT_PLACE",
            message_type=MSG_SELECT_PLACE,
            response_value=f"zone_{location:02x}_{sequence}",
            response_bytes=response,
            description=f"Select zone ({location:02x}, {sequence})",
        )
        self._recurse(action_history + [action])

    def _handle_select_position(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_POSITION - always select ATK.

        Analysis showed position choices don't affect final board states
        for this library, so we skip branching to reduce search space.
        """
        response = struct.pack("<I", 0x1)
        action = Action(
            action_type="SELECT_POSITION",
            message_type=MSG_SELECT_POSITION,
            response_value=0x1,
            response_bytes=response,
            description="Position: ATK (auto)",
        )
        self._recurse(action_history + [action])

    def _handle_yes_no(self, duel, action_history, msg_data, msg_type):
        """Handle yes/no prompts - branch on both options."""
        depth = len(action_history)

        for choice, choice_name in [(1, "Yes"), (0, "No")]:
            response = struct.pack("<I", choice)
            action = Action(
                action_type="YES_NO",
                message_type=msg_type,
                response_value=choice,
                response_bytes=response,
                description=f"Choose: {choice_name}",
            )
            self.log(f"Branch: {choice_name}", depth)
            self._recurse(action_history + [action])

    def _handle_select_option(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_OPTION - select from multiple options."""
        depth = len(action_history)
        count = msg_data.get("count", 2) if msg_data else 2
        options = msg_data.get("options", []) if msg_data else []

        self.log(f"SELECT_OPTION: {count} options available", depth)

        for opt in range(count):
            desc = options[opt]["desc"] if opt < len(options) else 0
            response = struct.pack("<I", opt)
            action = Action(
                action_type="SELECT_OPTION",
                message_type=MSG_SELECT_OPTION,
                response_value=opt,
                response_bytes=response,
                description=f"Option {opt} (desc={desc})",
            )
            self.log(f"Branch: Option {opt}", depth)
            self._recurse(action_history + [action])

    def _handle_select_unselect_card(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_UNSELECT_CARD - select/unselect cards.

        Optimization: Deduplicate by card code to avoid redundant branches
        when selecting identical cards.
        """
        depth = len(action_history)
        finishable = msg_data.get("finishable", 0)
        select_cards = msg_data.get("select_cards", [])
        unselect_cards = msg_data.get("unselect_cards", [])

        self.log(f"SELECT_UNSELECT: {len(select_cards)} select, {len(unselect_cards)} unselect, finishable={finishable}", depth)

        # If finishable and we have unselect options, we can finish
        if finishable and unselect_cards:
            response = struct.pack("<i", -1)
            action = Action(
                action_type="SELECT_UNSELECT_FINISH",
                message_type=MSG_SELECT_UNSELECT_CARD,
                response_value=-1,
                response_bytes=response,
                description="Finish selection",
            )
            self.log(f"Branch: Finish selection", depth)
            self._recurse(action_history + [action])

        # Enumerate selectable cards - deduplicate by card code
        seen_codes = set()
        for i, card in enumerate(select_cards):
            code = card["code"]
            if code in seen_codes:
                continue
            seen_codes.add(code)

            name = get_card_name(code)
            response = struct.pack("<i", i)
            action = Action(
                action_type="SELECT_UNSELECT_SELECT",
                message_type=MSG_SELECT_UNSELECT_CARD,
                response_value=i,
                response_bytes=response,
                description=f"Select {name}",
                card_code=code,
                card_name=name,
            )
            self.log(f"Branch: Select {name} ({len(seen_codes)} unique)", depth)
            self._recurse(action_history + [action])

    def _handle_select_sum(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_SUM - select cards whose levels sum to target.

        Used for Xyz summon material selection, Synchro tuning, and similar mechanics.
        This handler enumerates ALL valid sum combinations.
        """
        depth = len(action_history)

        must_select = msg_data.get("must_select", [])
        can_select = msg_data.get("can_select", [])
        target_sum = msg_data.get("target_sum", 0)

        select_mode = msg_data.get("select_mode", 0)
        min_cards = msg_data.get("min", 1)
        max_cards = msg_data.get("max", len(can_select) if can_select else 2)
        mode_str = "exact" if select_mode == 0 else "at_least"
        self.log(f"SELECT_SUM: target={target_sum} ({mode_str}), select {min_cards}-{max_cards} cards", depth)

        # Debug output
        if self.verbose and "_raw_hex" in msg_data:
            raw_hex = msg_data['_raw_hex']
            raw_len = msg_data.get('_raw_len', len(raw_hex)//2)
            self.log(f"  RAW ({raw_len} bytes): {raw_hex[:80]}{'...' if len(raw_hex) > 80 else ''}", depth)
            if raw_len >= 33:
                self.log(f"  Card0 bytes (offset 15): {raw_hex[30:66]}", depth)

        if "_parse_error" in msg_data:
            self.log(f"  PARSE ERROR: {msg_data['_parse_error']}", depth)

        if self.verbose:
            for i, card in enumerate(must_select):
                name = get_card_name(card.get("code", 0))
                self.log(f"  must[{i}]: {name} level={card.get('level', 0)} (sum_param=0x{card.get('sum_param', 0):08x})", depth)
            for i, card in enumerate(can_select):
                name = get_card_name(card.get("code", 0))
                self.log(f"  can[{i}]: {name} level={card.get('level', 0)} (sum_param=0x{card.get('sum_param', 0):08x})", depth)

        # Branch 1: Cancel the selection
        # Mark the preceding SELECT_CARD choice as failed at its context
        last_select_card = None
        for action in reversed(action_history):
            if action.action_type == "SELECT_CARD" and action.card_code is not None:
                last_select_card = action
                break

        if last_select_card and last_select_card.context_hash is not None:
            self._mark_card_failed_at_context(
                last_select_card.context_hash,
                last_select_card.card_code
            )
            self.log(f"  Marked {last_select_card.card_name} as failed at context {last_select_card.context_hash}", depth)

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
        actual_target = target_sum
        if can_select and target_sum > 0:
            first_card_value = can_select[0].get("value", 0)
            if target_sum <= len(can_select) and first_card_value > 0:
                expected_sum = first_card_value * target_sum
                actual_target = expected_sum
                self.log(f"  Adjusted target: {target_sum} -> {actual_target} (card_value={first_card_value})", depth)

        valid_combos = find_valid_sum_combinations(
            must_select=must_select,
            can_select=can_select,
            target_sum=actual_target,
            min_select=min_cards,
            max_select=max_cards,
            mode=select_mode,
        )

        self.log(f"  Found {len(valid_combos)} valid sum combinations", depth)

        # Deduplicate combinations by card codes
        seen_code_combos = set()

        for combo_indices in valid_combos:
            combo_codes = tuple(sorted(can_select[i].get("code", 0) for i in combo_indices))

            if combo_codes in seen_code_combos:
                continue
            seen_code_combos.add(combo_codes)

            full_indices = list(combo_indices)
            count = len(full_indices)
            response = struct.pack('<iI', 0, count)
            for idx in full_indices:
                response += struct.pack('<I', idx)

            if self.verbose:
                hex_resp = response.hex()
                self.log(f"  SELECT_SUM response ({len(response)} bytes): {hex_resp}", depth)
                self.log(f"  Indices: {full_indices} (can_select has {len(can_select)} cards)", depth)

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

        # Fallback if no valid combinations found
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

    def _handle_select_tribute(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_TRIBUTE - enumerate all valid tribute combinations."""
        depth = len(action_history)

        cards = msg_data.get('cards', [])
        min_req = msg_data.get('min', 1)
        max_req = msg_data.get('max', 2)
        cancelable = msg_data.get('cancelable', False)

        self.log(f"SELECT_TRIBUTE: {len(cards)} cards, need {min_req}-{max_req} tributes", depth)

        if self.verbose:
            for card in cards:
                name = get_card_name(card.get("code", 0))
                self.log(f"  [{card['index']}]: {name} (release_param={card.get('release_param', 1)})", depth)

        valid_combos = find_valid_tribute_combinations(cards, min_req, max_req)

        # Deduplicate by card codes
        seen_code_combos = set()

        for combo in valid_combos:
            combo_codes = tuple(sorted(cards[i].get("code", 0) for i in combo))

            if combo_codes in seen_code_combos:
                continue
            seen_code_combos.add(combo_codes)

            response = build_select_tribute_response(combo)
            card_names = [get_card_name(cards[i].get("code", 0)) for i in combo]
            desc = f"Tribute {len(combo)} card(s): {', '.join(card_names)}"

            action = Action(
                action_type="SELECT_TRIBUTE",
                message_type=MSG_SELECT_TRIBUTE,
                response_value=combo,
                response_bytes=response,
                description=desc,
            )

            self.log(f"Branch: {desc}", depth)
            self._recurse(action_history + [action])

        # Cancel option
        if cancelable:
            cancel_response = struct.pack('<B', 0)
            cancel_action = Action(
                action_type="SELECT_TRIBUTE_CANCEL",
                message_type=MSG_SELECT_TRIBUTE,
                response_value=0,
                response_bytes=cancel_response,
                description="Cancel tribute",
            )
            self.log(f"Branch: Cancel tribute", depth)
            self._recurse(action_history + [cancel_action])

        # Fallback
        if not valid_combos and not cancelable and cards:
            fallback_indices = list(range(min(min_req, len(cards))))
            fallback_response = build_select_tribute_response(fallback_indices)
            fallback_action = Action(
                action_type="SELECT_TRIBUTE_FALLBACK",
                message_type=MSG_SELECT_TRIBUTE,
                response_value=fallback_indices,
                response_bytes=fallback_response,
                description=f"Fallback: tribute first {len(fallback_indices)} cards",
            )
            self.log(f"Branch: Fallback tribute", depth)
            self._recurse(action_history + [fallback_action])

    def _handle_legacy_message_12(self, duel, action_history, msg_data):
        """Handle legacy message type 12.

        In some ygopro-core versions, message 12 is used for effect activation prompts.
        We treat it similar to yes/no but with simpler parsing.
        """
        depth = len(action_history)
        self.log(f"Legacy MSG 12 at depth {depth}", depth)

        for choice in [1, 0]:
            response = struct.pack("<I", choice)
            choice_name = "Yes" if choice else "No"
            action = Action(
                action_type="LEGACY_12",
                message_type=12,
                response_value=choice,
                response_bytes=response,
                description=f"Legacy choice: {choice_name}",
            )
            self.log(f"Branch: {choice_name}", depth)
            self._recurse(action_history + [action])


__all__ = ['MessageHandlerMixin']
