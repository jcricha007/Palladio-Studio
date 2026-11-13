"""Import a prepared, north-aligned elevation grid into the property frame."""

from datetime import datetime

from .scene import ValidationError, number, required_text


def surveyed_landscape(data):
    if not isinstance(data, dict):
        raise ValidationError("Elevation grid must be a JSON object.")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValidationError("Elevation grid version must be 1.")
    size = data.get("size")
    if type(size) is not int or not 3 <= size <= 129 or size % 2 == 0:
        raise ValidationError("Grid size must be an odd integer from 3 to 129.")
    spacing = number(data.get("spacing_m"), "Sample spacing (m)", 0.25, 100)
    extent = spacing * (size - 1)
    if not 20 <= extent <= 256:
        raise ValidationError("The grid must cover 20 to 256 metres per side.")

    latitude = number(data.get("latitude"), "Centre latitude", -90, 90)
    longitude = number(data.get("longitude"), "Centre longitude", -180, 180)
    dataset = required_text(data.get("dataset"), "Elevation source", 200)
    datum = required_text(data.get("vertical_datum"), "Vertical datum", 120)
    samples = data.get("elevations_m")
    if not isinstance(samples, list) or len(samples) != size * size:
        raise ValidationError("Supply size × size elevation samples in row-major order.")
    samples = [number(sample, "Elevation (m)", -12000, 10000) for sample in samples]
    origin = samples[len(samples) // 2]
    heights = [sample - origin for sample in samples]
    if max(map(abs, heights)) > 200:
        raise ValidationError("Samples must be within 200 metres of the centre elevation.")

    baseline = {
        "source": {
            "kind": "elevation grid",
            "profile": "Imported elevation",
            "dataset": dataset,
            "vertical_datum": datum,
            "latitude": latitude,
            "longitude": longitude,
            "origin_elevation_m": origin,
        },
        "terrain": {"size": size, "spacing": spacing, "heights": heights},
        "vegetation": [],
        "environment": {"weather": "clear", "hour": 16},
    }

    if "acquisition" in data:
        acquisition = data["acquisition"]
        if not isinstance(acquisition, dict):
            raise ValidationError("Acquisition metadata must be an object.")
        retrieved = required_text(acquisition.get("retrieved_utc"), "Acquisition time", 80)
        try:
            if datetime.fromisoformat(retrieved).tzinfo is None:
                raise ValueError("Timezone is required")
        except ValueError as error:
            raise ValidationError("Acquisition time must be an ISO timestamp with a timezone.") from error
        tiles = acquisition.get("source_tiles")
        if not isinstance(tiles, list) or not 1 <= len(tiles) <= size * size:
            raise ValidationError("Acquisition metadata needs source tiles.")
        validated_tiles = []
        for tile in tiles:
            if not isinstance(tile, dict) or type(tile.get("id")) is not int:
                raise ValidationError("Each source tile needs a raster ID.")
            validated_tiles.append({
                "id": tile["id"],
                "name": required_text(tile.get("name"), "Source tile", 200),
                "resolution": number(tile.get("resolution"), "Source resolution", 0.0000001, 100000),
            })
        baseline["source"]["acquisition"] = {
            "service": required_text(acquisition.get("service"), "Source service", 500),
            "retrieved_utc": retrieved,
            "sampling": required_text(acquisition.get("sampling"), "Sampling method", 200),
            "source_tiles": validated_tiles,
        }
    return baseline
