"""Run the local Palladio workspace with python -m palladio."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import webbrowser

from .local_agent import AgentError, AgentService, OllamaPlanner
from .assemblies import ASSEMBLIES, assembly_preview
from .scene import ELEMENTS, MATERIALS, WEATHER, ValidationError
from .store import Library, MissingProject, RevisionConflict

from .unreal import unreal_view

WEB = Path(__file__).with_name("web")
STATIC = {
    "/": ("index.html", "text/html"),
    "/studio.css": ("studio.css", "text/css"),
    "/studio.js": ("studio.js", "text/javascript"),
    "/viewport.js": ("viewport.js", "text/javascript"),
}
PROPERTY_ROUTE = re.compile(r"/api/properties/([a-f0-9-]{36})(?:/(duplicate|edit|preview|assembly-preview|unreal))?")


def handler_for(library, agent=None):
    agent = agent or AgentService()
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, content_type, body):
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # A cancelled preview must never become a server error or edit.

        def json_response(self, status, value):
            self.respond(status, "application/json", json.dumps(value).encode())

        def trusted_host(self):
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected:
                self.json_response(403, {"error": f"Open http://{expected} to use Palladio."})
                return False
            return True

        def do_GET(self):
            if not self.trusted_host():
                return
            path = urlsplit(self.path).path
            if path in STATIC:
                filename, content_type = STATIC[path]
                self.respond(200, content_type, (WEB / filename).read_bytes())
                return
            if path == "/api/agent":
                self.json_response(200, agent.describe())
                return
            if path == "/api/catalog":
                self.json_response(200, {"elements": ELEMENTS, "materials": MATERIALS, "weather": WEATHER, "assemblies": ASSEMBLIES})
                return
            if path == "/api/properties":
                self.json_response(200, library.list())
                return
            match = PROPERTY_ROUTE.fullmatch(path)
            if match and match[2] in (None, "unreal"):
                try:
                    project = library.get(match[1])
                    self.json_response(200, unreal_view(project) if match[2] == "unreal" else project)
                except MissingProject as error:
                    self.json_response(404, {"error": str(error)})
                return
            self.json_response(404, {"error": "Route not found."})

        def read_json(self):
            if self.headers.get_content_type() != "application/json":
                raise ValidationError("Send a JSON request.")
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1_000_000:
                    raise ValidationError("Request size is invalid.")
                payload = json.loads(self.rfile.read(size))
            except (json.JSONDecodeError, UnicodeError, ValueError, RecursionError) as error:
                raise ValidationError("Invalid JSON request.") from error
            if not isinstance(payload, dict):
                raise ValidationError("Request must be a JSON object.")
            return payload

        def do_POST(self):
            if not self.trusted_host():
                return
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://127.0.0.1:{self.server.server_port}":
                self.json_response(403, {"error": "Only the local Palladio workspace can make edits."})
                return
            path = urlsplit(self.path).path
            try:
                data = self.read_json()
                if path == "/api/agent/models":
                    self.json_response(200, agent.models())
                    return
                if path == "/api/properties":
                    result = library.create(data.get("name"), data.get("brief"), data.get("starter", False))
                    self.json_response(201, result)
                    return
                match = PROPERTY_ROUTE.fullmatch(path)
                if match and match[2] == "duplicate":
                    self.json_response(201, library.duplicate(match[1], data.get("name")))
                elif match and match[2] == "edit":
                    self.json_response(200, library.commit(
                        match[1], data.get("revision"), data.get("commands"), data.get("restore"),
                    ))
                elif match and match[2] == "assembly-preview":
                    self.json_response(200, assembly_preview(library.get(match[1]), data.get("assembly")))
                elif match and match[2] == "preview":
                    project = library.get(match[1])
                    plan = agent.preview(project, data.get("prompt"), data.get("selection"),
                                         provider=data.get("provider", "rules"), model=data.get("model"),
                                         revision=data.get("revision"))
                    if library.get(match[1])["revision"] != plan["revision"]:
                        raise RevisionConflict("This property changed while the agent was planning. Reload it and preview again.")
                    self.json_response(200, plan)
                else:
                    self.json_response(404, {"error": "Route not found."})
            except AgentError as error:
                self.json_response(error.status, {"error": str(error)})
            except ValidationError as error:
                self.json_response(400, {"error": str(error)})
            except MissingProject as error:
                self.json_response(404, {"error": str(error)})
            except RevisionConflict as error:
                self.json_response(409, {"error": str(error)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--library", default=Path(".palladio/properties.sqlite3"), type=Path)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--ollama-port", default=11434, type=int,
                        help="Local Ollama port on 127.0.0.1 (no remote endpoints).")
    arguments = parser.parse_args()
    library = Library(arguments.library)
    try:
        agent = AgentService(OllamaPlanner(port=arguments.ollama_port))
    except ValueError as error:
        parser.error(str(error))
    with ThreadingHTTPServer(("127.0.0.1", arguments.port), handler_for(library, agent)) as server:
        address = f"http://127.0.0.1:{server.server_port}"
        print(f"Palladio Studio is running at {address}", flush=True)
        print(f"Property library: {library.path}", flush=True)
        if not arguments.no_browser:
            webbrowser.open(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
