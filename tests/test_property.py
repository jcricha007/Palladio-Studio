from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from palladio.agent import preview
from palladio.scene import ValidationError, landscape
from palladio.store import Library, RevisionConflict


class PropertyTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "properties.sqlite3"
        self.library = Library(self.database)
        self.project = self.library.create("Ridge House", "A wooded hillside", starter=True)
        self.project_id = self.project["id"]

    def test_terrain_generation_is_deterministic_and_supports_three_profiles(self):
        for brief, profile in [
            ("A coastal bluff overlooking the ocean", "coastal bluff"),
            ("Open meadow", "open meadow"),
            ("A wooded hillside", "wooded hills"),
        ]:
            with self.subTest(profile=profile):
                baseline = landscape(brief)
                self.assertEqual(baseline, landscape(brief))
                self.assertEqual(baseline["source"]["profile"], profile)
                terrain = baseline["terrain"]
                self.assertEqual(len(terrain["heights"]), terrain["size"] ** 2)
                self.assertGreater(len(baseline["vegetation"]), 0)

    def test_committed_edit_reopens_and_preserves_original_site(self):
        changed = self.library.commit(self.project_id, 1, [{
            "action": "environment", "environment": {"weather": "fog", "hour": 7.5},
        }])
        reopened = Library(self.database).get(self.project_id)
        self.assertEqual(reopened, changed)
        self.assertEqual(reopened["scene"]["environment"], {"weather": "fog", "hour": 7.5})
        self.assertEqual(reopened["baseline"], self.project["baseline"])
        self.assertEqual(reopened["revision"], 2)

    def test_element_edit_and_restore_keep_identity_and_history(self):
        element = self.project["scene"]["elements"][0]
        revised = self.library.commit(self.project_id, 1, [{
            "action": "update", "id": element["id"],
            "element": {"size": [13, 0.25, 9], "yaw": 25, "material": "stone"},
        }])
        changed = revised["scene"]["elements"][0]
        self.assertEqual(changed["id"], element["id"])
        self.assertEqual(changed["size"], [13, 0.25, 9])
        self.assertEqual(changed["yaw"], 25)
        self.assertEqual(changed["material"], "stone")
        restored = self.library.commit(self.project_id, 2, restore=1)
        self.assertEqual(restored["scene"], self.project["scene"])
        self.assertEqual([entry["number"] for entry in restored["history"]], [3, 2, 1])

    def test_duplicate_is_independent(self):
        duplicate = self.library.duplicate(self.project_id, "Ridge House Alternative")
        self.assertNotEqual(duplicate["id"], self.project_id)
        self.assertEqual(duplicate["scene"], self.project["scene"])
        self.assertEqual(duplicate["baseline"], self.project["baseline"])
        self.library.commit(duplicate["id"], 1, [{
            "action": "remove", "id": duplicate["scene"]["elements"][0]["id"],
        }])
        self.assertEqual(self.library.get(self.project_id), self.project)
        self.assertEqual(len(self.library.list()), 2)

    def test_invalid_batch_is_atomic(self):
        with self.assertRaises(ValidationError):
            self.library.commit(self.project_id, 1, [
                {"action": "environment", "environment": {"weather": "rain"}},
                {"action": "update", "id": "missing", "element": {"yaw": 0}},
            ])
        self.assertEqual(self.library.get(self.project_id), self.project)

    def test_simultaneous_edits_to_same_revision_cannot_overwrite(self):
        def edit(weather):
            try:
                self.library.commit(self.project_id, 1, [
                    {"action": "environment", "environment": {"weather": weather}},
                ])
            except RevisionConflict:
                return False
            return True

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(edit, ["fog", "rain"])), [False, True])
        self.assertEqual(self.library.get(self.project_id)["revision"], 2)

    def test_prompt_preview_uses_the_same_edit_path_and_rejects_stale_plan(self):
        proposal = preview(self.project, "Set time to 17:30.")
        self.assertEqual(self.library.get(self.project_id), self.project)
        committed = self.library.commit(self.project_id, proposal["revision"], [proposal["command"]])
        self.assertEqual(committed["scene"]["environment"]["hour"], 17.5)
        with self.assertRaises(RevisionConflict):
            self.library.commit(self.project_id, proposal["revision"], [proposal["command"]])
        with self.assertRaises(ValidationError):
            preview(committed, "Use oak")


if __name__ == "__main__":
    unittest.main()
