from __future__ import annotations

import json
from dataclasses import dataclass

from .adventure import AdventureDefinition, validate_adventure


@dataclass(frozen=True)
class AdventureReview:
    warnings: list[str]
    strengths: list[str]

    @property
    def ok(self) -> bool:
        return not self.warnings


def review_adventure(adventure: AdventureDefinition) -> AdventureReview:
    validate_adventure(adventure)
    warnings: list[str] = []
    strengths: list[str] = []

    if 3 <= len(adventure.locations) <= 6:
        strengths.append("Location count fits a short adventure.")
    else:
        warnings.append("Use 3 to 6 locations for a focused short adventure.")

    if len(adventure.clues) >= 2:
        strengths.append("Adventure has multiple clues.")
    else:
        warnings.append("Add at least two clues so the party has backup paths to progress.")

    if any(encounter.get("monsters") for encounter in adventure.encounters):
        strengths.append("At least one encounter includes monsters.")
    else:
        warnings.append("Add monsters to at least one encounter before combat demos can use it.")

    if adventure.campaign.get("dm_secret"):
        strengths.append("Campaign includes a DM secret.")
    else:
        warnings.append("Add campaign.dm_secret so the AI DM has a hidden truth to preserve.")

    if any(location.get("dm_notes") for location in adventure.locations):
        strengths.append("Locations include DM notes.")
    else:
        warnings.append("Add dm_notes to locations for hidden details and adjudication context.")

    clue_location_ids = {clue["location_id"] for clue in adventure.clues}
    if len(clue_location_ids) > 1:
        strengths.append("Clues are distributed across multiple locations.")
    elif len(adventure.locations) > 1:
        warnings.append("Distribute clues across more than one location to support exploration.")

    return AdventureReview(warnings=warnings, strengths=strengths)


def render_adventure_review(adventure: AdventureDefinition) -> str:
    review = review_adventure(adventure)
    lines = [f"Adventure review: {adventure.campaign['title']}"]
    lines.append(f"Status: {'OK' if review.ok else 'Needs attention'}")
    if review.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in review.warnings)
    if review.strengths:
        lines.append("")
        lines.append("Strengths:")
        lines.extend(f"- {strength}" for strength in review.strengths)
    return "\n".join(lines)


def adventure_review_to_dict(adventure: AdventureDefinition) -> dict:
    review = review_adventure(adventure)
    return {
        "title": adventure.campaign["title"],
        "ok": review.ok,
        "warnings": list(review.warnings),
        "strengths": list(review.strengths),
        "counts": {
            "locations": len(adventure.locations),
            "npcs": len(adventure.npcs),
            "clues": len(adventure.clues),
            "quests": len(adventure.quests),
            "encounters": len(adventure.encounters),
            "endings": len(adventure.endings),
        },
    }


def render_adventure_review_json(adventure: AdventureDefinition) -> str:
    return json.dumps(adventure_review_to_dict(adventure), ensure_ascii=False, indent=2)
