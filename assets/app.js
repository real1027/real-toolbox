const CATEGORY_LABEL = {
  internal: '公司內部',
  personal: '個人專案',
};

function toolCard(tool) {
  const initials = tool.name.trim().slice(0, 2).toUpperCase();
  const card = document.createElement('article');
  card.className = 'card';
  card.dataset.category = tool.category;
  card.innerHTML = `
    <div class="card-art" aria-hidden="true"><span>${initials}</span></div>
    <div class="card-body">
      <div class="card-top">
        <h3 class="card-title">${tool.name}</h3>
        <span class="badge badge-${tool.category}">${CATEGORY_LABEL[tool.category] || tool.category}</span>
      </div>
      ${tool.description ? `<p class="card-desc">${tool.description}</p>` : ''}
      <div class="card-footer">
        <span class="version-tag">v${tool.latest_version}</span>
        <a class="launch-btn" href="real-toolbox://launch/${encodeURIComponent(tool.id)}">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          啟動
        </a>
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
    grid.innerHTML = `<p class="empty-state">無法載入工具清單：${err.message}</p>`;
  }
}

setupTabs();
loadTools();
