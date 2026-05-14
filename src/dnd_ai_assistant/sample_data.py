from __future__ import annotations

from .core.character import Character
from .core.spells import Spell, Spellcasting


def sample_adventure_character() -> Character:
    return Character(
        name="Leth",
        player_name="Sample Player",
        class_name="Cleric",
        level=3,
        ancestry="Human",
        ability_scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12},
        armor_class=16,
        max_hp=24,
        current_hp=24,
        skill_proficiencies={"insight", "medicine", "religion"},
        saving_throw_proficiencies={"wis", "cha"},
        spellcasting=Spellcasting(
            ability="wis",
            slots_by_level={1: 4, 2: 2},
            known_spells=[
                Spell("Bless", 1, concentration=True),
                Spell("Cure Wounds", 1),
                Spell("Healing Word", 1, casting_time="1 bonus action"),
                Spell("Sacred Flame", 0),
            ],
        ),
    )
