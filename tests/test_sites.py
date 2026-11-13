import copy
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from palladio.__main__ import handler_for
from palladio.scene import ValidationError
from palladio.sites import GEOCODER_URL, GRID_SIZE, SiteError, SiteService, grid_points
from palladio.store import Library


class SitesTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.requests = []
        self.offset = 0
        self.fault = None
        self.sites = SiteService(self.root / "cache", self.transport)

    def transport(self, url, parameters):
        self.requests.append((url, parameters))
        if url == GEOCODER_URL:
            return {"result": {"addressMatches": [{
                "matchedAddress": "Reference address",
                "coordinates": {"x": -82.6, "y": 35.6},
            }]}}
        points = json.loads(parameters["geometry"])["points"]
        samples = [{
            "locationId": index, "location": {"x": point[0], "y": point[1]},
            "value": str(600 + (point[0] + 82.6) * 1000 + (point[1] - 35.6) * 1000 + self.offset),
            "rasterId": 7, "resolution": 1, "attributes": {"Name": "Reference tile"},
        } for index, point in enumerate(points)]
        if self.fault == "missing":
            samples.pop()
        elif self.fault == "nodata":
            samples[0]["value"] = "NoData"
        elif self.fault == "wrong-location":
            samples[0]["location"]["x"] += 1
        elif self.fault == "nan-location":
            samples[0]["location"]["x"] = float("nan")
        # Response order must not determine the vertex order.
        return {"samples": list(reversed(samples))}

    def test_grid_orientation_and_metre_spacing(self):
        points = grid_points(35.6, -82.6, 128)
        self.assertEqual(points[len(points) // 2], [-82.6, 35.6])
        self.assertLess(points[0][0], points[1][0])
        self.assertGreater(points[0][1], points[-1][1])
        self.assertAlmostEqual((points[1][0] - points[0][0]) * 90614, 8, delta=.02)
        self.assertAlmostEqual((points[0][1] - points[GRID_SIZE][1]) * 110946, 8, delta=.02)

    def test_refresh_keeps_reviewed_grid_and_reopens_offline(self):
        first = self.sites.preview(35.6, -82.6)
        old_grid = copy.deepcopy(self.sites.load(first["key"]))
        self.assertFalse(first["cached"])
        self.assertEqual(len(self.requests), 5)
        baseline = first["baseline"]
        self.assertAlmostEqual(baseline["terrain"]["heights"][GRID_SIZE ** 2 // 2], 0)
        self.assertEqual(baseline["source"]["acquisition"]["source_tiles"][0]["name"], "Reference tile")
        self.offset = 12
        updated = self.sites.preview(35.6, -82.6, refresh=True)
        self.assertNotEqual(first["key"], updated["key"])
        self.assertEqual(self.sites.load(first["key"]), old_grid)
        def offline(*args):
            self.fail("Cached terrain should be available without a request")
        offline_service = SiteService(self.root / "cache", offline)
        cached = offline_service.preview(35.6, -82.6)
        self.assertTrue(cached["cached"])
        self.assertEqual(cached["key"], updated["key"])
        self.assertEqual(offline_service.load(first["key"]), old_grid)

    def test_partial_or_invalid_elevation_never_creates_cache(self):
        for fault in ("missing", "nodata", "wrong-location", "nan-location"):
            self.fault = fault
            with self.subTest(fault=fault), self.assertRaises(SiteError):
                self.sites.preview(35.6, -82.6)
        self.assertFalse((self.root / "cache").exists())

    def test_invalid_arguments_and_cache_keys(self):
        for arguments in ((True, -82.6), (float("nan"), -82.6), (86, 0), (0, 200), (0, 0, 1000)):
            with self.subTest(arguments=arguments), self.assertRaises(ValidationError):
                self.sites.preview(*arguments)
        with self.assertRaises(ValidationError):
            self.sites.load("../outside")
        self.assertEqual(self.requests, [])

    def test_lookup_returns_a_candidate_without_requesting_elevation(self):
        self.assertEqual(self.sites.lookup("Reference address"),
                         [{"label": "Reference address", "latitude": 35.6, "longitude": -82.6}])
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0][0], GEOCODER_URL)

    def test_preview_and_save_through_http_preserve_provenance_after_restart(self):
        library = Library(self.root / "properties.sqlite3")
        with ThreadingHTTPServer(("127.0.0.1", 0), handler_for(library, sites=self.sites)) as server:
            worker = Thread(target=server.serve_forever)
            worker.start()
            try:
                address = f"http://127.0.0.1:{server.server_port}"
                def post(path, payload):
                    request = Request(address + path, data=json.dumps(payload).encode(),
                                      headers={"Content-Type": "application/json"})
                    with urlopen(request, timeout=5) as response:
                        return json.load(response)
                preview = post("/api/sites/preview", {"latitude": 35.6, "longitude": -82.6})
                self.assertEqual(library.list(), [])
                saved = post("/api/properties", {"name": "Real site", "site_key": preview["key"]})
                self.assertEqual(saved["baseline"], preview["baseline"])
                key = saved["id"]
                post(f"/api/properties/{key}/edit", {"revision": 1, "commands": [{
                    "action": "environment", "environment": {"weather": "fog"},
                }]})
                with self.assertRaises(HTTPError) as stale:
                    post(f"/api/properties/{key}/edit", {"revision": 1, "commands": [{
                        "action": "environment", "environment": {"weather": "rain"},
                    }]})
                self.assertEqual(stale.exception.code, 409)
                self.assertEqual(Library(library.path).get(key)["baseline"], preview["baseline"])
                duplicated = library.duplicate(key, "Alternative")
                self.assertEqual(duplicated["baseline"], preview["baseline"])
                with urlopen(address + f"/api/properties/{key}/unreal", timeout=5) as response:
                    view = json.load(response)
                self.assertEqual(len(view["vertices_cm"]), GRID_SIZE ** 2)
                self.assertEqual(view["vertices_cm"][GRID_SIZE ** 2 // 2], [0, 0, 0])
                self.assertEqual(view["environment"]["weather"], "fog")
                with self.assertRaises(HTTPError):
                    post("/api/properties", {"name": "Missing", "site_key": "0" * 64})
                self.assertEqual(len(library.list()), 2)
            finally:
                server.shutdown()
                worker.join()
