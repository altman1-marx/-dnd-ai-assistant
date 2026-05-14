from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlparse

from .adventure import AdventureDefinition, validate_adventure
from .adventure_importer import campaign_from_adventure
from .adventure_runtime import AdventureRuntime, handle_adventure_action
from .core.campaign import Campaign
from .core.serialization import campaign_to_dict


@dataclass
class APIState:
    campaigns: dict[str, Campaign] = field(default_factory=dict)


class APIError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def import_adventure(state: APIState, adventure_data: dict) -> dict:
    adventure = AdventureDefinition(adventure_data)
    validate_adventure(adventure)
    campaign = campaign_from_adventure(adventure)
    state.campaigns[campaign.id] = campaign
    return {
        "campaign_id": campaign.id,
        "campaign": campaign_to_dict(campaign),
    }


def campaign_state(state: APIState, campaign_id: str) -> dict:
    return campaign_to_dict(_campaign_or_404(state, campaign_id))


def run_campaign_action(state: APIState, campaign_id: str, action: str, seed: int = 1) -> dict:
    if not action.strip():
        raise APIError(400, "Action cannot be empty.")
    campaign = _campaign_or_404(state, campaign_id)
    runtime = AdventureRuntime(campaign, rng=random.Random(seed))
    keep_going = handle_adventure_action(runtime, action)
    return {
        "campaign_id": campaign.id,
        "keep_going": keep_going,
        "transcript": runtime.flush(),
        "campaign": campaign_to_dict(campaign),
    }


def create_handler(state: APIState) -> type[BaseHTTPRequestHandler]:
    class DNDAPIHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._handle("GET")

        def do_POST(self) -> None:
            self._handle("POST")

        def log_message(self, format: str, *args) -> None:
            return

        def _handle(self, method: str) -> None:
            try:
                response = route_request(state, method, self.path, self._read_json())
                self._write_json(200, response)
            except APIError as exc:
                self._write_json(exc.status, {"error": exc.message})
            except Exception as exc:
                self._write_json(500, {"error": str(exc)})

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise APIError(400, "Request body must be valid JSON.") from exc

        def _write_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return DNDAPIHandler


def route_request(state: APIState, method: str, path: str, body: dict) -> dict:
    parsed = urlparse(path)
    parts = [part for part in parsed.path.split("/") if part]
    if method == "GET" and parts == ["health"]:
        return {"ok": True}
    if method == "POST" and parts == ["campaigns", "import"]:
        adventure = body.get("adventure")
        if not isinstance(adventure, dict):
            raise APIError(400, "Missing adventure object.")
        return import_adventure(state, adventure)
    if method == "GET" and len(parts) == 2 and parts[0] == "campaigns":
        return campaign_state(state, parts[1])
    if method == "POST" and len(parts) == 3 and parts[0] == "campaigns" and parts[2] == "actions":
        action = str(body.get("action", ""))
        seed = int(body.get("seed", 1))
        return run_campaign_action(state, parts[1], action, seed=seed)
    raise APIError(404, "Route not found.")


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    state: APIState | None = None,
    server_factory: Callable[..., ThreadingHTTPServer] = ThreadingHTTPServer,
) -> None:
    api_state = state or APIState()
    server = server_factory((host, port), create_handler(api_state))
    server.serve_forever()


def _campaign_or_404(state: APIState, campaign_id: str) -> Campaign:
    campaign = state.campaigns.get(campaign_id)
    if campaign is None:
        raise APIError(404, "Campaign not found.")
    return campaign
