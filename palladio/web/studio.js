import {Viewport} from "./viewport.js";

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

try {
  viewport = new Viewport($("view"), id => {
    if (!busy && project && !baselineView) select(id);
  });
} catch (error) {
  console.error(error);
  viewportError = "3D viewport unavailable. You can still edit the property in the inspector.";
}

async function api(path, data) {
  const options = data === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data),
  };
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
  $("new-property").disabled = busy || !catalog;
  $("empty-create").disabled = busy || !catalog;
  $("duplicate").disabled = busy || !project;
  $("create-submit").disabled = busy;
  $("design-view").disabled = busy || !project;
  $("baseline-view").disabled = busy || !project;
  $("frame").disabled = !viewport || !project;
  $("restore").disabled = busy || !project || baselineView || project.history.length < 2;
  for (const control of document.querySelectorAll(
    "#prompt-form input, #prompt-form button, #apply-plan, #discard-plan, #environment input, #environment select, " +
    "#environment button, #add-kind, #add-element, #element input, #element select, #element button, #history, #assembly-form input, #assembly-form select, #assembly-form button",
  )) control.disabled = busy || !project || baselineView;
  for (const button of $("properties").querySelectorAll("button")) button.disabled = busy;
}

async function run(operation, onError = error => status(error.message, true)) {
  if (busy) return;
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
  updateViewport();
}

function updateViewport() {
  const previewElements = !baselineView && pending?.elements;
  $("assembly-preview-badge").hidden = !previewElements;
  if (!project || !catalog) return;
  const viewProject = previewElements ? {
    ...project, scene: {...project.scene, elements: [...project.scene.elements, ...previewElements]},
  } : project;
  viewport?.update(viewProject, baselineView, catalog.materials, selected);
}

function discardOnEdit() {
  if (!pending) return;
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
  if (selected !== id) showPlan();
  selected = id;
  render();
}

function showProject(next, resetView = false) {
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
  $("site-profile").textContent = project.baseline.source.profile + " · Procedural site";
  $("weather").value = scene.environment.weather;
  $("hour").value = displayTime(scene.environment.hour);
  $("rain").classList.toggle("active", scene.environment.weather === "rain");
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

function showDialog(duplicate = false) {
  showPlan();
  duplicating = duplicate;
  $("property-form").reset();
  $("dialog-error").hidden = true;
  $("dialog-title").textContent = duplicate ? "Duplicate property" : "New property";
  $("create-submit").textContent = duplicate ? "Duplicate property" : "Create property";
  $("new-fields").hidden = duplicate;
  $("landscape-brief").required = !duplicate;
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
      : await api(propertiesPath, {name, brief: $("landscape-brief").value, starter: $("starter").checked});
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
  run(async () => {
    showPlan();
    const plan = await api(propertiesPath + "/" + project.id + "/preview", {
      prompt: $("request").value, selection: selected,
    });
    if (plan.revision !== project.revision) throw new Error("This property changed. Reopen it and preview again.");
    showPlan(plan);
    status("Review the proposed edit.");
  });
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
  if (pending) commit({commands: [pending.command]}, pending.revision);
});
$("discard-plan").addEventListener("click", () => {
  showPlan();
  status("Proposal discarded.");
});

render();
run(async () => {
  catalog = await api("/api/catalog");
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
