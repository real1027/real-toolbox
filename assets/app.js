async function loadTools() {
  const res = await fetch('manifest.json', { cache: 'no-store' });
  const { tools } = await res.json();

  const internalList = document.getElementById('internal-list');
  const personalList = document.getElementById('personal-list');

  for (const tool of tools) {
    const li = document.createElement('li');
    li.className = 'tool-item';
    li.innerHTML = `
      <a class="tool-link" href="real-toolbox://launch/${encodeURIComponent(tool.id)}">
        <span class="tool-name">${tool.name}</span>
        <span class="tool-version">v${tool.latest_version}</span>
      </a>
      ${tool.description ? `<p class="tool-desc">${tool.description}</p>` : ''}
    `;
    (tool.category === 'internal' ? internalList : personalList).appendChild(li);
  }
}

loadTools();
