"""SQLite property library and transactional revision history."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .terrain import surveyed_landscape

from .scene import ValidationError, edit_scene, landscape, required_text, starter_elements


class MissingProject(LookupError):
    pass


class RevisionConflict(RuntimeError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Library:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                connection.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE IF NOT EXISTS properties (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        baseline TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        updated TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS revisions (
                        project_id TEXT NOT NULL REFERENCES properties (id),
                        number INTEGER NOT NULL,
                        label TEXT NOT NULL,
                        scene TEXT NOT NULL,
                        PRIMARY KEY (project_id, number)
                    );
                    PRAGMA user_version = 1;
                    COMMIT;
                """)
            elif version != 1:
                raise RuntimeError(f"Unsupported Palladio database schema {version}.")

    @contextmanager
    def connect(self, *, write=False):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                if write:
                    connection.execute("BEGIN IMMEDIATE")
                yield connection
        finally:
            connection.close()

    def list(self):
        with self.connect() as connection:
            return [dict(row) for row in connection.execute("""
                SELECT id, name, revision, updated FROM properties ORDER BY updated DESC
            """)]

    def get(self, project_id):
        with self.connect() as connection:
            return self._read(connection, project_id)

    def _read(self, connection, project_id):
        row = connection.execute("""
            SELECT p.id, p.name, p.baseline, p.revision, p.updated, r.scene
            FROM properties AS p JOIN revisions AS r
            ON r.project_id = p.id AND r.number = p.revision WHERE p.id = ?
        """, (project_id,)).fetchone()
        if row is None:
            raise MissingProject("Property not found.")
        result = dict(row)
        result["baseline"] = json.loads(result["baseline"])
        result["scene"] = json.loads(result["scene"])
        # Exclude newer revisions if another connection commits between the reads.
        result["history"] = [dict(entry) for entry in connection.execute("""
            SELECT number, label FROM revisions WHERE project_id = ? AND number <= ?
            ORDER BY number DESC
        """, (project_id, result["revision"]))]
        return result

    def create(self, name, brief, starter=False, *, elevation=None):
        name = required_text(name, "Property name", 100)
        if type(starter) is not bool:
            raise ValidationError("Starter pavilion must be true or false.")
        if elevation is not None and starter:
            raise ValidationError("Place buildings manually on imported terrain.")
        baseline = landscape(brief) if elevation is None else surveyed_landscape(elevation)
        scene = {
            "environment": baseline["environment"],
            "elements": starter_elements() if starter else [],
        }
        with self.connect(write=True) as connection:
            return self._insert(connection, name, baseline, scene, "Created property")

    def _insert(self, connection, name, baseline, scene, label):
        project_id = str(uuid4())
        connection.execute("INSERT INTO properties VALUES (?, ?, ?, 1, ?)", (
            project_id, name, json.dumps(baseline), timestamp(),
        ))
        connection.execute("INSERT INTO revisions VALUES (?, 1, ?, ?)", (
            project_id, label, json.dumps(scene),
        ))
        return self._read(connection, project_id)

    def duplicate(self, project_id, name):
        name = required_text(name, "Property name", 100)
        with self.connect(write=True) as connection:
            original = self._read(connection, project_id)
            return self._insert(
                connection, name, original["baseline"], original["scene"],
                f"Duplicated {original['name']} at revision {original['revision']}",
            )

    def commit(self, project_id, expected_revision, commands=None, restore=None):
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValidationError("A valid current revision is required.")
        with self.connect(write=True) as connection:
            current = self._read(connection, project_id)
            if expected_revision != current["revision"]:
                raise RevisionConflict("This property changed in another session. Reload it and retry.")
            if restore is not None:
                if type(restore) is not int or commands is not None:
                    raise ValidationError("Choose a single revision to restore.")
                row = connection.execute("""
                    SELECT scene FROM revisions WHERE project_id = ? AND number = ?
                """, (project_id, restore)).fetchone()
                if row is None:
                    raise ValidationError("That revision does not exist.")
                scene = json.loads(row["scene"])
                label = f"Restored revision {restore}"
            else:
                if not isinstance(commands, list) or not 1 <= len(commands) <= 100:
                    raise ValidationError("Submit between 1 and 100 scene commands.")
                scene = current["scene"]
                labels = [edit_scene(scene, command, current["baseline"]) for command in commands]
                label = labels[0] if len(labels) == 1 else f"Applied {len(labels)} edits"
            revision = current["revision"] + 1
            connection.execute("INSERT INTO revisions VALUES (?, ?, ?, ?)", (
                project_id, revision, label, json.dumps(scene),
            ))
            connection.execute("UPDATE properties SET revision = ?, updated = ? WHERE id = ?", (
                revision, timestamp(), project_id,
            ))
            return self._read(connection, project_id)
