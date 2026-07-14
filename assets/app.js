const CATEGORY_LABEL = {
  internal: '公司內部',
  personal: '個人專案',
};

const LAUNCH_ICON = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const EXTERNAL_ICON = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3zM5 5h5V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-5h-2v5H5z"/></svg>';

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
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
  const initials = tool.name.trim().slice(0, 2).toUpperCase();
  const card = document.createElement('article');
  card.className = 'card' + (tool.status === 'coming_soon' ? ' is-coming-soon' : '');
  card.dataset.category = tool.category;
  card.innerHTML = `
    <div class="card-art" aria-hidden="true"><span>${escapeHtml(initials)}</span></div>
    <div class="card-body">
      <div class="card-top">
        <h3 class="card-title">${escapeHtml(tool.name)}</h3>
        <span class="badge badge-${escapeHtml(tool.category)}">${escapeHtml(CATEGORY_LABEL[tool.category] || tool.category)}</span>
      </div>
      ${tool.description ? `<p class="card-desc">${escapeHtml(tool.description)}</p>` : ''}
      <div class="card-footer">
        ${footerContent(tool)}
      </div>
    </div>
  `;
  return card;
}

function applyFilter(filter) {
  document.querySelectorAll('.card').forEach((card) => {
    card.hidden = filter !== 'all' && card.dataset.category !== filter;
  });
  const visible = document.querySelectorAll('.card:not([hidden])').length;
  document.getElementById('empty-state').hidden = visible !== 0;
}

function setupTabs() {
  const tabs = document.getElementById('tabs');
  tabs.addEventListener('click', (e) => {
    const btn = e.target.closest('.tab');
    if (!btn) return;
    tabs.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t === btn));
    applyFilter(btn.dataset.filter);
  });
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

setupTabs();
loadTools();
