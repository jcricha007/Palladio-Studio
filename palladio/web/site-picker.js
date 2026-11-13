import {Viewport} from "./viewport.js";

export class SitePicker {
  constructor(find, api, changed) {
    this.find = find;
    this.api = api;
    this.changed = changed;
    this.generation = 0;
    this.controller = null;
    this.preview = null;
    this.matches = [];
    this.viewport = null;
    for (const id of ["site-latitude", "site-longitude", "site-span", "site-refresh"]) {
      for (const event of ["input", "change"]) find(id).addEventListener(event, () => this.invalidate());
    }
    find("site-address").addEventListener("input", () => {
      this.invalidate();
      find("site-matches-field").hidden = true;
    });
    find("lookup-address").addEventListener("click", () => this.lookup());
    find("preview-site").addEventListener("click", () => this.download());
    find("cancel-site").addEventListener("click", () => this.invalidate("Request cancelled."));
    find("site-matches").addEventListener("change", () => {
      this.invalidate();
      const match = this.matches[Number(find("site-matches").value)];
      if (!match || find("site-matches").value === "") return;
      find("site-latitude").value = match.latitude;
      find("site-longitude").value = match.longitude;
      this.message("Check the approximate coordinates, then preview the terrain.");
    });
    find("property-dialog").addEventListener("close", () => this.invalidate());
  }

  message(text) {
    this.find("site-status").textContent = text;
  }

  sync() {
    this.find("lookup-address").disabled = Boolean(this.controller);
    this.find("preview-site").disabled = Boolean(this.controller);
    this.find("cancel-site").hidden = !this.controller;
    this.changed();
  }

  invalidate(message = "") {
    this.generation += 1;
    this.controller?.abort();
    this.controller = null;
    this.preview = null;
    this.find("site-preview").hidden = true;
    this.message(message);
    this.sync();
  }

  signature() {
    return ["site-latitude", "site-longitude", "site-span"].map(id => this.find(id).value).join("|");
  }

  propertyData(name) {
    if (!this.preview || this.preview.signature !== this.signature()) {
      throw new Error("Preview the current terrain before creating the property.");
    }
    return {name, site_key: this.preview.key};
  }

  async lookup() {
    const address = this.find("site-address").value.trim();
    if (!address) {
      this.message("Enter a U.S. street address or use coordinates directly.");
      return;
    }
    await this.request("/api/sites/lookup", {address}, "Looking up the address…", matches => {
      this.matches = matches;
      this.find("site-matches").replaceChildren(new Option("Choose a matching address", ""),
        ...matches.map((match, index) => new Option(match.label, index)));
      this.find("site-matches-field").hidden = matches.length === 0;
      this.message(matches.length ? "Choose an address match and check its approximate coordinates."
        : "No matching address. Enter latitude and longitude directly.");
    });
  }

  async download() {
    const fields = ["site-latitude", "site-longitude", "site-span"];
    if (fields.some(id => !this.find(id).value.trim() || !this.find(id).checkValidity())) {
      this.message("Enter valid latitude, longitude, and site width.");
      return;
    }
    const signature = this.signature();
    const [latitude, longitude, span_m] = fields.map(id => Number(this.find(id).value));
    await this.request("/api/sites/preview", {
      latitude, longitude, span_m, refresh: this.find("site-refresh").checked,
    }, "Loading USGS terrain or its saved cache…", result => {
      if (signature !== this.signature()) return;
      const {baseline} = result;
      const heights = baseline.terrain.heights;
      const low = Math.min(...heights), high = Math.max(...heights);
      const origin = baseline.source.origin_elevation_m;
      this.find("site-preview").hidden = false;
      this.find("site-summary").textContent =
        `${span_m} × ${span_m} m · ${baseline.terrain.size} × ${baseline.terrain.size} samples · ${baseline.terrain.spacing} m spacing. ` +
        `Elevation ${(low + origin).toFixed(1)}–${(high + origin).toFixed(1)} m. North is −Z.`;
      const acquisition = baseline.source.acquisition;
      this.find("site-provenance").textContent =
        `${baseline.source.dataset} · Downloaded ${acquisition.retrieved_utc}. ` +
        `Source tiles: ${acquisition.source_tiles.map(tile => tile.name).join(", ")}. ` +
        `Source pixel sizes (service-reported values): ${[...new Set(acquisition.source_tiles.map(tile => tile.resolution))].join(", ")}. ` +
        `Vertical datum: ${baseline.source.vertical_datum}.`;
      this.preview = {key: result.key, signature};
      try {
        this.viewport ||= new Viewport(this.find("site-canvas"), () => {});
        this.viewport.update({id: result.key, baseline, scene: {elements: [], environment: baseline.environment}}, true, {}, null);
        this.viewport.reset();
      } catch (error) {
        this.message("Terrain ready. " + error.message);
        return;
      }
      this.message(result.cached ? "Cached terrain ready. Create property to save this site."
        : "Terrain downloaded. Create property to save this site.");
    });
  }

  async request(path, body, message, receive) {
    if (this.controller) return;
    this.invalidate();
    const generation = this.generation;
    const controller = new AbortController();
    this.controller = controller;
    this.message(message);
    this.sync();
    try {
      const result = await this.api(path, body, controller.signal);
      if (generation !== this.generation) return;
      receive(result);
    } catch (error) {
      if (generation === this.generation) this.message(error.message);
    } finally {
      if (generation === this.generation) {
        this.controller = null;
        this.sync();
      }
    }
  }
}
