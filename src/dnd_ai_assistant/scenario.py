from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SCENE_PATH = Path(__file__).parent / "scenes" / "old_chapel.json"


@dataclass(frozen=True)
class SceneDefinition:
    raw: dict

    @property
    def campaign(self) -> dict:
        return self.raw["campaign"]

    @property
    def hero(self) -> dict:
        return self.raw["hero"]

    @property
    def location(self) -> dict:
        return self.raw["location"]

    @property
    def npc(self) -> dict:
        return self.raw["npc"]

    @property
    def clue(self) -> dict:
        return self.raw["clue"]

    @property
    def quest(self) -> dict:
        return self.raw["quest"]

    @property
    def text(self) -> dict:
        return self.raw["text"]

    @property
    def checks(self) -> dict:
        return self.raw["checks"]


def load_scene(path: str | Path | None = None) -> SceneDefinition:
    scene_path = Path(path) if path is not None else DEFAULT_SCENE_PATH
    with scene_path.open("r", encoding="utf-8") as f:
        return SceneDefinition(json.load(f))

