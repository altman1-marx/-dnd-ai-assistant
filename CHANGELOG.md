# Changelog

## Unreleased

- Added DND core dice and d20 check utilities.
- Added simplified character state with HP, AC, proficiencies, damage, and healing.
- Added campaign, location, NPC, clue, quest, encounter, monster, and session event models.
- Added in-memory campaign store.
- Added DM tool layer for campaign updates, rolls, clue reveals, damage, healing, encounter resolution, and attacks.
- Added JSON campaign serialization and saved-state summaries.
- Added scene JSON loading, validation, and template generation.
- Added a bundled `old_chapel` scene.
- Added scene engine separated from CLI input/output.
- Added interactive and scripted CLI play mode.
- Added initiative tracker and initiative CLI demo.
- Added one-attack combat CLI demo with optional state export.
- Added architecture documentation.
- Added core DND 5e skill mapping and reusable skill-check tooling.
- Added combat turn resources for actions, bonus actions, reactions, and movement.
- Added duplicate entity safeguards for campaign inserts.
- Added stricter character validation and skill proficiency normalization.
- Added reusable saving throw tool support.
- Added store and campaign integrity tests.
- Added minimal spell and spellcasting resource models with serialization support.
- Added GitHub Actions unit test workflow.
- Added rules configuration for common DC thresholds and default movement speed.
- Added adventure JSON template, loader, validator, and CLI commands.
- Added text and Mermaid adventure map rendering.
- Added adventure-to-campaign import support.
- Added AI adventure prompt generation and model-output JSON cleanup.
- Added a one-step model-output compile command for adventure and campaign files.
- Added adventure content review warnings and CLI output.
- Added JSON output for adventure content reviews.
- Added review finding codes and severity levels.
- Added pluggable AI providers for mock and OpenAI-compatible text generation.
- Added `generate-adventure` CLI workflow for provider-backed adventure generation.
- Improved OpenAI-compatible provider handling for Windows env files and incomplete HTTP responses.
- Added retry-and-repair prompts for invalid AI adventure output.
- Added optional JSON object response format for OpenAI-compatible generation.
- Added campaign current location state and basic adventure runtime movement.
