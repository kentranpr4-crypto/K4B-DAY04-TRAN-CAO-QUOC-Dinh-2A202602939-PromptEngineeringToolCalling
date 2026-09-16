from __future__ import annotations

import argparse
import json
import re
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from chat import ARTIFACTS_DIR, ROOT, now_iso, run_model_tool_loop, safe_slug, trim_history, write_transcript
from providers import make_provider
from tools import _hospital, load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


UI_FILE = ROOT / "index.html"
MAX_MESSAGE_CHARS = 2000
JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def extract_reply(text: str) -> str:
    """The system prompt asks for {intent, action, reply, evidence_ids}; show only reply."""
    match = JSON_BLOCK.search(text or "")
    candidate = match.group(1) if match else (text or "").strip()
    try:
        parsed = json.loads(candidate)
    except (TypeError, ValueError):
        return text or ""
    if isinstance(parsed, dict) and isinstance(parsed.get("reply"), str):
        return parsed["reply"]
    return text or ""


def classify(args: dict[str, Any], output: dict[str, Any]) -> str:
    """Map a real tool result to the UI activity kinds."""
    if output.get("error"):
        return "bị chặn"
    if output.get("awaiting_user"):
        return "chờ xác nhận" if args.get("response_type") == "yes_no" else "hỏi lại"
    status = output.get("status")
    if status == "needs_confirmation":
        return "chờ xác nhận"
    if status in ("created", "cancelled"):
        return "ghi"
    return "đọc"


def activity_entries(result: dict[str, Any], artifact_version: str) -> list[dict[str, Any]]:
    entries = []
    for event in result["tool_events"]:
        args = event.get("args") or {}
        raw = event.get("result")
        output = raw if isinstance(raw, dict) else {"value": raw}
        entries.append({
            "tool": event["tool"],
            "kind": classify(args, output),
            "input": args,
            "output": output,
            "result": None if output.get("error") else output,
            "error": output.get("error"),
            "version": artifact_version,
        })
    if not entries:
        entries.append({
            "tool": None,
            "kind": "không gọi tool",
            "input": {"no_tool": True},
            "output": {"note": "Agent trả lời trực tiếp, không gọi tool."},
            "result": None,
            "error": None,
            "version": artifact_version,
        })
    return entries


def quick_replies(result: dict[str, Any]) -> list[str]:
    if result["status"] != "waiting_for_user":
        return []
    pending = next(
        (event["result"] for event in reversed(result["tool_events"])
         if isinstance(event.get("result"), dict) and event["result"].get("awaiting_user")),
        None,
    )
    if pending is None:
        return []
    if pending.get("response_type") == "yes_no":
        return ["Xác nhận", "Hủy"]
    return [str(option) for option in pending.get("options") or []]


class ChatService:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.provider = make_provider(args.provider)
        self.model = args.model or getattr(self.provider, "default_model", None)
        self.sessions: dict[tuple[str, str], dict[str, Any]] = {}
        self.lock = threading.Lock()

    def _session(self, session_id: str, version: str) -> dict[str, Any]:
        key = (session_id, version)
        if key not in self.sessions:
            # Read artifacts when the session starts so the hash matches the text used.
            artifact_version = build_artifact_version(version, self.args.system_prompt, self.args.tools)
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
            transcript_id = "_".join([safe_slug(version), safe_slug(self.args.provider), "ui", safe_slug(session_id), timestamp])
            self.sessions[key] = {
                "system_prompt": self.args.system_prompt.read_text(encoding="utf-8"),
                "tools": to_openai_tools(load_tool_declarations(self.args.tools)),
                "artifact_version": artifact_version.artifact_version,
                "history": [],
                "path": self.args.transcripts_dir / f"{transcript_id}.transcript.json",
                "transcript": {
                    "transcript_id": transcript_id,
                    **artifact_version_dict(artifact_version),
                    "provider": self.args.provider,
                    "model": self.model,
                    "interface": "index.html via server.py",
                    "session_id": session_id,
                    "system_prompt": str(self.args.system_prompt),
                    "tools": str(self.args.tools),
                    "history_window": self.args.history_window,
                    "max_tool_rounds": self.args.max_tool_rounds,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                    "turns": [],
                },
            }
        return self.sessions[key]

    def chat(self, session_id: str, version: str, message: str) -> tuple[HTTPStatus, dict[str, Any]]:
        with self.lock:
            session = self._session(session_id, version)
            transcript = session["transcript"]
            turn = {
                "turn_index": len(transcript["turns"]) + 1,
                "started_at": now_iso(),
                "user": message,
                "status": "started",
                "assistant_text": None,
                "rounds": [],
                "tool_events": [],
            }
            messages = [
                {"role": "system", "content": session["system_prompt"]},
                *trim_history(session["history"], self.args.history_window),
                {"role": "user", "content": message},
            ]
            try:
                result = run_model_tool_loop(
                    provider=self.provider,
                    messages=messages,
                    tools=session["tools"],
                    model=self.args.model,
                    max_tool_rounds=self.args.max_tool_rounds,
                )
            except Exception as exc:
                turn.update({"status": "provider_error", "error": f"{type(exc).__name__}: {exc}", "ended_at": now_iso()})
                transcript["turns"].append(turn)
                write_transcript(session["path"], transcript)
                return HTTPStatus.BAD_GATEWAY, {
                    "error": "provider_error",
                    "message": turn["error"],
                    "version": version,
                    "artifact_version": session["artifact_version"],
                    "transcript": display_path(session["path"]),
                }

            turn.update(result)
            turn["ended_at"] = now_iso()
            transcript["turns"].append(turn)
            write_transcript(session["path"], transcript)
            session["history"].append({"role": "user", "content": message})
            session["history"].append({"role": "assistant", "content": result["assistant_text"]})
            return HTTPStatus.OK, {
                "reply": extract_reply(result["assistant_text"]),
                "raw_assistant_text": result["assistant_text"],
                "status": result["status"],
                "tool_calls": activity_entries(result, session["artifact_version"]),
                "quick_replies": quick_replies(result),
                "version": version,
                "artifact_version": session["artifact_version"],
                "model": self.model,
                "transcript": display_path(session["path"]),
            }


def fleet_snapshot() -> dict[str, Any]:
    robots = _hospital.load("robots")
    locations = _hospital.by_id(_hospital.load("locations")["locations"], "location_id")
    return {
        "snapshot_at": robots["snapshot_at"],
        "robots": [
            {
                "robot_id": robot["robot_id"],
                "status": robot["status"],
                "battery_pct": robot["battery_pct"],
                "location_id": robot["location_id"],
                "location_name": locations.get(robot["location_id"], {}).get("name", robot["location_id"]),
            }
            for robot in robots["robots"]
        ],
    }


def make_handler(service: ChatService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")

        def do_OPTIONS(self) -> None:  # noqa: N802 - http.server naming
            self._send(HTTPStatus.NO_CONTENT, b"", "text/plain")

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, UI_FILE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/fleet":
                self._json(HTTPStatus.OK, fleet_snapshot())
            elif path == "/health":
                self._json(HTTPStatus.OK, {"ok": True, "provider": service.args.provider, "model": service.model})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": f"No route {path}"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] != "/chat":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": f"No route {self.path}"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json", "message": "Send a JSON body."})
                return
            message = body.get("message")
            if not isinstance(message, str) or not message.strip():
                self._json(HTTPStatus.BAD_REQUEST, {"error": "missing_message", "message": "message must be a non-empty string."})
                return
            if len(message) > MAX_MESSAGE_CHARS:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "message_too_long", "max_chars": MAX_MESSAGE_CHARS})
                return
            session_id = str(body.get("session_id") or "default")[:64]
            version = safe_slug(str(body.get("version") or "ui"))[:32]
            try:
                status, payload = service.chat(session_id, version, message.strip())
            except Exception as exc:  # surface server bugs to the UI instead of dropping the connection
                status, payload = HTTPStatus.INTERNAL_SERVER_ERROR, {
                    "error": "server_error",
                    "message": f"{type(exc).__name__}: {exc}",
                    "version": version,
                }
            self._json(status, payload)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base signature
            print(f"[server] {self.address_string()} {format % args}")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve index.html and a /chat endpoint backed by the real agent tool loop.")
    parser.add_argument("--provider", choices=["openrouter", "openai", "anthropic", "gemini"], default="anthropic")
    parser.add_argument("--model", default=None)
    parser.add_argument("--system-prompt", type=Path, default=ARTIFACTS_DIR / "system_prompt.md")
    parser.add_argument("--tools", type=Path, default=ARTIFACTS_DIR / "tools.yaml")
    parser.add_argument("--transcripts-dir", type=Path, default=ROOT / "transcripts")
    parser.add_argument("--history-window", type=int, default=5)
    parser.add_argument("--max-tool-rounds", type=int, default=4)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    service = ChatService(args)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    print(f"AMR UI: http://{args.host}:{args.port}/  provider={args.provider} model={service.model}")
    print(f"prompt={args.system_prompt}  tools={args.tools}  transcripts={args.transcripts_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
