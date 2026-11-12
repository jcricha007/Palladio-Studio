import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from palladio.__main__ import handler_for
from palladio.store import Library


class UnrealBridgeTest(unittest.TestCase):
    def test_existing_scene_round_trips_through_loopback(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "properties.sqlite3"
            library = Library(database)
            saved = library.create("Cliff House", "Ocean bluff", starter=True)
            roof = saved["scene"]["elements"][-1]
            library.commit(saved["id"], 1, [{
                "action": "update", "id": roof["id"],
                "element": {"position": [3, 2, -4], "size": [7, 2, 5], "yaw": 35},
            }, {"action": "environment", "environment": {"hour": 9, "weather": "fog"}}])
            with ThreadingHTTPServer(("127.0.0.1", 0), handler_for(Library(database))) as server:
                worker = Thread(target=server.serve_forever)
                worker.start()
                try:
                    endpoint = f"http://127.0.0.1:{server.server_port}/api/properties/{saved['id']}"
                    before = self.read(endpoint + "/unreal")
                    self.assertEqual(before["environment"], {"hour": 9, "weather": "fog"})
                    self.assertEqual(before["baseline_environment"], {"hour": 16, "weather": "clear"})
                    self.assertTrue(before["coastal"])
                    self.assertEqual(len(before["vertices_cm"]), 33 ** 2)
                    self.assertEqual(len(before["triangles"]), 6 * 32 ** 2)
                    self.assertEqual(before["triangles"][:6], [0, 33, 34, 0, 34, 1])
                    self.assertEqual(before["vertices_cm"][1][:2], [-6000, -6400])
                    native_roof = before["elements"][-1]
                    self.assertEqual(native_roof, {
                        "id": roof["id"], "name": roof["name"], "center_cm": [300, -400, 300],
                        "dimensions_cm": [700, 500, 200], "yaw_degrees": -35, "color": "#3a3632",
                    })

                    move = {"revision": before["revision"], "commands": [{
                        "action": "update", "id": native_roof["id"],
                        "element": {"position": [3.5, 2, -4.5]},
                    }]}
                    self.read(endpoint + "/edit", move)
                    with self.assertRaises(HTTPError) as stale:
                        self.read(endpoint + "/edit", move)
                    self.assertEqual(stale.exception.code, 409)
                    after = self.read(endpoint + "/unreal")
                    self.assertEqual(after["elements"][-1], {**native_roof, "center_cm": [350, -450, 300]})
                    self.assertEqual(after["vertices_cm"], before["vertices_cm"])
                    reopened = Library(database).get(saved["id"])
                    self.assertEqual([item["number"] for item in reopened["history"]], [3, 2, 1])
                finally:
                    server.shutdown()
                    worker.join()

    @staticmethod
    def read(url, data=None):
        request = Request(url)
        if data is not None:
            request.data = json.dumps(data).encode()
            request.add_header("Content-Type", "application/json")
        with urlopen(request, timeout=5) as response:
            return json.load(response)
