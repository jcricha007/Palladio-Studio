import {Viewport} from "./viewport.js";
import {DesignTools} from "./tools.js";
import {SitePicker} from "./site-picker.js";

const $ = id => document.getElementById(id);
const propertiesPath = "/api/properties";
let catalog;
let project;
let selected;
let baselineView = false;
let pending;
let busy = false;
let duplicating = false;
let viewport;
let viewportError = "";
let agentRequest = null;
let agentGeneration = 0;
let modelRequest = null;
let modelGeneration = 0;
let installedModels = [];
let agentEndpoint = "http://127.0.0.1:11434";
const sites = new SitePicker($, api, syncControls);
const designTools = new DesignTools($, previewTool, discardOnEdit);

function agentStatus(message, error = false) {
  $("agent-status").textContent = message;
  $("agent-status").dataset.error = String(error);
}

function rememberedModel(value) {
  try {
    if (value !== undefined) localStorage.setItem("palladio.agent.model", value);
    return localStorage.getItem("palladio.agent.model") || "";
  } catch { return ""; }
}

function cancelAgentRequest(message = "") {
  const active = Boolean(agentRequest);
  agentGeneration += 1;
  agentRequest?.abort();
  agentRequest = null;
  if (active && message) agentStatus(message);
  syncControls();
  return active;
}

function cancelModelRequest() {
  modelGeneration += 1;
  modelRequest?.abort();
  modelRequest = null;
}

async function refreshModels() {
  if (busy || $("agent-provider").value !== "ollama" || modelRequest) return;
  cancelAgentRequest();
  showPlan();
  const generation = ++modelGeneration;
  const controller = new AbortController();
  modelRequest = controller;
  const preferred = $("agent-model").value || rememberedModel();
  installedModels = [];
  $("agent-model").replaceChildren(option("", "Checking installed models…"));
  agentStatus("Connecting to local Ollama…");
  syncControls();
  try {
    const result = await api("/api/agent/models", {}, controller.signal);
    if (generation !== modelGeneration || $("agent-provider").value !== "ollama") return;
    if (!Array.isArray(result.models) || result.models.some(item => typeof item.name !== "string")) {
      throw new Error("Ollama returned an invalid model list.");
    }
    installedModels = result.models.map(item => item.name);
    $("agent-model").replaceChildren(option("", "Choose an installed model"),
      ...result.models.map(item => option(item.name, item.name)));
    $("agent-model").value = installedModels.includes(preferred) ? preferred : "";
    agentStatus(installedModels.length
      ? `Connected to ${agentEndpoint}. Choose a model, then preview your request.`
      : "Ollama is connected, but no models are installed. Install a model in Ollama, then Refresh models.");
  } catch (error) {
    if (generation !== modelGeneration) return;
    $("agent-model").replaceChildren(option("", "No models available"));
    agentStatus(error.message + " Start Ollama locally and Refresh models, or use Built-in commands.", true);
  } finally {
    if (generation === modelGeneration) {
      modelRequest = null;
      syncControls();
    }
  }
}

function changeAgent() {
  cancelAgentRequest();
  cancelModelRequest();
  showPlan();
  const local = $("agent-provider").value === "ollama";
  $("agent-model-label").hidden = !local;
  $("refresh-models").hidden = !local;
  $("agent-privacy").hidden = !local;
  if (local) refreshModels();
  else agentStatus("Built-in commands use no language model.");
  syncControls();
}

async function previewRequest() {
  if (busy || agentRequest || !project || baselineView) return;
  const provider = $("agent-provider").value;
  const model = $("agent-model").value;
  if (provider === "ollama" && (!model || !installedModels.includes(model))) {
    agentStatus("Choose an installed model before previewing.", true);
    return;
  }
  showPlan();
  const generation = ++agentGeneration;
  const controller = new AbortController();
  agentRequest = controller;
  const snapshot = {id: project.id, revision: project.revision, selection: selected,
    prompt: $("request").value, provider, model};
  agentStatus(provider === "ollama" ? `Waiting for ${model}… No changes have been saved.` : "Preparing command preview…");
  syncControls();
  try {
    const plan = await api(propertiesPath + "/" + snapshot.id + "/preview", {
      prompt: snapshot.prompt, selection: snapshot.selection, revision: snapshot.revision,
      provider, ...(provider === "ollama" ? {model} : {}),
    }, controller.signal);
    if (generation !== agentGeneration || project?.id !== snapshot.id ||
        project?.revision !== snapshot.revision || selected !== snapshot.selection ||
        $("request").value !== snapshot.prompt || $("agent-provider").value !== provider ||
        (provider === "ollama" && $("agent-model").value !== model)) return;
    if (plan.revision !== project.revision) throw new Error("This property changed. Reopen it and preview again.");
    showPlan(plan);
    const hasEdits = (plan.commands || [plan.command]).filter(Boolean).length > 0;
    agentStatus(hasEdits ? "Preview ready. Review every change before Apply. Nothing has been saved." : "Response ready. No scene changes proposed.");
    status(hasEdits ? "Review the proposed edit." : "No changes were saved.");
  } catch (error) {
    if (generation !== agentGeneration) return;
    agentStatus(error.message, true);
    status(error.message, true);
  } finally {
    if (generation === agentGeneration) {
      agentRequest = null;
      syncControls();
    }
  }
}

try {
  viewport = new Viewport($("view"), id => {
    if (!busy && project && !baselineView) select(id);
  });
} catch (error) {
  console.error(error);
  viewportError = "3D viewport unavailable. You can still edit the property in the inspector.";
}

async function api(path, data, signal) {
  const options = data === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data),
  };
  if (signal) options.signal = signal;
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "Palladio could not complete the request.");
  return value;
}

function status(message, error = false) {
  $("status").textContent = [message, viewportError].filter(Boolean).join(" · ");
  $("status").dataset.error = String(error || Boolean(viewportError));
}

function syncControls() {
  designTools.sync(busy || !project || baselineView);
  $("new-property").disabled = busy || !catalog;
  $("empty-create").disabled = busy || !catalog;
  $("duplicate").disabled = busy || !project;
  $("create-submit").disabled = busy || (!duplicating && $("landscape-source").value === "online" && !sites.preview);
  $("design-view").disabled = busy || !project;
  $("baseline-view").disabled = busy || !project;
  $("frame").disabled = !viewport || !project;
  $("restore").disabled = busy || !project || baselineView || project.history.length < 2;
  for (const control of document.querySelectorAll(
    "#prompt-form input, #prompt-form button, #apply-plan, #discard-plan, #environment input, #environment select, " +
    "#environment button, #add-kind, #add-element, #element input, #element select, #element button, #history, #assembly-form input, #assembly-form select, #assembly-form button",
  )) control.disabled = busy || !project || baselineView;
  for (const button of $("properties").querySelectorAll("button")) button.disabled = busy;
  $("agent-provider").disabled = busy;
  $("agent-model").disabled = busy || Boolean(modelRequest) || !installedModels.length;
  $("refresh-models").disabled = busy || Boolean(modelRequest);
  $("preview-request").disabled = busy || Boolean(agentRequest) || !project || baselineView ||
    ($("agent-provider").value === "ollama" && (Boolean(modelRequest) || !$("agent-model").value));
  $("cancel-request").hidden = !agentRequest;
  $("cancel-request").disabled = !agentRequest;
  $("apply-plan").disabled = busy || !project || baselineView || !pending ||
    !(pending.commands || [pending.command]).filter(Boolean).length;
}

async function run(operation, onError = error => status(error.message, true)) {
  if (busy) return;
  cancelAgentRequest("Request cancelled because the workspace changed. Nothing was saved.");
  busy = true;
  syncControls();
  try {
    await operation();
  } catch (error) {
    onError(error);
  } finally {
    busy = false;
    syncControls();
  }
}

function option(value, label = value) {
  return new Option(label, value);
}

function displayList(node, items, current, onChoose, empty) {
  node.replaceChildren();
  if (!items.length) {
    const message = document.createElement("p");
    message.className = "muted";
    message.textContent = empty;
    node.append(message);
    return;
  }
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "list-item";
    button.textContent = item.name;
    button.setAttribute("aria-current", String(item.id === current));
    button.addEventListener("click", () => onChoose(item.id));
    node.append(button);
  }
}

async function loadLibrary() {
  const projects = await api(propertiesPath);
  displayList($("properties"), projects, project?.id, openProject, "No saved properties.");
  return projects;
}

function showPlan(plan = null) {
  pending = plan;
  $("proposal").hidden = !plan;
  $("proposal-text").textContent = plan?.summary || "";
  $("proposal-source").textContent = plan ? (plan.provider === "ollama"
    ? `Local model: ${plan.model} · Suggested response · Revision ${plan.revision} · Not saved`
    : `${plan.provider === "tools" ? "Manual tools" : "Built-in commands"} · Revision ${plan.revision} · Not saved`) : "";
  $("proposal-commands-detail").open = false;
  $("proposal-commands").textContent = plan ? JSON.stringify(plan.commands || (plan.command ? [plan.command] : []), null, 2) : "";
  $("proposal-changes").replaceChildren();
  for (const change of [...(plan?.changes || []), ...(plan?.warnings || [])]) {
    const item = document.createElement("li");
    item.textContent = change;
    $("proposal-changes").append(item);
  }
  updateViewport();
  syncControls();
}

function updateViewport() {
  const hasEdits = pending && (pending.commands || [pending.command]).filter(Boolean).length > 0;
  const previewElements = !baselineView && hasEdits && pending?.elements;
  const previewScene = !baselineView && hasEdits && pending?.scene;
  $("assembly-preview-badge").hidden = !previewElements && !previewScene;
  if (!project || !catalog) return;
  const viewProject = previewScene ? {...project, scene: previewScene} : previewElements ? {
    ...project, scene: {...project.scene, elements: [...project.scene.elements, ...previewElements]},
  } : project;
  $("rain").classList.toggle("active", (baselineView ? project.baseline : viewProject.scene).environment.weather === "rain");
  viewport?.update(viewProject, baselineView, catalog.materials, selected);
}

function discardOnEdit() {
  const wasRequest = cancelAgentRequest("Request cancelled because the input changed. Preview again when ready.");
  if (!pending && !wasRequest) return;
  showPlan();
  status("Preview cleared. Preview again to review your changes.");
}

function assemblyDefaults() {
  const template = catalog?.assemblies?.[$("assembly-kind").value];
  if (!template) return;
  $("assembly-name").value = template.label;
  $("assembly-material").value = template.material;
  for (const dimension of ["width", "height", "depth"]) {
    const input = $("assembly-" + dimension);
    input.value = template[dimension];
    input.min = template.limits[dimension][0];
    input.max = template.limits[dimension][1];
  }
}

function select(id) {
  if (selected !== id) {
    cancelAgentRequest("Request cancelled because the selection changed.");
    showPlan();
  }
  selected = id;
  render();
}

function showProject(next, resetView = false) {
  cancelAgentRequest("Request cancelled because the property changed.");
  if (resetView) {
    selected = null;
    baselineView = false;
    viewport?.reset();
    $("request").value = "";
  }
  project = next;
  if (!project.scene.elements.some(item => item.id === selected)) selected = null;
  history.replaceState(null, "", "#" + project.id);
  showPlan();
  render();
  status("Saved locally · Revision " + project.revision);
}

function openProject(id) {
  if (busy) return;
  showPlan();
  return run(async () => {
    showProject(await api(propertiesPath + "/" + id), true);
    await loadLibrary();
  });
}

function displayTime(hour) {
  const minutes = Math.min(1439, Math.round(hour * 60));
  return [Math.floor(minutes / 60), minutes % 60].map(value => String(value).padStart(2, "0")).join(":");
}

function render() {
  $("empty-state").hidden = Boolean(project);
  $("view").hidden = !project || !viewport;
  $("inspector").hidden = !project;
  $("project-title").textContent = project?.name || "Property library";
  $("design-view").setAttribute("aria-pressed", String(!baselineView));
  $("baseline-view").setAttribute("aria-pressed", String(baselineView));
  if (!project) {
    displayList($("scene-items"), [], null, select, "Open a property to see its elements.");
    syncControls();
    return;
  }
  const scene = baselineView ? project.baseline : project.scene;
  const items = baselineView ? [] : scene.elements;
  displayList($("scene-items"), items, selected, select, baselineView ? "Original landscape" : "No elements.");
  const {source, terrain} = project.baseline;
  $("site-profile").textContent = source.kind === "elevation grid"
    ? `${source.dataset} · ${terrain.spacing} m grid · ${source.latitude}, ${source.longitude}`
    : source.profile + " · Procedural site";
  $("site-profile").title = source.kind === "elevation grid"
    ? `Centre elevation ${source.origin_elevation_m} m · ${source.vertical_datum}`
    : "";
  $("saved-source").hidden = source.kind !== "elevation grid";
  const acquisition = source.acquisition;
  $("saved-source-text").textContent = source.kind === "elevation grid"
    ? `${source.dataset}. Centre ${source.latitude}, ${source.longitude}. ${terrain.spacing} m sample spacing. ` +
      `Centre elevation ${source.origin_elevation_m.toFixed(2)} m. ${source.vertical_datum}.` +
      (acquisition ? ` Downloaded ${acquisition.retrieved_utc}. ${acquisition.sampling}. ` +
        `Source tiles: ${acquisition.source_tiles.map(tile => tile.name).join(", ")}. ` +
        `Source pixel sizes (service-reported values): ${[...new Set(acquisition.source_tiles.map(tile => tile.resolution))].join(", ")}.` : "")
    : "";
  $("weather").value = scene.environment.weather;
  $("hour").value = displayTime(scene.environment.hour);
  $("rain").classList.toggle("active", scene.environment.weather === "rain");
  designTools.render(project, selected);
  const target = items.find(item => item.id === selected);
  $("element").hidden = !target;
  if (target) {
    $("element-name").value = target.name;
    $("material").value = target.material;
    $("yaw").value = target.yaw;
    for (const [index, axis] of ["x", "y", "z"].entries()) {
      $("position-" + axis).value = target.position[index];
      $("size-" + axis).value = target.size[index];
    }
  }
  const earlier = project.history.slice(1);
  $("history").replaceChildren(...(earlier.length
    ? earlier.map(entry => option(entry.number, entry.number + " · " + entry.label))
    : [option("", "No earlier revisions")]));
  updateViewport();
  syncControls();
}

function previewTool(commands) {
  return run(async () => {
    showPlan();
    const id = project.id, revision = project.revision;
    const plan = await api(propertiesPath + '/' + id + '/command-preview', {revision, commands});
    if (project.id !== id || project.revision !== plan.revision) throw new Error('Property changed. Preview again.');
    showPlan(plan);
    status('Review the proposed changes and placement notes, then Apply or Discard.');
  });
}

function commit(payload, revision = project.revision) {
  return run(async () => {
    showPlan();
    const next = await api(propertiesPath + "/" + project.id + "/edit", {revision, ...payload});
    const previousCount = project.scene.elements.length;
    if (payload.commands?.length === 1 && payload.commands[0].action === "add" &&
        next.scene.elements.length > previousCount) {
      selected = next.scene.elements.at(-1).id;
    }
    showProject(next);
    await loadLibrary();
  });
}

function updateLandscapeFields() {
  sites.invalidate();
  const mode = $("landscape-source").value;
  const procedural = duplicating || mode === "procedural";
  $("landscape-brief-field").hidden = !procedural;
  $("landscape-brief").required = !duplicating && procedural;
  $("starter-field").hidden = !procedural;
  $("elevation-file-field").hidden = mode !== "elevation";
  $("elevation-file").required = !duplicating && mode === "elevation";
  $("real-site-fields").hidden = mode !== "online";
  for (const id of ["site-latitude", "site-longitude", "site-span"]) {
    $(id).disabled = duplicating || mode !== "online";
  }
}

$("landscape-source").addEventListener("change", updateLandscapeFields);

async function newPropertyData(name) {
  if ($("landscape-source").value === "online") return sites.propertyData(name);
  if ($("landscape-source").value !== "elevation") {
    return {name, brief: $("landscape-brief").value, starter: $("starter").checked};
  }
  const file = $("elevation-file").files[0];
  if (!file || file.size > 950_000) {
    throw new Error("Choose an elevation JSON file smaller than 950 KB.");
  }
  let elevation;
  try {
    elevation = JSON.parse(await file.text());
  } catch {
    throw new Error("The elevation file must contain valid JSON.");
  }
  if (!elevation || typeof elevation !== "object" || Array.isArray(elevation)) {
    throw new Error("The elevation file must contain a JSON object.");
  }
  return {name, elevation};
}

function showDialog(duplicate = false) {
  cancelAgentRequest("Request cancelled because the property changed.");
  showPlan();
  duplicating = duplicate;
  $("property-form").reset();
  $("dialog-error").hidden = true;
  $("dialog-title").textContent = duplicate ? "Duplicate property" : "New property";
  $("create-submit").textContent = duplicate ? "Duplicate property" : "Create property";
  $("new-fields").hidden = duplicate;
  updateLandscapeFields();
  $("site-matches-field").hidden = true;
  if (duplicate) $("property-name").value = (project.name.slice(0, 93) + " copy");
  $("property-dialog").showModal();
  $("property-name").focus();
}

$("new-property").addEventListener("click", () => showDialog());
$("empty-create").addEventListener("click", () => showDialog());
$("duplicate").addEventListener("click", () => showDialog(true));
$("close-dialog").addEventListener("click", () => $("property-dialog").close());
$("property-form").addEventListener("submit", event => {
  event.preventDefault();
  run(async () => {
    const name = $("property-name").value;
    const next = duplicating
      ? await api(propertiesPath + "/" + project.id + "/duplicate", {name})
      : await api(propertiesPath, await newPropertyData(name));
    $("property-dialog").close();
    showProject(next, true);
    await loadLibrary();
  }, error => {
    $("dialog-error").textContent = error.message;
    $("dialog-error").hidden = false;
    status(error.message, true);
  });
});

for (const [id, mode] of [["design-view", false], ["baseline-view", true]]) {
  $(id).addEventListener("click", () => {
    if (baselineView === mode) return;
    cancelAgentRequest("Request cancelled because the view changed.");
    baselineView = mode;
    showPlan();
    render();
  });
}
$("frame").addEventListener("click", () => viewport?.reset());
$("environment").addEventListener("submit", event => {
  event.preventDefault();
  const [hours, minutes] = $("hour").value.split(":").map(Number);
  commit({commands: [{action: "environment", environment: {
    weather: $("weather").value, hour: hours + minutes / 60,
  }}]});
});
$("add-element").addEventListener("click", () => {
  const kind = $("add-kind").value;
  commit({commands: [{action: "add", element: {
    kind, name: kind[0].toUpperCase() + kind.slice(1),
    material: kind === "glazing" ? "glass" : "concrete",
    position: [0, 0, 0], size: catalog.elements[kind],
  }}]});
});
$("element").addEventListener("submit", event => {
  event.preventDefault();
  const coordinates = prefix => ["x", "y", "z"].map(axis => $(prefix + "-" + axis).valueAsNumber);
  commit({commands: [{action: "update", id: selected, element: {
    name: $("element-name").value, material: $("material").value,
    position: coordinates("position"), size: coordinates("size"), yaw: $("yaw").valueAsNumber,
  }}]});
});
$("remove-element").addEventListener("click", () => {
  commit({commands: [{action: "remove", id: selected}]});
});
$("restore").addEventListener("click", () => {
  const restore = Number($("history").value);
  if (restore !== project.revision) commit({restore});
});
$("prompt-form").addEventListener("submit", event => {
  event.preventDefault();
  previewRequest();
});
$("agent-provider").addEventListener("change", changeAgent);
$("agent-model").addEventListener("change", () => {
  cancelAgentRequest();
  showPlan();
  rememberedModel($("agent-model").value);
  agentStatus($("agent-model").value ? `Selected ${$("agent-model").value}. Preview to review its proposed changes.` : "Choose an installed model.");
});
$("refresh-models").addEventListener("click", refreshModels);
$("cancel-request").addEventListener("click", () => {
  cancelAgentRequest("Request cancelled locally. Its reply will be ignored; Ollama may finish inference in the background.");
  showPlan();
  status("Request cancelled. No changes were saved.");
});
$("request").addEventListener("input", discardOnEdit);
for (const form of ["assembly-form", "environment", "element"]) {
  $(form).addEventListener("input", discardOnEdit);
  $(form).addEventListener("change", discardOnEdit);
}
$("assembly-kind").addEventListener("change", () => {
  discardOnEdit();
  assemblyDefaults();
});
$("assembly-form").addEventListener("submit", event => {
  event.preventDefault();
  run(async () => {
    showPlan();
    const assembly = {
      kind: $("assembly-kind").value,
      name: $("assembly-name").value,
      material: $("assembly-material").value,
      width: $("assembly-width").valueAsNumber,
      height: $("assembly-height").valueAsNumber,
      depth: $("assembly-depth").valueAsNumber,
      position: ["x", "y", "z"].map(axis => $("assembly-" + axis).valueAsNumber),
      yaw: $("assembly-yaw").valueAsNumber,
    };
    const plan = await api(propertiesPath + "/" + project.id + "/assembly-preview", {assembly});
    if (plan.revision !== project.revision) throw new Error("This property changed. Reopen it and preview again.");
    showPlan(plan);
    status("Assembly preview only. Apply to save, or Discard to return to the saved design.");
  });
});
$("apply-plan").addEventListener("click", () => {
  if (pending) commit({commands: pending.commands || [pending.command]}, pending.revision);
});
$("discard-plan").addEventListener("click", () => {
  cancelAgentRequest();
  showPlan();
  status("Proposal discarded.");
});

render();
run(async () => {
  catalog = await api("/api/catalog");
  try {
    const agent = await api("/api/agent");
    if (Array.isArray(agent.providers)) {
      $("agent-provider").replaceChildren(...agent.providers.map(item => option(item.id, item.label)));
    }
    $("agent-provider").value = "rules";
    agentEndpoint = agent.endpoint || agentEndpoint;
  } catch (error) { agentStatus("Agent settings unavailable. Built-in commands remain available. " + error.message, true); }
  $("weather").replaceChildren(...catalog.weather.map(value => option(value)));
  $("material").replaceChildren(...Object.keys(catalog.materials).map(value => option(value)));
  $("add-kind").replaceChildren(...Object.keys(catalog.elements).map(value => option(value)));
  $("assembly-kind").replaceChildren(...Object.entries(catalog.assemblies).map(([key, value]) => option(key, value.label)));
  $("assembly-material").replaceChildren(...Object.keys(catalog.materials).map(value => option(value)));
  assemblyDefaults();
  const projects = await loadLibrary();
  const remembered = projects.find(item => "#" + item.id === location.hash);
  const first = remembered || projects[0];
  if (first) {
    showProject(await api(propertiesPath + "/" + first.id), true);
    await loadLibrary();
  } else {
    status("Create a property to begin.");
  }
});
