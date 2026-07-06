from __future__ import annotations

import json
from dataclasses import dataclass

from .coc_runtime import COCScenario


@dataclass(frozen=True)
class COCReviewFinding:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class COCScenarioReview:
    findings: list[COCReviewFinding]
    strengths: list[str]

    @property
    def ok(self) -> bool:
        return not any(finding.severity in {"warning", "error"} for finding in self.findings)

    @property
    def warnings(self) -> list[str]:
        return [finding.message for finding in self.findings]


def review_coc_scenario(scenario: COCScenario) -> COCScenarioReview:
    findings: list[COCReviewFinding] = []
    strengths: list[str] = []

    if 2 <= len(scenario.locations) <= 5:
        strengths.append("Location count fits a short COC investigation.")
    else:
        findings.append(
            COCReviewFinding(
                code="location_count",
                severity="warning",
                message="Use 2 to 5 locations for a focused COC one-shot investigation.",
            )
        )

    if len(scenario.clues) >= 3:
        strengths.append("Scenario has enough clues for fallback investigation paths.")
    else:
        findings.append(
            COCReviewFinding(
                code="clue_count",
                severity="warning",
                message="Add at least three clues so the investigation can survive a failed roll.",
            )
        )

    _review_reachability(scenario, findings, strengths)
    _review_clue_distribution(scenario, findings, strengths)
    _review_soft_failures(scenario, findings, strengths)
    _review_npcs(scenario, findings, strengths)
    _review_sanity_loss(scenario, findings, strengths)
    _review_evidence(scenario, findings, strengths)
    _review_exit_requirements(scenario, findings, strengths)
    _review_completion_requirements(scenario, findings, strengths)

    if scenario.ending_text.strip():
        strengths.append("Scenario includes an ending text.")
    else:
        findings.append(
            COCReviewFinding(
                code="ending_text",
                severity="warning",
                message="Add ending_text so the Keeper can close the investigation cleanly.",
            )
        )

    return COCScenarioReview(findings=findings, strengths=strengths)


def coc_review_to_dict(scenario: COCScenario) -> dict:
    review = review_coc_scenario(scenario)
    return {
        "title": scenario.title,
        "ok": review.ok,
        "findings": [
            {"code": finding.code, "severity": finding.severity, "message": finding.message}
            for finding in review.findings
        ],
        "warnings": list(review.warnings),
        "strengths": list(review.strengths),
        "counts": {
            "locations": len(scenario.locations),
            "npcs": len(scenario.npcs),
            "clues": len(scenario.clues),
            "evidence": len([clue for clue in scenario.clues if clue.evidence]),
            "soft_failure_clues": len([clue for clue in scenario.clues if clue.failure_text]),
            "total_sanity_loss": sum(max(0, clue.sanity_loss) for clue in scenario.clues),
            "completion_goals": _completion_goal_count(scenario),
        },
    }


def _completion_goal_count(scenario: COCScenario) -> int:
    return sum(len(values) for values in scenario.completion_requirements.values())

def render_coc_review(scenario: COCScenario) -> str:
    review = review_coc_scenario(scenario)
    lines = [f"COC scenario review: {scenario.title}"]
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


def render_coc_review_json(scenario: COCScenario) -> str:
    return json.dumps(coc_review_to_dict(scenario), ensure_ascii=False, indent=2)


def _review_reachability(
    scenario: COCScenario,
    findings: list[COCReviewFinding],
    strengths: list[str],
) -> None:
    if not scenario.locations:
        return
    start_id = scenario.current_location_id or next(iter(scenario.locations))
    reachable = _reachable_location_ids(scenario, start_id)
    if len(reachable) == len(scenario.locations):
        strengths.append("All locations are reachable from the starting location.")
    else:
        missing = sorted(set(scenario.locations) - reachable)
        findings.append(
            COCReviewFinding(
                code="unreachable_locations",
                severity="warning",
                message=f"Some locations are unreachable from the start: {', '.join(missing)}.",
            )
        )


def _review_clue_distribution(
    scenario: COCScenario,
    findings: list[COCReviewFinding],
    strengths: list[str],
) -> None:
    clue_locations = {clue.location_id for clue in scenario.clues if clue.location_id}
    if len(clue_locations) >= min(2, len(scenario.locations)):
        strengths.append("Clues are distributed across multiple locations.")
    elif len(scenario.locations) > 1:
        findings.append(
            COCReviewFinding(
                code="clue_distribution",
                severity="info",
                message="Distribute clues across more than one location to reward exploration.",
            )
        )


def _review_soft_failures(
    scenario: COCScenario,
    findings: list[COCReviewFinding],
    strengths: list[str],
) -> None:
    gated_clues = [clue for clue in scenario.clues if clue.skill]
    if not gated_clues:
        return
    soft_failure_clues = [clue for clue in gated_clues if clue.failure_text]
    if len(soft_failure_clues) == len(gated_clues):
        strengths.append("Skill-gated clues include soft-failure leads to reduce dead ends.")
        return
    missing = sorted(clue.id for clue in gated_clues if not clue.failure_text)
    findings.append(
        COCReviewFinding(
            code="clue_soft_failure",
            severity="info",
            message=(
                "Add failure_text to skill-gated clues so failed rolls still reveal partial leads: "
                + ", ".join(missing)
                + "."
            ),
        )
    )

def _review_npcs(
    scenario: COCScenario,
    findings: list[COCReviewFinding],
    strengths: list[str],
) -> None:
    if not scenario.npcs:
        findings.append(
            COCReviewFinding(
                code="npc_count",
                severity="info",
                message="Add at least one NPC witness or suspect for social investigation.",
            )
        )
        return
    if all(npc.dialogue for npc in scenario.npcs):
        strengths.append("NPCs include dialogue prompts.")
    else:
        findings.append(
            COCReviewFinding(
                code="npc_dialogue",
                severity="info",
                message="Give each NPC at least one dialogue line or testimony hook.",
            )
        )


def _review_sanity_loss(
    scenario: COCScenario,
    findings: list[COCReviewFinding],
    strengths: list[str],
) -> None:
    total = sum(max(0, clue.sanity_loss) for clue in scenario.clues)
    if total <= 8:
        strengths.append("Total automatic SAN loss is modest for a starter scenario.")
    else:
        findings.append(
            COCReviewFinding(
                code="sanity_loss_budget",
                severity="warning",
                message="Total clue SAN loss is high for a starter scenario; consider lowering it or gating the worst revelations.",
            )
        )


def _review_evidence(
    scenario: COCScenario,
    findings: list[COCReviewFinding],
    strengths: list[str],
) -> None:
    evidence_count = len([clue for clue in scenario.clues if clue.evidence])
    if evidence_count >= max(1, len(scenario.clues) // 2):
        strengths.append("Many clues produce concrete evidence for the player inventory.")
    else:
        findings.append(
            COCReviewFinding(
                code="evidence_count",
                severity="info",
                message="Add evidence names to more clues so the investigation leaves visible artifacts.",
            )
        )


def _review_completion_requirements(
    scenario: COCScenario,
    findings: list[COCReviewFinding],
    strengths: list[str],
) -> None:
    requirements = scenario.completion_requirements
    if not requirements:
        findings.append(
            COCReviewFinding(
                code="completion_requirements",
                severity="info",
                message="Add completion_requirements so the intended ending is explicit and data driven.",
            )
        )
        return
    clue_ids = {clue.id for clue in scenario.clues}
    evidence_names = {clue.evidence for clue in scenario.clues if clue.evidence}
    location_ids = set(scenario.locations)
    npc_ids = {npc.id for npc in scenario.npcs}
    references = {
        "completion_requirement_clue": ("required_clue_ids", clue_ids, "unknown clue ids"),
        "completion_requirement_evidence": ("required_evidence", evidence_names, "evidence no clue can produce"),
        "completion_requirement_location": ("required_location_ids", location_ids, "unknown location ids"),
        "completion_requirement_npc": ("required_npc_ids", npc_ids, "unknown NPC ids"),
    }
    missing_any = False
    for code, (key, known_values, label) in references.items():
        missing = sorted(set(requirements.get(key, [])) - known_values)
        if missing:
            missing_any = True
            findings.append(
                COCReviewFinding(
                    code=code,
                    severity="warning",
                    message=f"completion_requirements.{key} references {label}: {', '.join(missing)}.",
                )
            )
    if not missing_any:
        strengths.append("Completion requirements define a clear investigation ending.")

def _review_exit_requirements(
    scenario: COCScenario,
    findings: list[COCReviewFinding],
    strengths: list[str],
) -> None:
    clue_ids = {clue.id for clue in scenario.clues}
    evidence_names = {clue.evidence for clue in scenario.clues if clue.evidence}
    gated_exits = 0
    for location in scenario.locations.values():
        for exit_name, requirement in location.exit_requirements.items():
            gated_exits += 1
            unknown_clues = sorted(set(requirement.get("required_clue_ids", [])) - clue_ids)
            if unknown_clues:
                findings.append(
                    COCReviewFinding(
                        code="exit_requirement_clue",
                        severity="warning",
                        message=(
                            f"Exit '{exit_name}' in '{location.id}' requires unknown clue ids: "
                            + ", ".join(unknown_clues)
                            + "."
                        ),
                    )
                )
            unknown_evidence = sorted(set(requirement.get("required_evidence", [])) - evidence_names)
            if unknown_evidence:
                findings.append(
                    COCReviewFinding(
                        code="exit_requirement_evidence",
                        severity="warning",
                        message=(
                            f"Exit '{exit_name}' in '{location.id}' requires evidence no clue can produce: "
                            + ", ".join(unknown_evidence)
                            + "."
                        ),
                    )
                )
            if not requirement.get("message"):
                findings.append(
                    COCReviewFinding(
                        code="exit_requirement_message",
                        severity="info",
                        message=f"Give gated exit '{exit_name}' in '{location.id}' a Keeper-facing blocked message.",
                    )
                )
    if gated_exits and not any(
        finding.code in {"exit_requirement_clue", "exit_requirement_evidence"} for finding in findings
    ):
        strengths.append("Exit requirements create investigation gates with valid clue and evidence references.")


def _reachable_location_ids(scenario: COCScenario, start_id: str) -> set[str]:
    if start_id not in scenario.locations:
        return set()
    visited: set[str] = set()
    queue = [start_id]
    while queue:
        location_id = queue.pop(0)
        if location_id in visited:
            continue
        visited.add(location_id)
        for destination_id in scenario.locations[location_id].exits.values():
            if destination_id in scenario.locations and destination_id not in visited:
                queue.append(destination_id)
    return visited
