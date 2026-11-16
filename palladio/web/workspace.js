// Presentation-only workspace state. Scene edits still use the existing review flow.
export function setupWorkspace(viewport) {
  const find = id => document.getElementById(id);
  const inspector = find('inspector');
  const groups = {
    'saved-source':'site', 'reference-board':'finish', 'group-panel':'edit',
    'terrain-tools':'site', 'water-panel':'site', 'foundation-panel':'build',
    'wall-tools':'build', 'presentation-panel':'present', 'palette-panel':'finish',
    'finish-panel':'finish',
  };
  const headings = {'Environment':'site','Assembly builder':'build','Elements':'edit','History':'edit'};
  const summaries = {'Layout and measurements':'edit','Planted landscape':'site',
    'Reusable assets':'build','Design jobs':'build'};
  let current = 'edit';
  for (const child of inspector.children) {
    if (child.tagName === 'H2') current = headings[child.textContent.trim()] || current;
    const summary = child.tagName === 'DETAILS' ? child.querySelector('summary')?.textContent.trim() : '';
    child.dataset.workspace = groups[child.id] || summaries[summary] || current;
    if (child.tagName === 'HR') child.classList.add('workspace-divider');
  }
  const tabs = Array.from(document.querySelectorAll('[data-workspace-tab]'));
  function activate(name, focus = false) {
    if (!tabs.some(tab => tab.dataset.workspaceTab === name)) name = 'edit';
    for (const child of inspector.children) child.classList.toggle('workspace-inactive', child.dataset.workspace !== name);
    for (const tab of tabs) {
      const active = tab.dataset.workspaceTab === name;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    }
    inspector.setAttribute('aria-labelledby', 'workspace-tab-' + name);
    try { localStorage.setItem('palladio.workspace', name); } catch {}
  }
  for (const [index, tab] of tabs.entries()) {
    tab.addEventListener('click', () => activate(tab.dataset.workspaceTab));
    tab.addEventListener('keydown', event => {
      const direction = {ArrowRight:1,ArrowDown:1,ArrowLeft:-1,ArrowUp:-1}[event.key];
      if (!direction && !['Home','End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + direction + tabs.length) % tabs.length;
      activate(tabs[next].dataset.workspaceTab, true);
    });
  }
  let remembered = 'edit';
  try { remembered = localStorage.getItem('palladio.workspace') || remembered; } catch {}
  activate(remembered);
  find('scene-items').addEventListener('click', () => activate('edit'));
  find('focus-workspace').addEventListener('click', () => {
    const focus = document.body.classList.toggle('focus-workspace');
    find('focus-workspace').setAttribute('aria-pressed', String(focus));
    find('focus-workspace').textContent = focus ? 'Show panels' : 'Focus view';
  });
  find('render-quality').addEventListener('change', () => {
    viewport?.setQuality(find('render-quality').value);
    find('render-status').textContent = viewport?.qualityDescription() || 'Viewport unavailable';
    try { localStorage.setItem('palladio.render.quality', find('render-quality').value); } catch {}
  });
  try {
    const quality = localStorage.getItem('palladio.render.quality');
    if (['draft','studio','presentation'].includes(quality)) find('render-quality').value = quality;
  } catch {}
  viewport?.setQuality(find('render-quality').value);
  find('render-status').textContent = viewport?.qualityDescription() || 'Viewport unavailable';
}
