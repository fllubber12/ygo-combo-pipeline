import unittest

from src.sim.rules import (
    ActivationContext,
    CardType,
    EffectLocation,
    EffectType,
    validate_activation,
)


class TestRulesEngine(unittest.TestCase):
    def test_trap_from_hand_fails(self):
        ctx = ActivationContext(
            card_type=CardType.TRAP,
            effect_location=EffectLocation.FIELD,
            effect_type=EffectType.QUICK,
            current_location="hand",
            is_set=False,
            turns_since_set=0,
        )
        ok, _reason = validate_activation(ctx)
        self.assertFalse(ok)

    def test_trap_same_turn_set_fails(self):
        ctx = ActivationContext(
            card_type=CardType.TRAP,
            effect_location=EffectLocation.FIELD,
            effect_type=EffectType.QUICK,
            current_location="stz",
            is_set=True,
            turns_since_set=0,
        )
        ok, _reason = validate_activation(ctx)
        self.assertFalse(ok)

    def test_gy_effect_when_on_field_fails(self):
        ctx = ActivationContext(
            card_type=CardType.SPELL,
            effect_location=EffectLocation.GY,
            effect_type=EffectType.IGNITION,
            current_location="stz",
        )
        ok, _reason = validate_activation(ctx)
        self.assertFalse(ok)

    def test_trigger_effect_without_trigger_fails(self):
        ctx = ActivationContext(
            card_type=CardType.MONSTER,
            effect_location=EffectLocation.FIELD,
            effect_type=EffectType.TRIGGER,
            current_location="mz",
            trigger_event_occurred=False,
        )
        ok, _reason = validate_activation(ctx)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
