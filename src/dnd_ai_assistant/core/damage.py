from __future__ import annotations


UNTYPED_DAMAGE = "untyped"


def normalize_damage_type(damage_type: str | None) -> str:
    if damage_type is None:
        return UNTYPED_DAMAGE
    normalized = damage_type.strip().lower().replace(" ", "_").replace("-", "_")
    return normalized or UNTYPED_DAMAGE


def normalize_damage_types(damage_types: set[str] | list[str] | tuple[str, ...]) -> set[str]:
    return {normalize_damage_type(damage_type) for damage_type in damage_types}


def adjusted_damage_amount(
    amount: int,
    damage_type: str | None,
    immunities: set[str],
    resistances: set[str],
    vulnerabilities: set[str],
) -> int:
    if amount < 0:
        raise ValueError("Damage cannot be negative.")

    normalized = normalize_damage_type(damage_type)
    if normalized in immunities:
        return 0

    adjusted = amount
    if normalized in resistances:
        adjusted //= 2
    if normalized in vulnerabilities:
        adjusted *= 2
    return adjusted
