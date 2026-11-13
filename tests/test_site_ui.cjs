const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const nodes = new Map();
class Element {
  constructor() { this.value = ""; this.events = {}; this.hidden = false; this.checked = false; }
  addEventListener(name, action) { (this.events[name] ||= []).push(action); }
  replaceChildren(...children) { this.children = children; this.value = children[0].value; }
  checkValidity() { return Number.isFinite(Number(this.value)); }
}
const node = id => {
  if (!nodes.has(id)) nodes.set(id, new Element());
  return nodes.get(id);
};
const emit = (id, event) => node(id).events[event].forEach(action => action());
let reply, lastSignal, updates = 0;
const context = vm.createContext({
  AbortController, Option: function(label, value) { this.label = label; this.value = String(value); },
  Viewport: class { update() { updates++; } reset() {} },
  find: node,
  api: async (path, data, signal) => { lastSignal = signal; return reply(path, data); },
});
vm.runInContext(fs.readFileSync("palladio/web/site-picker.js", "utf8")
  .replace(/^import .+;$/gm, "").replace("export class", "class") +
  "\nconst picker = new SitePicker(find, api, () => {});", context);
const evaluate = source => vm.runInContext(source, context);
const baseline = {
  terrain: {size: 3, spacing: 10, heights: [1, 2, 3, 4, 0, 5, 6, 7, 8]},
  environment: {weather: "clear", hour: 16},
  source: {dataset: "USGS 3DEP", origin_elevation_m: 600, vertical_datum: "Source datum",
    acquisition: {retrieved_utc: "2026-01-01T00:00:00+00:00", source_tiles: [{name: "Tile", resolution: 1}]}},
};
const result = {key: "abc", cached: false, baseline};
node("site-latitude").value = "35.6";
node("site-longitude").value = "-82.6";
node("site-span").value = "128";
(async () => {
  reply = async () => result;
  await evaluate("picker.download()");
  assert.equal(evaluate('picker.propertyData("House").site_key'), "abc");
  assert.equal(updates, 1);
  emit("site-latitude", "input");
  assert.throws(() => evaluate('picker.propertyData("House")'), /Preview the current terrain/);

  let release;
  reply = async () => new Promise(resolve => { release = resolve; });
  const pending = evaluate("picker.download()");
  emit("site-longitude", "change");
  assert.equal(lastSignal.aborted, true);
  release(result);
  await pending;
  assert.equal(evaluate("picker.preview"), null);

  const cancelled = evaluate("picker.download()");
  emit("cancel-site", "click");
  release(result);
  await cancelled;
  assert.equal(evaluate("picker.preview"), null);
  assert.match(node("site-status").textContent, /cancelled/);

  node("site-address").value = "Street";
  reply = async () => [{label: "Candidate", latitude: 36, longitude: -83}];
  await evaluate("picker.lookup()");
  assert.equal(node("site-latitude").value, "35.6");
  assert.equal(node("site-matches").children.length, 2);
  node("site-matches").value = "0";
  emit("site-matches", "change");
  assert.equal(node("site-latitude").value, 36);
  assert.equal(node("site-longitude").value, -83);

  node("site-latitude").value = "36";
  node("site-longitude").value = "-83";
  reply = async () => result;
  await evaluate("picker.download()");
  emit("property-dialog", "close");
  assert.equal(evaluate("picker.preview"), null);

  reply = async () => { throw new Error("No coverage"); };
  await evaluate("picker.download()");
  assert.match(node("site-status").textContent, /No coverage/);
  assert.equal(evaluate("picker.preview"), null);
  console.log("PASS: terrain preview, coordinate invalidation, cancellation, late replies, address selection, dialog close, coverage errors");
})().catch(error => { console.error(error); process.exitCode = 1; });
