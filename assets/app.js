// Icon paths from Lucide (https://lucide.dev), ISC License.
const ICONS = {
  camera: '<path d="M13.997 4a2 2 0 0 1 1.76 1.05l.486.9A2 2 0 0 0 18.003 7H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1.997a2 2 0 0 0 1.759-1.048l.489-.904A2 2 0 0 1 10.004 4z" /><circle cx="12" cy="13" r="3" />',
  'file-diff': '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" /><path d="M9 10h6" /><path d="M12 13V7" /><path d="M9 17h6" />',
  box: '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" /><path d="m3.3 7 8.7 5 8.7-5" /><path d="M12 22V12" />',
  repeat: '<path d="m17 2 4 4-4 4" /><path d="M3 11v-1a4 4 0 0 1 4-4h14" /><path d="m7 22-4-4 4-4" /><path d="M21 13v1a4 4 0 0 1-4 4H3" />',
  play: '<path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z" />',
  'external-link': '<path d="M15 3h6v6" /><path d="M10 14 21 3" /><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />',
  wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z" />',
};

const LAUNCHER_SETUP_KEY = 'mt_toolbox_launcher_ready';

function svgIcon(name, size = 16, strokeWidth = 2) {
  const inner = ICONS[name];
  if (!inner) return null;
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
}

const LAUNCH_ICON = svgIcon('play', 14);
const EXTERNAL_ICON = svgIcon('external-link', 14);

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function cardArt(tool) {
  const icon = tool.icon && svgIcon(tool.icon, 28, 1.75);
  if (icon) return icon;
  return `<span>${escapeHtml(tool.name.trim().slice(0, 2).toUpperCase())}</span>`;
}

function launchButton(href, label) {
  return `<a class="launch-btn" href="${href}">${LAUNCH_ICON}${escapeHtml(label)}</a>`;
}

function footerContent(tool) {
  if (tool.status === 'coming_soon') {
    return `
      <span class="coming-soon-tag">即將推出</span>
      <span class="launch-btn is-disabled">${LAUNCH_ICON}啟動</span>
    `;
  }

  if (tool.type === 'link') {
    return `
      <span class="version-tag">外部連結</span>
      <a class="launch-btn" target="_blank" rel="noopener" href="${escapeHtml(tool.url)}">${EXTERNAL_ICON}前往</a>
    `;
  }

  if (Array.isArray(tool.sub_tools) && tool.sub_tools.length) {
    const buttons = tool.sub_tools
      .map((sub) => launchButton(`real-toolbox://launch/${encodeURIComponent(tool.id)}/${encodeURIComponent(sub.id)}`, sub.name))
      .join('');
    return `<span class="version-tag">v${escapeHtml(tool.latest_version)}</span><div class="sub-tool-buttons">${buttons}</div>`;
  }

  return `
    <span class="version-tag">v${escapeHtml(tool.latest_version)}</span>
    ${launchButton(`real-toolbox://launch/${encodeURIComponent(tool.id)}`, '啟動')}
  `;
}

function toolCard(tool) {
  const card = document.createElement('article');
  card.className = 'card' + (tool.status === 'coming_soon' ? ' is-coming-soon' : '');
  card.innerHTML = `
    <div class="card-art" aria-hidden="true">${cardArt(tool)}</div>
    <div class="card-body">
      <div class="card-top">
        <h3 class="card-title">${escapeHtml(tool.name)}</h3>
      </div>
      ${tool.description ? `<p class="card-desc">${escapeHtml(tool.description)}</p>` : ''}
      <div class="card-footer">
        ${footerContent(tool)}
      </div>
    </div>
  `;
  return card;
}

function setupLauncherReminder() {
  const card = document.getElementById('setup-card');
  const reopenBtn = document.getElementById('setup-reopen');
  const dismissBtn = document.getElementById('dismiss-setup');

  const isDismissed = localStorage.getItem(LAUNCHER_SETUP_KEY) === '1';
  card.hidden = isDismissed;
  reopenBtn.hidden = !isDismissed;

  dismissBtn.addEventListener('click', () => {
    localStorage.setItem(LAUNCHER_SETUP_KEY, '1');
    card.hidden = true;
    reopenBtn.hidden = false;
  });

  reopenBtn.addEventListener('click', () => {
    localStorage.removeItem(LAUNCHER_SETUP_KEY);
    card.hidden = false;
    card.open = true;
    reopenBtn.hidden = true;
  });
}

function hideMascotIfMissing() {
  const mascot = document.querySelector('.mascot');
  mascot.addEventListener('error', () => { mascot.hidden = true; });
}

async function loadTools() {
  const grid = document.getElementById('tool-grid');
  try {
    const res = await fetch('manifest.json', { cache: 'no-store' });
    const { tools } = await res.json();
    if (!tools.length) {
      document.getElementById('empty-state').hidden = false;
      return;
    }
    for (const tool of tools) {
      grid.appendChild(toolCard(tool));
    }
  } catch (err) {
    grid.innerHTML = `<p class="empty-state">無法載入工具清單：${escapeHtml(err.message)}</p>`;
  }
}

setupLauncherReminder();
hideMascotIfMissing();
loadTools();
