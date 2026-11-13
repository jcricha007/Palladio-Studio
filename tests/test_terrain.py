import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from palladio.scene import ValidationError
from palladio.store import Library
from palladio.unreal import unreal_view


class ElevationImportTests(unittest.TestCase):
    def setUp(self):
        fixture = Path(__file__).resolve().parents[1] / "examples" / "elevation-grid.json"
        self.grid = json.loads(fixture.read_text(encoding="utf-8"))
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database = Path(directory.name) / "properties.sqlite3"
        self.library = Library(self.database)

    def test_import_preserves_relief_provenance_and_original_site(self):
        created = self.library.create("Hillside", None, elevation=self.grid)
        project_id = created["id"]
        baseline = created["baseline"]
        self.assertEqual(baseline["source"]["origin_elevation_m"], 600)
        self.assertEqual(baseline["source"]["dataset"], self.grid["dataset"])
        self.assertEqual(baseline["source"]["vertical_datum"], self.grid["vertical_datum"])
        self.assertEqual(baseline["terrain"]["heights"], [
            sample - 600 for sample in self.grid["elevations_m"]
        ])
        self.assertEqual(created["scene"]["elements"], [])
        self.library.commit(project_id, 1, [{
            "action": "environment", "environment": {"weather": "fog"},
        }])
        reopened = Library(self.database).get(project_id)
        self.assertEqual(reopened["baseline"], baseline)
        view = unreal_view(reopened)
        self.assertEqual(view["vertices_cm"][0], [-2400, -2400, 500])
        self.assertEqual(view["vertices_cm"][12], [0, 0, 0])
        self.assertEqual(view["vertices_cm"][-1], [2400, 2400, -700])
        self.assertEqual(view["baseline_environment"]["weather"], "clear")
        self.assertEqual(view["environment"]["weather"], "fog")

    def test_invalid_import_does_not_create_a_property(self):
        for changes in (
            {"version": True},
            {"size": 4},
            {"spacing_m": 100},
            {"latitude": 91},
            {"vertical_datum": ""},
            {"elevations_m": [0]},
            {"elevations_m": [float("nan")] + self.grid["elevations_m"][1:]},
            {"elevations_m": [950] + self.grid["elevations_m"][1:]},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.library.create("Invalid", None, elevation={**self.grid, **changes})
        with self.assertRaises(ValidationError):
            self.library.create("Invalid", None, starter=True, elevation=self.grid)
        self.assertEqual(self.library.list(), [])
