from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from .errors import IllegalActionError
from .ygopro_cdb import enrich_metadata

@dataclass
class CardInstance:
    cid: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    equipped: list["CardInstance"] = field(default_factory=list)
    properly_summoned: bool = False

    @staticmethod
    def from_raw(raw: Any) -> "CardInstance":
        if isinstance(raw, CardInstance):
            return raw
        if isinstance(raw, dict):
            cid = str(raw.get("cid", raw.get("name", ""))).strip()
            name = str(raw.get("name", raw.get("cid", ""))).strip()
            metadata = raw.get("metadata", {}) or {}
            metadata = dict(metadata)
            metadata = enrich_metadata(cid, name=name, existing=metadata)
            try:
                if int(metadata.get("link_rating", 0)) > 0 and not metadata.get("from_extra"):
                    metadata["from_extra"] = True
            except (TypeError, ValueError):
                pass
            try:
                summon_type = str(metadata.get("summon_type", "")).lower()
                if summon_type in {"fusion", "synchro", "xyz", "link"} and not metadata.get("from_extra"):
                    metadata["from_extra"] = True
            except (TypeError, ValueError):
                pass
            equipped_raw = raw.get("equipped", []) or []
            equipped = [CardInstance.from_raw(item) for item in equipped_raw]
            properly_summoned = bool(raw.get("properly_summoned", False))
            return CardInstance(
                cid=cid,
                name=name,
                metadata=metadata,
                equipped=equipped,
                properly_summoned=properly_summoned,
            )
        name = str(raw).strip()
        return CardInstance(cid=name, name=name, metadata={})


@dataclass
class FieldZones:
    mz: list[CardInstance | None]
    stz: list[CardInstance | None]
    fz: list[CardInstance | None]
    emz: list[CardInstance | None]


@dataclass
class GameState:
    deck: list[CardInstance]
    hand: list[CardInstance]
    gy: list[CardInstance]
    banished: list[CardInstance]
    extra: list[CardInstance]
    field: FieldZones
    turn_number: int
    phase: str
    normal_summon_set_used: bool
    opt_used: dict
    restrictions: list
    events: list[str]
    last_moved_to_gy: list[str]

    def clone(self) -> "GameState":
        return copy.deepcopy(self)

    def field_cards(self) -> list[tuple[str, int, CardInstance]]:
        cards = []
        for idx, card in enumerate(self.field.mz):
            if card:
                cards.append(("mz", idx, card))
        for idx, card in enumerate(self.field.emz):
            if card:
                cards.append(("emz", idx, card))
        return cards

    def open_mz_indices(self) -> list[int]:
        return [idx for idx, card in enumerate(self.field.mz) if card is None]

    def open_emz_indices(self) -> list[int]:
        return [idx for idx, card in enumerate(self.field.emz) if card is None]

    def can_equip_to(self, target: CardInstance | None) -> bool:
        return target is not None

    def equip_card(self, card: CardInstance, target: CardInstance) -> None:
        target.equipped.append(card)

    @staticmethod
    def from_snapshot(snapshot: dict) -> "GameState":
        zones = snapshot.get("zones", {})

        def parse_list(value: Any) -> list[CardInstance]:
            if value is None:
                return []
            return [CardInstance.from_raw(item) for item in value]

        hand = parse_list(zones.get("hand", []))
        deck = parse_list(zones.get("deck", []))
        gy = parse_list(zones.get("gy", []))
        banished = parse_list(zones.get("banished", []))
        extra = parse_list(zones.get("extra", []))

        mz_list = [None] * 5
        emz_list = [None] * 2
        stz_list = [None] * 5
        fz_list = [None]

        if "field_zones" in zones:
            field_zones = zones.get("field_zones", {})
            mz_values = field_zones.get("mz", [])
            emz_values = field_zones.get("emz", [])
            stz_values = field_zones.get("stz", [])
            fz_values = field_zones.get("fz", [])
        else:
            mz_values = zones.get("field", [])
            emz_values = zones.get("emz", [])
            stz_values = zones.get("stz", [])
            fz_values = zones.get("fz", [])

        for idx, raw in enumerate(mz_values[:5]):
            if raw is None:
                continue
            mz_list[idx] = CardInstance.from_raw(raw)
        for idx, raw in enumerate(emz_values[:2]):
            if raw is None:
                continue
            emz_list[idx] = CardInstance.from_raw(raw)
        for idx, raw in enumerate(stz_values[:5]):
            if raw is None:
                continue
            stz_list[idx] = CardInstance.from_raw(raw)
        if fz_values:
            if fz_values[0] is not None:
                fz_list[0] = CardInstance.from_raw(fz_values[0])

        return GameState(
            deck=deck,
            hand=hand,
            gy=gy,
            banished=banished,
            extra=extra,
            field=FieldZones(mz=mz_list, stz=stz_list, fz=fz_list, emz=emz_list),
            turn_number=int(snapshot.get("turn_number", 1)),
            phase=str(snapshot.get("phase", "Main Phase 1")),
            normal_summon_set_used=bool(snapshot.get("normal_summon_set_used", False)),
            opt_used=dict(snapshot.get("opt_used", {})),
            restrictions=list(snapshot.get("restrictions", [])),
            events=list(snapshot.get("events", [])),
            last_moved_to_gy=list(snapshot.get("last_moved_to_gy", [])),
        )


def is_extra_deck_monster(card: CardInstance) -> bool:
    if card.metadata.get("from_extra"):
        return True
    summon_type = str(card.metadata.get("summon_type", "")).lower()
    if summon_type in {"fusion", "synchro", "xyz", "link"}:
        return True
    try:
        return int(card.metadata.get("link_rating", 0)) > 0
    except (TypeError, ValueError):
        return False


def can_revive_from_gy(card: CardInstance) -> bool:
    return (not is_extra_deck_monster(card)) or bool(card.properly_summoned)


def validate_revive_from_gy(card: CardInstance) -> None:
    if not can_revive_from_gy(card):
        raise IllegalActionError("Target was not properly summoned.")
