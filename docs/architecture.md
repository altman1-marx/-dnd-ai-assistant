# Architecture

This project is being built as a DND-first AI tabletop assistant. The current implementation is intentionally small and local-first: the AI layer is not connected yet, but the state and rules layer are already shaped so an AI DM can call tools instead of inventing outcomes.

## Current Layers

### Core Rules

Location:

```text
src/dnd_ai_assistant/core/
```

Responsibilities:

- Dice parsing and rolling
- DND 5e d20 checks
- Rules configuration such as common DC thresholds
- DND 5e skill-to-ability mapping and skill modifiers
- Character HP and conditions
- Initiative order
- Combat turn resources and round advancement
- Minimal spellcasting resources and spell metadata
- Campaign data objects
- In-memory campaign storage
- Campaign serialization
- DM tool functions

The rule layer should stay deterministic and testable. AI should never be responsible for generating dice results directly.

### Scene Data

Location:

```text
src/dnd_ai_assistant/scenes/*.json
```

Scene JSON currently defines:

- Campaign metadata
- One player character
- One location
- One NPC
- One clue
- One quest
- Text responses
- Check configuration
- Action aliases

This format is deliberately simple. It is a stepping stone toward AI-generated scenario packs.

### Adventure Data

Location:

```text
src/dnd_ai_assistant/adventure.py
```

Adventure JSON is the broader format intended for AI adventure generation. It includes campaign metadata, a connected location graph, start and final locations, NPCs, clues, quests, encounters, endings, and opening text. The validator checks required fields, unique ids, location references, and reachability from the starting location.

### Adventure Map Rendering

Location:

```text
src/dnd_ai_assistant/adventure_map.py
```

The map renderer turns adventure location connections into text or Mermaid output. This keeps the first map generator structural and testable before adding visual map rendering.

### Scene Engine

Location:

```text
src/dnd_ai_assistant/scene_engine.py
```

Responsibilities:

- Build a `SceneSession` from scene JSON
- Describe the initial scene
- Match player actions against scene aliases
- Resolve fixed scene actions
- Reveal clues
- Run checks through `DMTools`
- Record session events

The scene engine should not know about command-line arguments, web UI, or network concerns.

### CLI

Location:

```text
src/dnd_ai_assistant/demo.py
```

Responsibilities:

- Expose local prototype commands
- Run quickstart demos
- Run scripted or interactive scenes
- Validate scene JSON
- Generate scene templates
- Print initiative demos
- Summarize saved campaign state

The CLI is a development surface, not the final product UI.

## Data Flow

```text
Scene JSON
  -> load_scene()
  -> build_scene_session()
  -> SceneSession + Campaign + Character + Location + NPC + Clue
  -> handle_player_action()
  -> DMTools
  -> Dice / DND checks / Campaign state
  -> transcript + session_log
  -> optional saved campaign JSON
```

## Future AI DM Integration

The AI DM should receive:

- Player-visible scene description
- Current character state
- Relevant public lore
- Recent session log
- Available tool schemas

The AI DM should not receive:

- Unrevealed clue secrets unless explicitly needed for DM reasoning
- Raw authority to mutate campaign state
- Permission to invent dice outcomes

The AI DM should call tools for:

- Rolling checks
- Revealing clues
- Recording events
- Applying damage and healing
- Starting or advancing encounters
- Searching lore
- Updating NPC attitudes

## Near-Term Technical Roadmap

1. Expand scene JSON beyond one fixed clue path.
2. Add generic action rules with preconditions and effects.
3. Add encounter data models.
4. Connect initiative tracker to encounters.
5. Add persistent SQLite storage.
6. Add a minimal local web UI.
7. Add OpenAI-backed AI DM only after tool boundaries are stable.
