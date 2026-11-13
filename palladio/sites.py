"""Download and cache a local ground-elevation grid from USGS 3DEP."""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import threading
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from .scene import ValidationError, number, required_text
from .terrain import surveyed_landscape

ELEVATION_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer"
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
KEY = re.compile(r"[a-f0-9]{64}")
GRID_SIZE = 17


class SiteError(RuntimeError):
    pass


def request_json(url, parameters):
    request = Request(url + "?" + urlencode(parameters), headers={
        "User-Agent": "Palladio-Studio/0.3",
        "Accept": "application/json",
    })
    try:
        with urlopen(request, timeout=25) as response:
            content = response.read(2_000_001)
        if len(content) > 2_000_000:
            raise SiteError("The site service returned too much data. Try again.")
        data = json.loads(content)
    except (OSError, URLError, ValueError, RecursionError) as error:
        raise SiteError("The site service could not be reached or returned invalid data. Try again when online.") from error
    if not isinstance(data, dict) or data.get("error") or data.get("errors"):
        raise SiteError("The site service could not complete this request. Check the location and try again.")
    return data


def grid_points(latitude, longitude, span):
    """WGS84 local tangent-plane approximation, north-first rows, eastward columns."""
    lat = math.radians(latitude)
    eccentricity_squared = 0.00669437999014
    radius = 6378137.0
    denominator = 1 - eccentricity_squared * math.sin(lat) ** 2
    north_radius = radius * (1 - eccentricity_squared) / denominator ** 1.5
    east_radius = radius / math.sqrt(denominator) * math.cos(lat)
    points = []
    for row in range(GRID_SIZE):
        north = span / 2 - row * span / (GRID_SIZE - 1)
        for column in range(GRID_SIZE):
            east = column * span / (GRID_SIZE - 1) - span / 2
            point_latitude = latitude + math.degrees(north / north_radius)
            point_longitude = (longitude + math.degrees(east / east_radius) + 180) % 360 - 180
            points.append([round(point_longitude, 9), round(point_latitude, 9)])
    return points


class SiteService:
    def __init__(self, cache_directory, transport=request_json):
        self.cache = Path(cache_directory)
        self.transport = transport
        self.lock = threading.Lock()

    def lookup(self, address):
        address = required_text(address, "U.S. street address", 300)
        data = self.transport(GEOCODER_URL, {
            "address": address, "benchmark": "Public_AR_Current", "format": "json",
        })
        try:
            matches = data["result"]["addressMatches"]
            if not isinstance(matches, list):
                raise ValueError("Invalid matches")
            return [{
                "label": required_text(match["matchedAddress"], "Matched address", 500),
                "latitude": number(match["coordinates"]["y"], "Latitude", -85, 85),
                "longitude": number(match["coordinates"]["x"], "Longitude", -180, 180),
            } for match in matches[:10]]
        except (KeyError, TypeError, ValueError) as error:
            raise SiteError("The address service returned an invalid result. Enter coordinates directly.") from error

    def load(self, key):
        if not isinstance(key, str) or not KEY.fullmatch(key):
            raise ValidationError("Choose a downloaded terrain preview before creating the property.")
        try:
            raw = (self.cache / f"grid-{key}.json").read_bytes()
            if hashlib.sha256(raw).hexdigest() != key:
                raise ValueError("Cache checksum mismatch")
            grid = json.loads(raw)
            surveyed_landscape(grid)
            return grid
        except (OSError, ValueError, TypeError) as error:
            raise SiteError("This terrain preview is unavailable. Preview the terrain again.") from error

    def preview(self, latitude, longitude, span=128, refresh=False):
        latitude = number(latitude, "Latitude", -85, 85)
        longitude = number(longitude, "Longitude", -180, 180)
        span = number(span, "Site width (m)", 20, 256)
        if type(refresh) is not bool:
            raise ValidationError("Refresh must be true or false.")
        # Use exactly the rounded centre in both the request and the cache identity.
        latitude, longitude = round(latitude, 7), round(longitude, 7)
        request_key = hashlib.sha256(json.dumps(
            [1, latitude, longitude, float(span), GRID_SIZE], separators=(",", ":")
        ).encode()).hexdigest()
        pointer = self.cache / f"request-{request_key}.txt"
        if not refresh:
            try:
                key = pointer.read_text(encoding="ascii")
                grid = self.load(key)
                return {"key": key, "cached": True, "baseline": surveyed_landscape(grid)}
            except (OSError, SiteError, ValidationError):
                pass
        if not self.lock.acquire(blocking=False):
            raise SiteError("Another terrain download is running. Try again after it finishes.")
        try:
            grid = self._download(latitude, longitude, span)
            baseline = surveyed_landscape(grid)
            raw = json.dumps(grid, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
            key = hashlib.sha256(raw).hexdigest()
            self.cache.mkdir(parents=True, exist_ok=True)
            self._write(self.cache / f"grid-{key}.json", raw)
            self._write(pointer, key.encode("ascii"))
            return {"key": key, "cached": False, "baseline": baseline}
        except OSError as error:
            raise SiteError("The terrain cache could not be saved. Check available disk space and access.") from error
        finally:
            self.lock.release()

    @staticmethod
    def _write(destination, content):
        temporary = destination.with_suffix("." + uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(content)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _download(self, latitude, longitude, span):
        points = grid_points(latitude, longitude, span)
        elevations = []
        sources = {}
        for start in range(0, len(points), 64):
            batch = points[start:start + 64]
            data = self.transport(ELEVATION_URL + "/getSamples", {
                "f": "json",
                "geometryType": "esriGeometryMultipoint",
                "geometry": json.dumps({"points": batch, "spatialReference": {"wkid": 4326}}, separators=(",", ":")),
                "returnFirstValueOnly": "true",
                "interpolation": "RSP_BilinearInterpolation",
                "outFields": "Name,Source,DEM_Type",
            })
            values = [None] * len(batch)
            try:
                samples = data["samples"]
                if not isinstance(samples, list):
                    raise ValueError("Invalid samples")
                for sample in samples:
                    index = sample["locationId"]
                    if type(index) is not int or not 0 <= index < len(batch) or values[index] is not None:
                        raise ValueError("Invalid sample identity")
                    location = sample["location"]
                    if (abs(number(location["x"], "Sample longitude", -180, 180) - batch[index][0]) > 0.0000001 or
                            abs(number(location["y"], "Sample latitude", -90, 90) - batch[index][1]) > 0.0000001):
                        raise ValueError("Mismatched sample coordinates")
                    value = float(sample["value"])
                    values[index] = number(value, "Elevation (m)", -12000, 10000)
                    raster = sample["rasterId"]
                    resolution = number(sample["resolution"], "Source resolution", 0.0000001, 100000)
                    name = required_text(sample["attributes"]["Name"], "Source tile", 200)
                    if type(raster) is not int:
                        raise ValueError("Invalid raster identity")
                    sources[raster] = {"id": raster, "name": name, "resolution": resolution}
                if any(value is None for value in values):
                    raise ValueError("Incomplete coverage")
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                raise SiteError("USGS returned incomplete or invalid elevation coverage. Choose another site or import an elevation file.") from error
            elevations.extend(values)
        return {
            "version": 1, "size": GRID_SIZE, "spacing_m": span / (GRID_SIZE - 1),
            "latitude": latitude, "longitude": longitude,
            "dataset": "USGS 3DEP",
            "vertical_datum": "USGS source datum; verify the listed source tiles",
            "elevations_m": elevations,
            "acquisition": {
                "service": ELEVATION_URL,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "sampling": "Bilinear; WGS84 local tangent plane",
                "source_tiles": sorted(sources.values(), key=lambda tile: tile["id"]),
            },
        }
