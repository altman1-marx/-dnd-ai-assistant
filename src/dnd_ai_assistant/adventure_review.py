from __future__ import annotations

import json
from dataclasses import dataclass

from .adventure import AdventureDefinition, validate_adventure


@dataclass(frozen=True)
class ReviewFinding:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class AdventureReview:
    findings: list[ReviewFinding]
    strengths: list[str]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def warnings(self) -> list[str]:
        return [finding.message for finding in self.findings]


def review_adventure(adventure: AdventureDefinition) -> AdventureReview:
    validate_adventure(adventure)
    findings: list[ReviewFinding] = []
    strengths: list[str] = []

    if 3 <= len(adventure.locations) <= 6:
        strengths.append("Location count fits a short adventure.")
    else:
        findings.append(
            ReviewFinding(
                code="location_count",
                severity="warning",
                message="Use 3 to 6 locations for a focused short adventure.",
            )
        )

    if len(adventure.clues) >= 2:
        strengths.append("Adventure has multiple clues.")
    else:
        findings.append(
            ReviewFinding(
                code="clue_count",
                severity="warning",
                message="Add at least two clues so the party has backup paths to progress.",
            )
        )

    if any(encounter.get("monsters") for encounter in adventure.encounters):
        strengths.append("At least one encounter includes monsters.")
    else:
        findings.append(
            ReviewFinding(
                code="encounter_monsters",
                severity="info",
                message="Add monsters to at least one encounter before combat demos can use it.",
            )
        )

    if adventure.campaign.get("dm_secret"):
        strengths.append("Campaign includes a DM secret.")
    else:
        findings.append(
            ReviewFinding(
                code="campaign_secret",
                severity="warning",
                message="Add campaign.dm_secret so the AI DM has a hidden truth to preserve.",
            )
        )

    if any(location.get("dm_notes") for location in adventure.locations):
        strengths.append("Locations include DM notes.")
    else:
        findings.append(
            ReviewFinding(
                code="location_dm_notes",
                severity="info",
                message="Add dm_notes to locations for hidden details and adjudication context.",
            )
        )

    clue_location_ids = {clue["location_id"] for clue in adventure.clues}
    if len(clue_location_ids) > 1:
        strengths.append("Clues are distributed across multiple locations.")
    elif len(adventure.locations) > 1:
        findings.append(
            ReviewFinding(
                code="clue_distribution",
                severity="info",
                message="Distribute clues across more than one location to support exploration.",
            )
        )

    return AdventureReview(findings=findings, strengths=strengths)


def render_adventure_review(adventure: AdventureDefinition) -> str:
    review = review_adventure(adventure)
    lines = [f"Adventure review: {adventure.campaign['title']}"]
    lines.append(f"Status: {'OK' if review.ok else 'Needs attention'}")
    if review.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- [{finding.severity}] {finding.message}" for finding in review.findings)
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
        "findings": [
            {"code": finding.code, "severity": finding.severity, "message": finding.message}
            for finding in review.findings
        ],
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
