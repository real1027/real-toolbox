// =============================================================================
// MT Toolbox entry page client script.
//
// What this file does, end to end:
//   1. Fetches manifest.json (the same file the Launcher reads) and renders
//      one card per tool into #tool-grid (see loadTools/toolCard).
//   2. Each launchable card's button is a plain <a href="real-toolbox://...">
//      link - clicking it is what triggers Windows to hand off to the
//      Launcher (see launcher/launcher.py's module docstring for the other
//      half of this handshake). This script has NO way to know whether that
//      handoff actually worked; wireLaunchFeedback() is a best-effort UX
//      patch for that fundamental limitation, not a real status readout.
//   3. Manages the "first time here? install the Launcher" reminder card,
//      remembering (via localStorage, since a static page cannot query the
//      local filesystem for whether the Launcher is actually installed) that
//      the user has already dealt with it.
//
// There is no build step - this is loaded directly via <script src="assets/
// app.js"> in index.html, so it must run in every evergreen browser as-is.
// =============================================================================

// Icon path data for every icon a tool's manifest entry can reference via its
// "icon" field (see cardArt), plus two fixed UI icons (play/external-link)
// used on every launch/external-link button regardless of which tool it's
// for. Sourced from Lucide (https://lucide.dev, ISC license) and inlined
// here as raw SVG path/shape markup (not full <svg> tags) so svgIcon() can
// wrap them at whatever size/stroke-width a given call site needs, without
// fetching anything from a CDN at runtime (this page has no external script/
// asset dependencies by design - it's a fully static GitHub Pages site).
//
// "repeat" and "wrench" are currently unused by any tool in manifest.json
// (repeat was SFIS Emulator's very first icon choice, swapped out for
// "database" because it read too much like a refresh/reload button sitting
// next to a launch button) but are kept here since they're cheap to keep
// around and a future tool may want them.
const ICONS = {
  camera: '<path d="M13.997 4a2 2 0 0 1 1.76 1.05l.486.9A2 2 0 0 0 18.003 7H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1.997a2 2 0 0 0 1.759-1.048l.489-.904A2 2 0 0 1 10.004 4z" /><circle cx="12" cy="13" r="3" />',
  'file-diff': '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" /><path d="M9 10h6" /><path d="M12 13V7" /><path d="M9 17h6" />',
  box: '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" /><path d="m3.3 7 8.7 5 8.7-5" /><path d="M12 22V12" />',
  repeat: '<path d="m17 2 4 4-4 4" /><path d="M3 11v-1a4 4 0 0 1 4-4h14" /><path d="m7 22-4-4 4-4" /><path d="M21 13v1a4 4 0 0 1-4 4H3" />',
  play: '<path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z" />',
  'external-link': '<path d="M15 3h6v6" /><path d="M10 14 21 3" /><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />',
  wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z" />',
  database: '<ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5V19A9 3 0 0 0 21 19V5" /><path d="M3 12A9 3 0 0 0 21 12" />',
  radio: '<path d="M16.247 7.761a6 6 0 0 1 0 8.478" /><path d="M19.075 4.933a10 10 0 0 1 0 14.134" /><path d="M4.925 19.067a10 10 0 0 1 0-14.134" /><path d="M7.753 16.239a6 6 0 0 1 0-8.478" /><circle cx="12" cy="12" r="2" />',
  'clipboard-check': '<rect width="8" height="4" x="8" y="2" rx="1" ry="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="m9 14 2 2 4-4" />',
  search: '<path d="m21 21-4.34-4.34" /><circle cx="11" cy="11" r="8" />',
};

// localStorage key used to remember "the user already dismissed the setup
// card" (see setupLauncherReminder). Prefixed with mt_toolbox_ to avoid ever
// colliding with an unrelated key some other script on the same origin might
// set (not a real risk on GitHub Pages, but costs nothing to be specific).
const LAUNCHER_SETUP_KEY = 'mt_toolbox_launcher_ready';

// Builds a standalone <svg>...</svg> string for one of the path/shape
// fragments in ICONS. Returns null (not a broken empty string) for an
// unrecognized name so callers (see cardArt) can distinguish "no icon
// available, fall back to something else" from "render an empty icon".
function svgIcon(name, size = 16, strokeWidth = 2) {
  const inner = ICONS[name];
  if (!inner) return null;
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
}

// Pre-rendered once at load time (not per-card) since every launch button and
// every external-link button on the whole page uses the exact same icon at
// the exact same size - no need to regenerate identical markup per card.
const LAUNCH_ICON = svgIcon('play', 14);
const EXTERNAL_ICON = svgIcon('external-link', 14);

// Manual HTML-escaping (as opposed to e.g. always using textContent) because
// several places below need to mix escaped user/manifest-provided text with
// trusted markup (icons, tags) inside a single innerHTML template string -
// escaping only the interpolated values, right at the point they're
// interpolated, is what keeps that safe. Every tool name/description/label
// that ultimately comes from manifest.json passes through this before being
// placed in innerHTML, since manifest.json is data (maintained by whoever is
// onboarding a tool - see CONTRIBUTING.md) rather than trusted script, and
// should be treated the same as any other untrusted string for XSS purposes.
function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// The little icon/initials tile at the top of each card. Prefers the
// manifest's "icon" field (a Lucide icon name - see ICONS) when present and
// recognized; falls back to the tool's own first two characters (upper-
// cased) as plain text when a tool has no icon set, or names one that isn't
// in ICONS yet (e.g. a typo, or a brand-new icon not added to this file yet)
// - a card should never end up looking visually broken just because of a
// missing/unrecognized icon name.
function cardArt(tool) {
  const icon = tool.icon && svgIcon(tool.icon, 28, 1.75);
  if (icon) return icon;
  return `<span>${escapeHtml(tool.name.trim().slice(0, 2).toUpperCase())}</span>`;
}

// Shared markup for any button that launches something via the Launcher
// (used both for a normal single-exe tool's one button, and for each of a
// multi-exe tool's several sub-tool buttons - see footerContent). `href` is
// expected to already be a fully-formed real-toolbox://launch/... URI with
// its path segments percent-encoded by the caller (encodeURIComponent), NOT
// escaped again here - escapeHtml is only applied to `label`, the
// human-readable button text, which is untrusted manifest data.
function launchButton(href, label) {
  return `<a class="launch-btn" href="${href}">${LAUNCH_ICON}${escapeHtml(label)}</a>`;
}

// Builds the bottom row of a tool card - what it looks like depends on which
// "kind" of manifest entry this tool is, checked in this priority order:
//
//   1. status === 'coming_soon' - a placeholder entry reserved for a tool
//      that's been announced but doesn't have a real download/URL yet (see
//      manifest.json's schema notes in README.md). Renders a disabled-
//      looking button (a <span>, not a real <a> link - there is nothing
//      to link to) plus a small "即將推出" tag, and is NOT clickable.
//
//   2. type === 'link' - a manifest entry that is just a bookmark to an
//      external web system (e.g. the equipment rental system, or the Error
//      Code search system), not something the Launcher downloads/runs at
//      all. Renders a plain external link that opens in a new tab - no
//      real-toolbox:// URI is involved for this case whatsoever.
//
//   3. Array of sub_tools present and non-empty - a multi-exe tool (e.g.
//      LED AOI's CAM/ROI/LED). Renders one launchButton() per sub-tool,
//      each linking to real-toolbox://launch/<tool-id>/<sub-id> (see
//      launcher.py's parse_launch_path/resolve_exe_name for how the
//      Launcher interprets that extra path segment), stacked in a column
//      (see .sub-tool-buttons in style.css) rather than the single button
//      the simple case below gets.
//
//   4. Otherwise (the common case) - a single normal tool with one exe.
//      Renders exactly one launchButton() linking to
//      real-toolbox://launch/<tool-id> with no trailing segment.
//
// tool.id and tool.sub.id are run through encodeURIComponent (URL-encoding,
// distinct from escapeHtml/HTML-encoding) since they become a path segment
// inside an href attribute, not just text content.
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

// Builds one <article class="card"> DOM element for a single manifest.json
// tool entry - called once per entry by loadTools(). Uses innerHTML (rather
// than building child elements one at a time) for simplicity, since every
// piece of untrusted text going into it has already been escaped by
// cardArt/escapeHtml/footerContent before reaching this template.
//
// The "is-coming-soon" class (which style.css uses to dim the whole card and
// disable its hover-lift animation) is applied here at the card level, not
// just on the button, so the entire card visually reads as "not available
// yet" rather than only the button looking different.
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

// Manages the "第一次使用？先安裝 Launcher" <details> card at the top of the
// page, and its counterpart "工具啟動教學" reopen button in the top bar.
//
// Why this exists at all: a static web page has no way to ask the local
// filesystem/registry whether the Launcher is actually installed on this
// machine (browsers deliberately don't expose that kind of local-system
// introspection to web pages, for obvious security reasons - see
// launcher/launcher.py's module docstring for the broader custom-protocol
// design this is part of). So instead of a real "is it installed?" check,
// this is an honest, user-controlled substitute: a "✓ 已完成安裝，不再顯示"
// button inside the card lets the user tell the page "I've already dealt
// with this", remembered via localStorage (scoped to this browser, this
// origin - a different browser/machine/profile will see the card again,
// which is the correct behavior since Launcher installation is genuinely
// per-machine).
//
// State transitions:
//   - Not yet dismissed (no localStorage key, or a previous "reopen" call
//     cleared it): the setup <details> card is visible (and starts expanded,
//     via the `open` attribute already present on the element in index.html)
//     and the "工具啟動教學" reopen button in the top bar is hidden - no
//     point offering to reopen a card that's already open.
//   - Dismissed: the setup card is hidden entirely and the reopen button
//     appears in its place, in case the user (or someone helping them on a
//     new machine) needs the instructions again later.
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

// The mascot image (assets/mascot.png, a personal touch in the page's
// signature corner) is allowed to simply not exist / fail to load without
// breaking the page layout or showing a browser's default broken-image
// icon - if it 404s or otherwise errors, this just hides the <img> entirely
// rather than leaving a broken-image placeholder visible.
function hideMascotIfMissing() {
  const mascot = document.querySelector('.mascot');
  mascot.addEventListener('error', () => { mascot.hidden = true; });
}

// Generous timeout: first-ever run of a freshly built/downloaded exe
// (the Launcher itself, or a newly downloaded tool) commonly gets held up
// several seconds - sometimes upwards of a minute, in practice - by Windows
// Defender/antivirus scanning before anything visible happens at all. A
// short timeout would revert the "啟動中…" button back to normal while a
// legitimate launch is still quietly in progress in the background,
// making it look like the click did nothing even though it's actually
// still working. This was originally 6 seconds, then raised to 15, then to
// 60 after real-world testing kept showing the antivirus-scan delay could
// exceed both of those.
const LAUNCH_FEEDBACK_TIMEOUT_MS = 60000;

// Wires up the button-level "啟動中…" feedback for every real-toolbox://
// launch link on the page (delegated via a single click listener on the
// whole #tool-grid container, so this works uniformly for both a simple
// tool's one button and a multi-exe tool's several sub-tool buttons,
// without needing to attach a listener to each button individually as
// cards are (re)rendered).
//
// *** Read this before changing anything here: a real-toolbox:// link gives
// this script ZERO feedback about what actually happened after the click.
// The browser either hands the URI straight to the registered Launcher, or
// shows its own native "open this link with...?" confirmation prompt first
// - either way, control leaves the web page's JavaScript entirely and
// nothing ever calls back into it to report success, failure, or even that
// a Launcher is installed at all. Everything below is therefore a UX
// approximation built from indirect signals, not a real status readout: ***
//
//   - On click: swap the button's label to "啟動中…", add the "is-loading"
//     class (which style.css uses to set `pointer-events: none` - this is
//     what actually stops a second click from doing anything while the
//     button is in this state, not any JavaScript-side click-guard logic)
//     and start a LAUNCH_FEEDBACK_TIMEOUT_MS timer.
//   - If the browser tab loses focus (the `visibilitychange` event fires
//     with `document.hidden === true`) before that timer elapses, treat
//     that as a reasonably strong signal that *something* did open (the
//     OS's own confirmation prompt taking focus, or the Launcher/tool
//     itself becoming the foreground window) and snap back to normal
//     immediately, rather than making the user wait out the full timeout
//     for no reason. This is a heuristic, not proof - e.g. a user
//     alt-tabbing away for an unrelated reason during that window would
//     trigger the same code path with no real launch having happened - but
//     it's a reasonable, low-cost improvement over always waiting the full
//     timeout.
//   - Otherwise, after LAUNCH_FEEDBACK_TIMEOUT_MS with no visibility change
//     observed, just revert anyway. There is no way to distinguish "it
//     quietly succeeded and nothing ever needed focus" from "it silently
//     failed" from inside this script, so reverting either way (rather
//     than, say, showing a permanent error) is the least-wrong default -
//     the button becomes clickable again either way, which is what matters
//     most for a user who wants to retry.
//
// Only one button can be "in flight" from this script's point of view at a
// time (`activeBtn`) - clicking a second launch button while the first is
// still in its "啟動中…" state immediately reverts the first one before
// starting the new one's timer, since this is purely a display concern (the
// actual duplicate-launch protection lives server-side, in the Launcher's
// acquire_launch_lock - see launcher.py) and there's no reason to leave a
// stale "啟動中…" showing on a button the user has moved on from.
function wireLaunchFeedback() {
  const grid = document.getElementById('tool-grid');
  let activeBtn = null;
  let revertTimer = null;

  function revert() {
    if (!activeBtn) return;
    activeBtn.classList.remove('is-loading');
    activeBtn.innerHTML = activeBtn.dataset.originalLabel;
    activeBtn = null;
  }

  grid.addEventListener('click', (e) => {
    // e.target.closest handles clicks landing on the icon <svg>/<path>
    // inside the button, not just the <a> element itself - closest() walks
    // up from whatever was actually clicked to find the nearest ancestor
    // (or self) matching the selector.
    const btn = e.target.closest('a.launch-btn');
    // Guard against: (a) the click not being on a launch button at all
    // (e.g. clicking the card's description text), and (b) it being an
    // external "前往" link (type: 'link' tools) or a disabled coming-soon
    // <span> (which isn't even an <a>, so this check would already exclude
    // it, but the href check is what excludes real external links, which
    // ARE <a> tags with class="launch-btn" too).
    if (!btn || !(btn.getAttribute('href') || '').startsWith('real-toolbox://')) return;

    // If some other button was already mid-"啟動中…" (e.g. the user clicked
    // one tool, then immediately clicked a different one before the first
    // reverted), clean that up first so only ever one button shows the
    // loading state at a time.
    revert();
    btn.dataset.originalLabel = btn.innerHTML;
    btn.classList.add('is-loading');
    btn.innerHTML = `${LAUNCH_ICON}啟動中…`;
    activeBtn = btn;
    clearTimeout(revertTimer);
    revertTimer = setTimeout(revert, LAUNCH_FEEDBACK_TIMEOUT_MS);
  });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden && activeBtn) {
      clearTimeout(revertTimer);
      revert();
    }
  });
}

// Fetches manifest.json and renders one card per entry into #tool-grid.
// `cache: 'no-store'` is deliberate: this page is meant to always reflect
// whatever is currently live in the repo (tools get added/updated
// independently of the page's own HTML/CSS/JS being redeployed), so a
// stale cached manifest.json - even one cached for just a few minutes by a
// normal browser HTTP cache - would show outdated data. GitHub Pages serves
// static files with caching headers that would otherwise allow exactly that
// kind of staleness.
//
// An empty tools array and a hard network/parse failure are handled as two
// visibly different cases: the former shows the page's built-in
// "目前還沒有工具" placeholder (a legitimate, if unlikely, empty state); the
// latter replaces the whole grid with the actual error message, since "the
// manifest failed to load" is a very different situation from "the manifest
// loaded fine and is just empty" and a user/maintainer debugging a broken
// deployment needs to see which one it is.
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

// Run everything at script-load time - this file is loaded with a plain
// <script src="assets/app.js"> at the very end of <body> (see index.html),
// after all the elements these functions reference already exist in the
// DOM, so there's no need to wait for a DOMContentLoaded event.
setupLauncherReminder();
hideMascotIfMissing();
wireLaunchFeedback();
loadTools();
