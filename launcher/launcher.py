"""MT Toolbox Launcher (repo/protocol name: real-toolbox).

=== What this program is ===
This is the small local program that makes the "click a link on a web page,
a desktop tool starts running" experience possible. Browsers cannot execute
arbitrary local .exe files for security reasons, so the web page instead
links to a custom URI scheme, real-toolbox://launch/<tool-id>, and Windows
is taught (via this program's --register step) to hand off any click on
such a link to this program. From there, this program:

  1. Parses which tool (and optionally which sub-tool) was requested.
  2. Downloads manifest.json (the shared catalogue of all tools) from the
     live MT Toolbox web page.
  3. Figures out whether the tool is already installed and up to date on
     this machine (see "Version + fingerprint checking" below).
  4. If not, downloads the tool's packaged zip, extracts it, and remembers
     what it did.
  5. Finds the requested .exe inside the extracted files and runs it.

Crucially, this file contains **no logic specific to any individual tool**.
Every tool-specific detail (display name, where to download it, which exe
to run, whether it has multiple sub-programs, etc.) lives in manifest.json,
not here. Adding a new tool to MT Toolbox never requires touching this file.

=== Why it runs windowless ===
Early versions of this Launcher were built with a console window (PyInstaller
--console), so every single invocation - even a successful, instant one -
flashed a black console window on screen. That looked broken and alarmed
users. The Launcher is now built with --windowed (no console at all). Because
there's no console to print status/errors to, this file uses two different
channels for talking to the user instead:
  - ctypes MessageBoxW (see show_message) for anything that should be seen
    immediately and requires no ongoing UI - e.g. "registration succeeded"
    or "something went wrong".
  - A small tkinter progress window (see ProgressWindow) shown only while an
    actual download/extract is happening, since that can take a visible
    amount of time and a blank screen makes it look hung.

=== Version + fingerprint checking (avoiding unnecessary re-downloads) ===
A tool should only be re-downloaded when it has actually changed, not on
every single launch. Two independent signals are compared against what was
recorded the last time this tool was successfully installed (see
installed_record / STATE_FILE):

  1. Version number (see resolve_live_version): rather than trusting a
     manually-typed "latest_version" field in manifest.json (which a tool
     author could easily forget to update, or which could simply be stale
     because nobody has told the MT Toolbox maintainer about a new release),
     the Launcher asks the tool's own GitLab Release "permalink" URL what
     tag it is currently pointing at, live, on every launch. This makes
     the system mostly self-healing: as long as a tool author keeps cutting
     normal GitLab Releases, version tracking "just works" with no manifest
     edits required after the tool's initial onboarding.

  2. Content fingerprint (see fetch_download_fingerprint): version numbers
     alone have one blind spot - a tool author could re-upload a corrected
     zip under the *same* release/tag (forgetting to bump the version). The
     Launcher additionally does a lightweight HEAD request against the
     actual download URL and remembers the response's ETag/Content-Length.
     If those differ from what was recorded last time, even though the
     version string is unchanged, the Launcher treats it as "changed" and
     re-downloads anyway. This is a safety net, not the primary mechanism -
     tool authors are still asked (see CONTRIBUTING.md / onboarding.html) to
     bump their version tag on every real change.

Both checks are best-effort: if the network call behind either one fails
(offline, internal network unreachable, host doesn't support HEAD, etc.),
the Launcher falls back to whatever it can still determine rather than
blocking the whole launch on a diagnostic nicety.

=== Guarding against a user re-clicking the launch button ===
Because the web page gets no callback from a real-toolbox:// link (see the
page's assets/app.js for the page-side half of this), a slow first-time
download with no on-screen change can look "stuck", tempting someone to
click the launch button again. See acquire_launch_lock: a short-lived lock
file per tool (or per tool+sub-tool) makes a second invocation, that arrives
while the first is still mid-flight, back off immediately and silently
instead of racing the first one (which could otherwise corrupt a half-written
extraction or spawn the target program twice).

=== Working offline (e.g. on a factory production line with no network) ===
Real deployment reality: some machines running this Launcher are on a
production line and are sometimes genuinely offline. See load_manifest's
docstring for the full mechanism, but in short: every successful manifest
fetch is cached to disk (MANIFEST_CACHE_FILE), and a failed fetch falls back
to that cache instead of failing outright. Combined with resolve_live_version
and fetch_download_fingerprint already being best-effort (they simply return
None, not raise, when their network call fails), this means: a tool that is
ALREADY installed and unchanged can still be launched with zero network
connectivity at all. A tool that needs a fresh download/update genuinely
cannot be fetched offline (see launch()'s friendlier error message for this
specific case) - there is no way around that without the download itself
being available somewhere offline, which is out of scope here. The one hard
requirement offline support doesn't remove: a machine's very first-ever use
of MT Toolbox still needs to be online at least once, since there is no way
to know what tools even exist before ever fetching the manifest.

=== Keeping the Launcher itself up to date (self-update) ===
Nothing about the version/fingerprint checking above updates the Launcher
program itself - it only ever manages the tools it launches. Without a
separate mechanism, everyone's already-downloaded, already-registered copy
of this exe would silently keep running whatever version they first
installed, forever, even after this file changes and a new build is
uploaded to the same GitHub Release. See the "Self-update" section further
down (around LAUNCHER_VERSION/maybe_self_update/apply_update) for the fix:
the Launcher applies the same "ask the host's Release system what's
actually current" trick to itself (via GitHub's releases/latest redirect,
GitHub's equivalent of the GitLab permalink trick used for tools) and, when
it finds itself out of date, downloads the new exe and swaps itself out on
disk automatically - fully silent, no user action required, and designed so
that a failure at any step (network, download, or the file-swap itself)
simply results in trying again on a later launch rather than breaking
anything. This was an explicit design choice after asking the user how
aggressive they wanted this (fully automatic vs. a manual "please update"
notice) - they chose fully automatic.
"""

import ctypes
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request
import winreg
import zipfile
from pathlib import Path

# Bump this, and cut a new GitHub Release tag in the form "launcher-vX.Y.Z"
# with the freshly-built exe attached, every time launcher.py meaningfully
# changes - see the "Self-update" section further down for how this constant
# gets compared against GitHub's actual latest release tag. Defined here at
# the very top (rather than down in that section) specifically so
# show_message can use it in every message box's title by default (see
# below) - otherwise there was previously NO way for a user to ever find out
# what version of the Launcher they were running at all, since nothing
# printed it anywhere on its own.
LAUNCHER_VERSION = "1.2.0"

# --- Windows message-box helpers -------------------------------------------
# There is no console (see module docstring), so these MB_* constants pick
# which icon ctypes.windll.user32.MessageBoxW shows: an "i" info icon for
# routine confirmations, a red "x" for anything that went wrong.
MB_ICONINFORMATION = 0x40
MB_ICONERROR = 0x10

# Crash-diagnostic log only - this is NOT a running trace of every step (that
# was tried once during development and ripped back out; it added noise for
# no benefit once the Launcher was working). It exists purely so that if a
# user reports "it just showed an error and I don't remember what it said",
# there is still a file on disk with the exact traceback, since there is no
# console the error could otherwise have been read from.
DEBUG_LOG = Path(os.environ.get("TEMP", str(Path.home()))) / "real-toolbox-debug.log"


def dbg(msg):
    """Append a timestamped line to DEBUG_LOG. Swallows any failure to write
    (e.g. a locked-down TEMP directory) - a broken diagnostic log must never
    itself become the reason the Launcher fails to run."""
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.time():.3f} {msg}\n")
    except OSError:
        pass


def show_message(text, icon=MB_ICONINFORMATION, title=f"MT Toolbox Launcher v{LAUNCHER_VERSION}"):
    """Native Windows message box. This blocks until the user clicks OK -
    that's fine for --register/--set-install-dir (the user is actively
    waiting), and for the top-level error handler in main() (there's nothing
    more useful to do than tell the user what broke and stop).

    The default title always includes LAUNCHER_VERSION - this is the ONE
    place a user can passively see what version of the Launcher they're
    running, without needing to know a --version flag exists at all: every
    message box this program ever shows (register confirmation,
    set-install-dir confirmation, any error) carries it in the title bar for
    free. See the module-level --version handling in dispatch() for the
    explicit, on-demand way to check it too.
    """
    ctypes.windll.user32.MessageBoxW(0, text, title, icon)


# --- Where things get installed ---------------------------------------------
# CONFIG_FILE deliberately always lives under the per-user profile
# (%LOCALAPPDATA%), which is guaranteed to exist and be writable on any
# Windows account, REGARDLESS of what install directory is actually
# configured. This matters because the config file's whole job is to let
# someone redirect DEFAULT_APP_DIR to a different drive/path - if the config
# file itself lived inside the (possibly-overridden, possibly-missing) app
# dir, a machine without a D: drive could never recover: it would have
# nowhere to even write "please stop using D:".
CONFIG_FILE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "real-toolbox" / "config.json"

# This fixed path is this deployment's chosen default (an Arcadyan-internal
# convention, not anything the Launcher assumes generically). Any machine
# that needs a different location can override it - see resolve_app_dir().
DEFAULT_APP_DIR = Path(r"D:\___ARC_MT_TOOLS___")


def resolve_app_dir():
    """Decide where downloaded tools/state should live on this machine.

    Priority order (first one found wins):
      1. REAL_TOOLBOX_INSTALL_DIR environment variable - mainly for local
         development/testing without touching the real install location.
      2. "install_dir" recorded in CONFIG_FILE, written by
         `real-toolbox-launcher.exe --set-install-dir <path>` - the
         supported way for an end user to relocate things (e.g. onto a
         drive with more free space).
      3. DEFAULT_APP_DIR, if neither of the above is set.

    Any error reading/parsing CONFIG_FILE (missing file, corrupt JSON) is
    swallowed and treated the same as "no override configured" - a broken
    config file must never prevent the Launcher from running at all, it
    should just fall back to the default.
    """
    env_override = os.environ.get("REAL_TOOLBOX_INSTALL_DIR")
    if env_override:
        return Path(env_override)
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if cfg.get("install_dir"):
                return Path(cfg["install_dir"])
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_APP_DIR


# Resolved once, at import time, and reused for the whole run - this must
# happen after resolve_app_dir/CONFIG_FILE/DEFAULT_APP_DIR are defined above.
APP_DIR = resolve_app_dir()
# Every tool gets its own subfolder here, and within that, one subfolder per
# version string (see launch() below) - e.g.
#   D:\___ARC_MT_TOOLS___\tools\sfisemulator_arcadyan\1.3.1\SfisSimulator.exe
# Keeping the version in the path means switching versions never requires
# deciding whether it's "safe" to overwrite existing files in place; the old
# version's folder is simply deleted (see launch()) and a fresh one created.
TOOLS_DIR = APP_DIR / "tools"
# Tracks, per tool id, the version + fingerprint that was last successfully
# installed - see installed_record()/save_state() and the "Version +
# fingerprint checking" section of the module docstring.
STATE_FILE = APP_DIR / "installed.json"

# The manifest is the single shared source of truth for every tool's
# metadata; it's the same file the web page itself fetches to render the
# tool list, so the Launcher and the page can never disagree about what
# tools exist or where to get them.
DEFAULT_MANIFEST_URL = "https://real1027.github.io/real-toolbox/manifest.json"
# Overridable for local development/testing (e.g. pointing at a manifest.json
# still sitting on disk, not yet pushed to GitHub Pages) without needing to
# edit this file.
MANIFEST_URL = os.environ.get("REAL_TOOLBOX_MANIFEST_URL", DEFAULT_MANIFEST_URL)

# A copy of the last successfully-fetched manifest.json, kept purely so a
# machine with no internet at all (a common real scenario on a factory
# production line - see load_manifest's docstring) can still launch a tool
# it already has installed, instead of failing at the very first step just
# because it couldn't re-fetch the catalogue it already knows about.
MANIFEST_CACHE_FILE = APP_DIR / "manifest_cache.json"


def load_manifest(manifest_url):
    """Fetch and parse manifest.json, with an offline fallback.

    Supports both a real http(s) URL (the normal case) and a plain local
    file path (so REAL_TOOLBOX_MANIFEST_URL can point at a file on disk
    during development, with no separate code path to keep in sync - the
    cache mechanism below only applies to the http(s) case).

    Every successful live fetch overwrites MANIFEST_CACHE_FILE with exactly
    what was received. If the live fetch fails for any network reason
    (no internet at all, or this specific host unreachable), this falls
    back to that cached copy instead of failing outright - this is what
    lets an already-installed tool still launch on a factory floor machine
    with no network connectivity, as long as this machine has successfully
    loaded the manifest at least once before while it did have connectivity.

    Only raises (SystemExit, with a message meant to be read by an end
    user - see main()'s top-level handler) when BOTH the live fetch and the
    cache are unavailable: there is no way to know what tools even exist
    without ever having fetched the manifest at least once, so a machine's
    very first use of MT Toolbox genuinely does require being online.
    """
    if manifest_url.startswith("http://") or manifest_url.startswith("https://"):
        try:
            with urllib.request.urlopen(manifest_url, timeout=10) as resp:
                raw = resp.read()
            manifest = json.loads(raw)
            try:
                APP_DIR.mkdir(parents=True, exist_ok=True)
                MANIFEST_CACHE_FILE.write_bytes(raw)
            except OSError:
                # Caching is a nicety for next time, not required for this
                # launch to succeed - a read-only/full disk must not turn a
                # perfectly good live fetch into a failure.
                pass
            return manifest
        except OSError:
            if MANIFEST_CACHE_FILE.exists():
                return json.loads(MANIFEST_CACHE_FILE.read_text(encoding="utf-8"))
            raise SystemExit(
                "無法連線取得工具清單，而且這台機器上沒有先前成功快取過的清單可用。\n\n"
                "請確認網路連線；如果這是這台機器第一次使用 MT Toolbox，"
                "離線環境下沒辦法完成第一次啟動（至少需要成功連線一次）。"
            )
    with open(manifest_url, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state():
    """Read installed.json (see STATE_FILE) - the record of what's already
    on this machine. Returns an empty dict (i.e. "nothing installed yet")
    if the file doesn't exist, which is the normal case on a brand new
    machine/install directory."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def installed_record(state, tool_id):
    """Normalize one tool's entry from installed.json to the current
    {"version": ..., "fingerprint": ...} shape, regardless of which Launcher
    version wrote it.

    Older Launcher builds (before the fingerprint safety-net feature was
    added) recorded just a plain version string per tool, e.g.
    {"sfisemulator_arcadyan": "1.3.1"}. Reading that back with this function
    produces {"version": "1.3.1", "fingerprint": None} - the missing
    fingerprint will simply be treated as "different from whatever we fetch
    live this run" the first time launch() compares them, which triggers
    exactly one redownload to backfill it. No explicit migration step is
    needed; old and new format entries are simply both handled here.
    """
    entry = state.get(tool_id)
    if isinstance(entry, dict):
        return entry
    return {"version": entry, "fingerprint": None}


def save_state(state):
    """Persist installed.json. Recreates APP_DIR first in case it doesn't
    exist yet (e.g. very first successful install on this machine)."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def find_tool(manifest, tool_id):
    """Look up one tool's manifest entry by id. Raising SystemExit here (as
    opposed to returning None) is deliberate: every caller of find_tool
    immediately needs a valid tool to proceed, so there is no useful "not
    found, but let's continue anyway" path - and SystemExit's message ends
    up shown to the user via main()'s top-level error handler."""
    for tool in manifest.get("tools", []):
        if tool["id"] == tool_id:
            return tool
    raise SystemExit(f"在工具清單裡找不到 '{tool_id}'")


class ProgressWindow:
    """A small always-on-top window shown ONLY while an actual download/
    extract is happening - i.e. a cold install, or a version/fingerprint
    change (see launch()). The overwhelmingly common case, "already
    installed and unchanged, just launch it", never creates this window at
    all - most launches should feel instant, and popping up a window for
    that case would be pure visual noise.

    The window is intentionally simple: a centered label describing the
    current phase ("正在下載.../正在解壓...") and an indeterminate (not a
    real percentage) progress bar, since accurately reporting percent-done
    would require knowing the total download size up front and dealing with
    hosts that don't report Content-Length - not worth the complexity for a
    "something is happening, please wait" indicator.
    """

    def __init__(self, tool_name):
        # Imported lazily (inside __init__, not at module top) so that the
        # rest of this file - and every other real-toolbox:// invocation
        # that never needs a progress window, i.e. every launch where the
        # tool is already up to date - never pays the cost of importing
        # tkinter at all.
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.root = tk.Tk()
        self.root.title("MT Toolbox")

        # Centered manually via winfo_screenwidth/height rather than the
        # Tcl convenience proc `tk::PlaceWindow . center`: that proc is not
        # guaranteed to be preloaded in every Tcl/Tk runtime bundled by
        # PyInstaller, and calling an unavailable Tcl proc raises a TclError
        # that (before this was fixed) surfaced as a silent-looking hang -
        # the resulting error message box just sat there blocked waiting for
        # a click nobody was there to give during automated testing. Manual
        # geometry math has no such external dependency.
        width, height = 360, 120
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(False, False)
        # Keeps the window above the target tool's own window as it starts
        # up, so the progress window doesn't get lost behind other apps.
        self.root.attributes("-topmost", True)

        self.label = tk.Label(self.root, text=f"正在準備 {tool_name} ...", pady=12, font=("Segoe UI", 10))
        self.label.pack()

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=300, mode="indeterminate")
        self.progress.pack(pady=6)
        self.progress.start(12)

        # Tkinter only actually draws/redraws in response to its own event
        # loop running (mainloop()) or an explicit update() call. This
        # program never calls mainloop() (that would block waiting for user
        # interaction, which this window never needs) - instead, pump()
        # calls update() periodically during the download so the window
        # stays responsive and visibly alive instead of appearing frozen.
        self.root.update()

    def set_status(self, text):
        """Change the label text (e.g. switching from "下載中" to "解壓中")
        and immediately repaint."""
        self.label.config(text=text)
        self.root.update()

    def pump(self):
        """Give tkinter a chance to process its event queue and repaint.
        Called periodically from download_and_extract's reporthook so the
        window doesn't appear to freeze during a long-running blocking
        network call."""
        self.root.update()

    def close(self):
        self.progress.stop()
        self.root.destroy()


class NullProgress:
    """No-op stand-in with the same interface as ProgressWindow, used when
    the real progress window couldn't be created (see make_progress_window).
    This means every caller of make_progress_window can treat its return
    value uniformly - call set_status/pump/close on it without needing an
    `if progress is not None` check scattered everywhere - regardless of
    whether tkinter actually worked on this particular machine/session.
    A download should still proceed silently rather than the whole launch
    failing just because a nice-to-have UI window couldn't be shown (e.g.
    some restricted/remote desktop sessions don't have a normal display
    surface for a new top-level window)."""

    def set_status(self, text):
        pass

    def pump(self):
        pass

    def close(self):
        pass


def make_progress_window(tool_name):
    """Try to create a real ProgressWindow; fall back to the silent
    NullProgress if that fails for any reason at all. The failure is still
    logged to DEBUG_LOG (not shown to the user - a progress window is a
    nicety, its absence shouldn't itself pop up an alarming error dialog)."""
    try:
        return ProgressWindow(tool_name)
    except Exception:
        dbg(f"ProgressWindow failed:\n{traceback.format_exc()}")
        return NullProgress()


def download_and_extract(tool, version_dir, progress=None):
    """Download tool["download_url"] to a temp zip next to version_dir, then
    extract it into version_dir and delete the zip.

    version_dir is TOOLS_DIR/<tool_id>/<version> - see launch() for how
    <version> is determined. Extraction targets that exact folder directly
    (not some intermediate staging area) because launch() has already
    deleted any previous version of this tool's folder before calling this
    function - there is nothing pre-existing at version_dir to worry about
    clobbering.

    The `report` inner function is urllib's reporthook - it fires
    periodically during urlretrieve's download loop purely so `progress`
    (a ProgressWindow or NullProgress) gets a chance to repaint; it doesn't
    track real byte-by-byte progress into the UI, see ProgressWindow's
    docstring for why an indeterminate bar was chosen over a real
    percentage.
    """
    version_dir.parent.mkdir(parents=True, exist_ok=True)
    zip_path = version_dir.parent / f"{tool['id']}.zip"

    def report(block_num, block_size, total_size):
        if progress:
            progress.pump()

    if progress:
        progress.set_status(f"正在下載 {tool['name']} ...")
    urllib.request.urlretrieve(tool["download_url"], zip_path, reporthook=report)

    if progress:
        progress.set_status(f"正在解壓 {tool['name']} ...")
        progress.pump()
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(version_dir)
    zip_path.unlink(missing_ok=True)


def find_exe(root_dir, exe_name):
    """Recursively search root_dir for a file named exe_name and return the
    first match. Recursive on purpose: a tool's zip is allowed to have any
    internal folder structure at all (see CONTRIBUTING.md) - the only rule
    tool authors must follow is that the exe filename they report must be
    unique within the zip. This is what makes the Launcher's exe-finding
    logic completely generic across every tool's differing zip layout."""
    for path in root_dir.rglob(exe_name):
        return path
    raise SystemExit(f"解壓後找不到 {exe_name}（資料夾：{root_dir}）")


# The exact substring that marks a download_url as using GitLab's Release
# "permalink" convention (see resolve_live_version's docstring for what that
# means and why it matters). If a tool's download_url doesn't contain this,
# resolve_live_version can't do anything clever with it and returns None.
PERMALINK_MARKER = "/-/releases/permalink/latest/downloads/"

# How long a launch-lock file (see acquire_launch_lock) is considered "still
# valid" - i.e. how long a second real-toolbox:// invocation for the same
# tool will back off and do nothing, assuming an earlier invocation for the
# same tool is still working. Comfortably longer than a normal download
# should take, short enough that a genuinely stuck/crashed first invocation
# doesn't permanently block all future launch attempts of that tool.
LOCK_TTL_SECONDS = 20


def resolve_live_version(download_url):
    """Ask the GitLab release permalink what tag it currently points at,
    instead of trusting a manually-maintained version number.

    Background: manifest.json has a "latest_version" field, but requiring a
    human to keep that field in sync with each tool's actual releases is
    exactly the kind of manual-relay step that goes stale (a tool author
    forgets to mention a new release; the MT Toolbox maintainer is busy;
    etc.) - see CONTRIBUTING.md / onboarding.html for the full reasoning
    given to tool authors.

    The fix exploits a property of the GitLab Release "permalink" URL
    convention this project already asks every tool author to use for
    hosting their download (see CONTRIBUTING.md step 3):

        download_url = ".../-/releases/permalink/latest/downloads/<file>"

    That URL always resolves to whatever the newest Release's attached file
    currently is. Stripping the "/downloads/<file>" suffix gives the
    permalink to the Release *page* itself:

        ".../-/releases/permalink/latest"

    GitLab serves that as an HTTP redirect, and critically, the redirect's
    Location header embeds the actual release tag, e.g.:

        Location: .../-/releases/v1.3.1

    So a plain HEAD request (no need to download or even follow the
    redirect - the tag is already visible in the *first* response's
    Location header) is enough to learn the true current version, live,
    every time a tool is launched. No polling, no webhook, no manifest.json
    edit ever required again after a tool's initial onboarding - as long as
    the tool author keeps cutting normal GitLab Releases.

    A raw http.client connection is used here (rather than the higher-level
    urllib.request, which is used everywhere else in this file) specifically
    because it does NOT auto-follow redirects - this function wants to
    inspect the *first* redirect response's Location header directly, not
    end up at the final downloaded resource.

    Returns None (meaning: caller should fall back to manifest.json's
    latest_version instead) when:
      - download_url doesn't use the permalink convention at all (some
        other hosting scheme entirely - see CONTRIBUTING.md's note on this)
      - the network request fails for any reason (offline, internal-only
        host unreachable from this machine, timeout, etc.)
      - the response unexpectedly has no Location header
    """
    idx = download_url.find(PERMALINK_MARKER)
    if idx == -1:
        return None
    version_url = download_url[:idx] + "/-/releases/permalink/latest"
    parsed = urllib.parse.urlsplit(version_url)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    try:
        conn = conn_cls(parsed.netloc, timeout=6)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        conn.request("HEAD", path)
        resp = conn.getresponse()
        location = resp.getheader("Location")
        conn.close()
    except OSError:
        return None
    if not location:
        return None
    # The tag in the Location header may or may not have a "v" prefix
    # (GitLab just reflects whatever the tool author's actual git tag was,
    # e.g. "v1.3.1"), but manifest.json's convention for latest_version
    # (and the version-string comparisons this file does elsewhere) is
    # WITHOUT the "v" - e.g. "1.3.1". Stripping a leading v/V (only when
    # immediately followed by a digit, so a tag that's genuinely just "v"
    # or starts with a letter-word isn't mangled) keeps both sources
    # directly comparable.
    tag = location.rstrip("/").rsplit("/", 1)[-1]
    if tag[:1] in ("v", "V") and tag[1:2].isdigit():
        tag = tag[1:]
    return tag or None


def fetch_download_fingerprint(download_url, timeout=8):
    """Best-effort HEAD request against the actual download URL, used as a
    safety net alongside (not instead of) resolve_live_version's version
    check - see the module docstring's "Version + fingerprint checking"
    section for the full reasoning.

    In short: version-number comparison alone would miss a tool author
    re-uploading a corrected zip under the exact same release tag (an easy
    mistake to make - forgetting to bump the version for what felt like a
    "small" fix). To catch that case too, this function fingerprints the
    actual file the download_url currently points at:

      - ETag: when the hosting server sets one (GitLab's plain "raw file
        from a git repo" serving does), this is normally a hash-derived
        value that changes whenever the file's content changes - exactly
        the signal wanted.
      - Content-Length: always available as a fallback (e.g. GitLab's
        generic Package Registry endpoint, used by some tools' download
        URLs, does not set an ETag but does report a length). A changed
        file size is a weaker signal than a changed hash (two different
        file versions could coincidentally be the same size), but it's
        still meaningfully better than no check at all, and costs nothing
        extra to also look at.

    Both are combined into one opaque fingerprint string; the caller
    (launch()) just compares this string to what's recorded from the last
    successful install and doesn't need to know or care which header(s)
    actually contributed to it.

    Returns None if the request fails outright, or if the response had
    neither header at all - callers MUST treat None as "couldn't determine,
    don't use this signal this time" and fall back to version-only
    comparison, NOT as "definitely different, force a re-download". Treating
    None as "changed" would force a redownload on every single launch on any
    host that simply doesn't support/answer HEAD requests, which would be
    strictly worse than not having this check at all.
    """
    try:
        req = urllib.request.Request(download_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            etag = resp.getheader("ETag")
            length = resp.getheader("Content-Length")
    except OSError:
        return None
    if not etag and not length:
        return None
    return f"{etag or ''}|{length or ''}"


def acquire_launch_lock(key):
    """Try to claim a short-lived lock for `key` (a tool id, or
    "<tool_id>__<sub_id>" for a sub-tool - see dispatch()), to guard against
    a user re-clicking the "啟動" button on the web page while an earlier
    click for the *same* tool is still mid-download/extract.

    Why this matters: a real-toolbox:// link gives the web page literally no
    feedback about whether the Launcher succeeded (see assets/app.js's
    wireLaunchFeedback for the page-side half of working around this). If a
    first-time download takes a visible number of seconds (slow network, or
    Windows Defender scanning a freshly-downloaded exe - see the setup notes
    on index.html), a user might reasonably assume their first click didn't
    register and click "啟動" again. Without this lock, that second click
    would spawn a second, fully independent launch() call that would race
    the first one: both would try to delete/recreate the same version
    folder, both would download the zip again, and both would eventually
    try to launch the tool - wasteful at best, and capable of corrupting a
    half-extracted folder at worst.

    Implementation: a plain file in APP_DIR/locks/<key>.lock, whose
    modification time records when it was (re-)claimed. If the file exists
    and is younger than LOCK_TTL_SECONDS, this function returns None,
    meaning "someone else already holds this lock, back off" - the caller
    (dispatch()) responds by doing nothing at all rather than proceeding.
    Otherwise (no lock file, or an old/stale one - e.g. a previous run
    crashed without releasing it) this function (re)writes the file with
    the current timestamp and returns its Path, which the caller must pass
    to release_launch_lock() once done (see dispatch()'s try/finally).

    This is intentionally simple (no real cross-process mutex/semaphore) -
    the worst case of a race slipping through (e.g. two invocations landing
    within the same few milliseconds) is some wasted bandwidth/CPU, not data
    corruption of anything outside this tool's own version folder, so a
    lightweight timestamp file is an appropriate amount of engineering for
    the actual risk.
    """
    lock_dir = APP_DIR / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / f"{key}.lock"
    if lock_file.exists():
        age = time.time() - lock_file.stat().st_mtime
        if age < LOCK_TTL_SECONDS:
            return None
    lock_file.write_text(str(time.time()), encoding="utf-8")
    return lock_file


def release_launch_lock(lock_file):
    """Delete the lock file claimed by acquire_launch_lock, if any (a locked-
    out invocation that returned early never acquired one, so lock_file may
    legitimately be None here - see dispatch())."""
    if lock_file:
        lock_file.unlink(missing_ok=True)


# =============================================================================
# Self-update
#
# The Launcher applies the exact same "ask the host's own Release system what
# the real current version is" trick to itself that resolve_live_version
# applies to each tool - except the Launcher's own home is a GitHub Release
# (this repo's launcher-v* tags), not a GitLab one, so this uses GitHub's
# equivalent of the permalink redirect instead (see resolve_latest_launcher_
# version). When a newer tag is found, the Launcher downloads the new exe and
# swaps itself out on disk via a small detached helper step (see apply_update
# and the hidden --apply-update dispatch case) - fully automatic, no user
# action required, matching the "把工具接進來不用管版號" philosophy applied to
# the Launcher itself. Every step here is deliberately best-effort: any
# failure at any point (offline, GitHub unreachable, download interrupted,
# the old exe file still locked when the swap is attempted) is swallowed
# silently and simply tried again on a later launch - self-updating must
# never be the reason a tool fails to start.
# =============================================================================

# (LAUNCHER_VERSION itself is defined near the top of this file, not here -
# see that definition's comment for why: show_message needed it available
# for every message box's default title, which runs long before this
# section of the file is reached.) Unlike the tools' download_url (a fixed
# permalink that always resolves to whatever the newest release is), this
# self-update check deliberately compares actual version *numbers* (this
# constant vs. whatever tag GitHub's "latest release" currently points at)
# rather than just detecting "is there anything newer" some other way, so
# that the constant is always a truthful, at-a-glance answer to "what
# version of the Launcher is this build" during development too.

# GitHub's web UI (not just its REST API) redirects a repo's "latest
# release" URL to that release's tag page - e.g. a HEAD request to
# https://github.com/<owner>/<repo>/releases/latest comes back as a 302
# whose Location header is .../releases/tag/launcher-v1.2.3. This is the
# same technique resolve_live_version uses against GitLab's permalink
# redirect, just GitHub's equivalent of it - no GitHub API token or
# authentication needed since this repo is public. Used only to learn the
# current *version number* for comparison against LAUNCHER_VERSION.
GITHUB_LATEST_RELEASE_URL = "https://github.com/real1027/real-toolbox/releases/latest"

# GitHub also has its own equivalent of GitLab's "permalink to the newest
# asset" trick: releases/latest/download/<asset-name> always resolves to
# whatever the newest release's same-named asset currently is, regardless of
# that release's tag. This fixed URL is used both here (to actually download
# the update - no need to construct a tag-specific URL from whatever
# resolve_latest_launcher_version() returned) and on the web page itself for
# the "下載 Launcher" link (see index.html) - neither ever needs to change
# again when a new Launcher release is cut.
GITHUB_LAUNCHER_ASSET_URL = "https://github.com/real1027/real-toolbox/releases/latest/download/real-toolbox-launcher.exe"

# Don't hit GitHub on literally every single tool launch just to check for a
# Launcher update - that's an extra network round-trip (and extra latency)
# for a check that only ever matters rarely. Throttled to at most once per
# this many seconds, tracked via a timestamp in CONFIG_FILE (see
# resolve_app_dir's docstring for why that specific file's location was
# chosen - same reasoning applies here: it's the one file guaranteed to
# exist and be writable regardless of install-dir configuration).
LAUNCHER_UPDATE_CHECK_INTERVAL_SECONDS = 24 * 60 * 60


def resolve_latest_launcher_version():
    """GitHub equivalent of resolve_live_version - HEAD request against
    GITHUB_LATEST_RELEASE_URL (deliberately NOT following the redirect, same
    reasoning as resolve_live_version: the tag is already visible in the
    first response's Location header, no need to actually fetch the release
    page), parse out the tag, strip the "launcher-v" prefix.

    Returns None (meaning: caller should skip the update check this time)
    on any failure - offline, GitHub unreachable, unexpected response shape,
    etc. - never raises.
    """
    parsed = urllib.parse.urlsplit(GITHUB_LATEST_RELEASE_URL)
    try:
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=6)
        conn.request("HEAD", parsed.path)
        resp = conn.getresponse()
        location = resp.getheader("Location")
        conn.close()
    except OSError:
        return None
    if not location:
        return None
    tag = location.rstrip("/").rsplit("/", 1)[-1]
    prefix = "launcher-v"
    if tag.startswith(prefix):
        return tag[len(prefix):]
    return None


def _read_config():
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def apply_update(new_path, old_path, self_path=None):
    """The hidden second half of a self-update (see maybe_self_update): swap
    a freshly-downloaded exe into place at old_path.

    This runs as a SEPARATE process from the one that downloaded the new
    exe - and critically, it must ALSO be a different exe file than
    old_path itself, not just a different process. A real bug caught during
    testing: an earlier version of this code spawned the helper directly as
    `old_path --apply-update ...`, which fails every single time with a
    permanent Access Denied error, not a transient one - a running Windows
    process holds its own backing exe file open for as long as it executes
    (that's how the OS keeps its code pages available), so a process quite
    literally cannot replace the file it is currently running from,
    regardless of how long it waits. See maybe_self_update, which now copies
    the current exe to a throwaway "updater" path first and launches this
    function from THAT copy - self_path, if provided, is that copy's own
    path, which this function best-effort deletes after a successful swap
    (see the end of this function) since it's no longer needed.

    Retries for up to 10 minutes (300 attempts, 2 seconds apart) replacing
    old_path before giving up. This generous window exists for a real,
    separate reason from the bug above: old_path itself may still be held
    open a while longer by the ORIGINAL Launcher process that triggered
    this update - maybe_self_update() runs as the very last thing
    dispatch() does (see its docstring), but that process doesn't actually
    exit the instant it returns. If the tool being launched failed (e.g.
    "coming_soon", or a real error), main()'s top-level handler still has
    to show a message box and WAIT FOR THE USER TO CLICK IT before the
    process truly exits, which could legitimately take anywhere from a
    second to several minutes depending on when the user gets back to
    their screen. A short retry window loses that race easily - confirmed
    directly during testing. Since this helper is a fully invisible,
    detached background process nobody is waiting on, there is essentially
    no cost to letting it simply keep trying for a long time.

    Deliberately silent either way (no message box) - see the module-level
    comment above this section for why: a user did nothing to trigger this,
    so nothing should interrupt them to announce it either succeeded or
    failed. If it fails every retry, old_path is simply left as-is and the
    next launch's version check will notice the same "outdated" state and
    try the whole update again - this is safe to attempt repeatedly.
    """
    for _ in range(300):
        try:
            os.replace(new_path, old_path)
            dbg(f"self-update applied: {old_path}")
            break
        except OSError:
            time.sleep(2)
    else:
        dbg(f"self-update failed after retries, leaving {old_path} as-is")
        Path(new_path).unlink(missing_ok=True)

    # Best-effort cleanup of the throwaway updater copy this process is
    # itself running from (see maybe_self_update) - a for/else "break" above
    # means the swap succeeded and fell through to here; the retries-
    # exhausted "else" branch above already returned without reaching this.
    # Deleting one's own currently-executing exe file is a different (and
    # more commonly supported) operation than replacing/overwriting it, but
    # still isn't guaranteed to succeed instantly - failing here is fine and
    # silent, it just means an ~11MB leftover file until the next time this
    # happens to get cleaned up, not a functional problem.
    if self_path:
        try:
            Path(self_path).unlink(missing_ok=True)
        except OSError:
            pass


def maybe_self_update():
    """Best-effort: check (throttled) whether a newer Launcher build exists,
    and if so, download it and hand off to a detached apply_update step.

    Deliberately does NOT try to make the CURRENT launch use the new
    version - this call downloads the update and arranges for it to be
    swapped into place shortly after this process exits, so the update
    takes effect starting from the user's NEXT click, not this one. That
    trade-off is what keeps this safe: the tool the user actually asked for
    right now always launches using the current, already-running,
    already-working code, regardless of whether an update was found,
    downloaded, or later successfully applied. See the module-level comment
    above this section for the overall design reasoning.

    Every failure mode - not frozen (a plain `python launcher.py` dev run,
    where "updating a exe" doesn't apply), throttled (checked too recently),
    no update available, network failure, download failure - results in
    this function simply returning without doing anything, never raising.
    This function must never be the reason a tool launch fails.
    """
    if not getattr(sys, "frozen", False):
        return  # nothing meaningful to self-update when just running the .py directly

    cfg = _read_config()
    last_check = cfg.get("last_launcher_update_check", 0)
    if time.time() - last_check < LAUNCHER_UPDATE_CHECK_INTERVAL_SECONDS:
        return
    cfg["last_launcher_update_check"] = time.time()
    _write_config(cfg)

    try:
        latest = resolve_latest_launcher_version()
        if latest is None or latest == LAUNCHER_VERSION:
            return

        exe_path = Path(sys.executable).resolve()
        new_path = exe_path.with_name(exe_path.stem + ".new.exe")
        urllib.request.urlretrieve(GITHUB_LAUNCHER_ASSET_URL, new_path)

        # The swap step MUST run from a DIFFERENT exe file than old_path,
        # not old_path itself - a Windows process holds its own backing exe
        # file open for as long as it's running (that's how the OS keeps
        # its code pages available), so a process launched directly as
        # `old_path --apply-update ...` can never successfully replace
        # old_path: it would be trying to overwrite the very file it's
        # currently executing from, and this failed outright with an
        # Access Denied error in real testing - not merely a slow retry,
        # a permanent failure that no amount of waiting fixes. The fix is
        # to copy the current exe to a throwaway "updater" path first and
        # launch the detached helper from THAT copy instead; it holds a
        # lock on the *copy*, not on old_path, so replacing old_path is
        # unobstructed. apply_update best-effort deletes the updater copy
        # itself after a successful swap (see its docstring).
        updater_path = exe_path.with_name(exe_path.stem + ".updater.exe")
        shutil.copy2(exe_path, updater_path)
        subprocess.Popen(
            [str(updater_path), "--apply-update", str(new_path), str(exe_path), str(updater_path)],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        dbg(f"self-update: found {latest} (current {LAUNCHER_VERSION}), handed off to apply_update")
    except Exception:
        # Truly best-effort - even an unexpected bug in this check must
        # never surface to the user or block the tool they actually asked
        # to launch. Logged for later debugging, not shown.
        dbg(f"self-update check failed:\n{traceback.format_exc()}")


def resolve_exe_name(tool, sub_id):
    """Figure out which exe filename to run for this invocation.

    Most tools have a single entry point - just tool["exe_name"]. Some tools
    (e.g. LED AOI, which bundles CAM/ROI/LED as three independent programs
    sharing one download) instead declare a "sub_tools" list in their
    manifest entry; in that case sub_id (parsed from the
    real-toolbox://launch/<tool-id>/<sub-id> URL - see parse_launch_path)
    picks out which one was actually requested. sub_id is None for a normal
    single-exe tool, since its launch link has no trailing /<sub-id> segment
    at all.
    """
    if sub_id is None:
        return tool["exe_name"]
    for sub in tool.get("sub_tools", []):
        if sub["id"] == sub_id:
            return sub["exe_name"]
    raise SystemExit(f"在 '{tool['id']}' 裡找不到子程式 '{sub_id}'")


def launch(tool_id, sub_id=None):
    """The actual "make the tool run" logic - this is what every real
    real-toolbox://launch/... invocation (as opposed to --register or
    --set-install-dir) ends up calling, via dispatch().

    High-level steps, each covered in more depth by the function/module
    docstrings referenced inline below:
      1. Load the shared manifest and find this tool's entry in it.
      2. Refuse to proceed if the tool is marked "coming_soon" in the
         manifest (a placeholder entry reserved for a tool that isn't
         actually available for download yet - see manifest.json's schema).
      3. Work out which exe to run (resolve_exe_name - handles sub-tools).
      4. Work out the tool's *actual* current version (resolve_live_version)
         and a content fingerprint (fetch_download_fingerprint) - both
         best-effort, see their own docstrings.
      5. Compare those against what's recorded from the last successful
         install of this tool (installed_record) to decide whether a
         (re)download is needed at all.
      6. If so: wipe any previous version of this tool's folder, download
         and extract the new one (with a progress window shown throughout),
         and record the new version+fingerprint.
      7. Either way, find the requested exe inside the (possibly
         newly-extracted, possibly already-existing) version folder and
         start it as a normal independent process - this Launcher process
         does not wait for the tool to exit, and exits itself immediately
         after subprocess.Popen returns.
    """
    manifest = load_manifest(MANIFEST_URL)
    tool = find_tool(manifest, tool_id)
    if tool.get("status") == "coming_soon":
        raise SystemExit(f"'{tool['name']}' 還沒上架，敬請期待。")
    exe_name = resolve_exe_name(tool, sub_id)

    # Prefer the live-resolved version (self-healing - see
    # resolve_live_version's docstring); only fall back to manifest.json's
    # possibly-stale latest_version field when live resolution isn't
    # possible for this tool's download_url or the network call failed.
    version = resolve_live_version(tool.get("download_url", "")) or tool["latest_version"]

    # Best-effort - may be None (see fetch_download_fingerprint's docstring
    # for exactly when/why), which is handled explicitly below rather than
    # treated as "definitely different".
    fingerprint = fetch_download_fingerprint(tool.get("download_url", ""))

    state = load_state()
    record = installed_record(state, tool_id)

    # version_dir bakes the version string directly into the path (see
    # TOOLS_DIR's comment above for why) - e.g.
    #   D:\___ARC_MT_TOOLS___\tools\sfisemulator_arcadyan\1.3.1\
    version_dir = TOOLS_DIR / tool_id / version

    version_changed = record["version"] != version
    # Only treat a fingerprint mismatch as meaningful when a *current*
    # fingerprint was actually obtained this run (fingerprint is not None) -
    # see fetch_download_fingerprint's docstring for why None must NOT be
    # treated as "changed" here (that would force a redownload every single
    # launch on any host that doesn't support HEAD requests).
    fingerprint_changed = fingerprint is not None and record.get("fingerprint") != fingerprint
    # Also redownload if the version folder is simply missing (e.g. deleted
    # by the user, or state.json claims a version that was never actually
    # fully installed) even if the recorded version/fingerprint both
    # "match" - installed.json describing a version that isn't present on
    # disk must never be trusted at face value.
    needs_download = version_changed or fingerprint_changed or not version_dir.exists()

    if needs_download:
        progress = make_progress_window(tool["name"])
        try:
            # Delete any previous version of this tool entirely first -
            # simpler and safer than trying to reconcile old files with new
            # ones in place (e.g. an old version's leftover file that the
            # new version no longer ships would otherwise linger forever).
            tool_dir = TOOLS_DIR / tool_id
            if tool_dir.exists():
                shutil.rmtree(tool_dir, ignore_errors=True)
            try:
                download_and_extract(tool, version_dir, progress=progress)
            except OSError as e:
                # A raw URLError/socket traceback here is technically
                # accurate but unhelpful to an end user - this is the one
                # specific failure worth a plain-language explanation,
                # since it's the direct answer to "why won't it launch": a
                # fresh download/update genuinely requires reaching this
                # tool's download host (typically the internal GitLab),
                # which offline-manifest-caching (see load_manifest) cannot
                # help with - that only covers *already-installed, unchanged*
                # tools.
                raise SystemExit(
                    f"無法下載 '{tool['name']}'：目前連不上下載來源"
                    "（可能是離線，或不在內部網路內）。\n\n"
                    "如果只是要執行已經裝過的版本，離線也可以用；"
                    "但這次判斷需要重新下載或更新，離線/內網外無法完成。"
                ) from e
            # Record what was actually installed, using the *current* version
            # and fingerprint (not necessarily what was in manifest.json),
            # so the next launch's comparison is against ground truth.
            state[tool_id] = {"version": version, "fingerprint": fingerprint}
            save_state(state)
        finally:
            # Always close the progress window, even if the download/extract
            # raised - an exception here propagates up to main()'s top-level
            # handler and shows an error message box; leaving a stray
            # progress window open on top of that would be confusing.
            progress.close()

    exe_path = find_exe(version_dir, exe_name)
    # Popen (not run/call) - this Launcher process is not meant to wait
    # around for the tool to exit; its job ends the moment the tool process
    # has been started.
    subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))


def parse_launch_path(uri):
    """Parse a real-toolbox://launch/<tool-id> or
    real-toolbox://launch/<tool-id>/<sub-id> URI (exactly what's in the
    web page's <a href="..."> links - see assets/app.js's footerContent) into
    (tool_id, sub_id). sub_id is None when the URI has no trailing segment
    (the normal, non-sub-tool case)."""
    match = re.match(r"real-toolbox://launch/([^/?#]+)(?:/([^/?#]+))?", uri)
    if not match:
        raise SystemExit(f"不是合法的 real-toolbox 連結：{uri}")
    return match.group(1), match.group(2)


def set_install_dir(path):
    """Handle `real-toolbox-launcher.exe --set-install-dir <path>`: records
    the chosen path in CONFIG_FILE (see resolve_app_dir for how this gets
    picked back up on the next launch) and confirms via a message box, since
    this is normally run directly by a user from a command prompt and
    expects to see some acknowledgement that it worked.

    Deliberately does NOT move any already-downloaded tools from the old
    location to the new one - that's a bigger, riskier operation (partial
    copies, disk space checks, etc.) than this simple config-writing command
    is meant to take on; the message box tells the user this explicitly so
    it isn't a silent surprise.
    """
    resolved = str(Path(path).resolve())
    cfg = _read_config()
    cfg["install_dir"] = resolved
    _write_config(cfg)
    show_message(
        f"安裝路徑已設定為：\n{resolved}\n\n"
        "下次啟動工具時會安裝到這個路徑；已下載的舊工具不會自動搬移。"
    )


def register_protocol():
    """Teach Windows that real-toolbox://... links should be handed to this
    exact running program - the one-time setup step every user runs once
    (double-clicking the downloaded exe with no arguments does this - see
    dispatch()) before any real-toolbox:// link on the web page will do
    anything at all.

    Writes under HKEY_CURRENT_USER (not HKEY_CLASSES_ROOT/HKEY_LOCAL_MACHINE)
    deliberately - HKCU\\Software\\Classes is honored by Windows for URI
    protocol handlers exactly like HKCR is, but does NOT require
    administrator privileges to write to, unlike HKCR/HKLM. This keeps the
    whole install process admin-free, matching the "just download and
    double-click" experience described on the web page.

    The registered command is built from sys.executable, i.e. wherever THIS
    exact running copy of the program currently lives on disk - NOT a fixed
    path. This means re-registering always points Windows at whichever copy
    you just ran --register from; running --register from more than one
    copy of the Launcher on the same machine (e.g. a developer's build
    alongside a user's downloaded copy) will make the most recently
    registered one "win". (This bit real-world testing during development:
    repeatedly running --register against development builds on a shared
    machine overwrote what a real end-to-end test had registered, which
    looked like a mysterious regression but was actually just this
    documented, expected behavior.)

    getattr(sys, "frozen", False) distinguishes "running as a PyInstaller-
    frozen .exe" from "running as a plain .py script via python.exe" -
    only relevant for local development (the frozen case is what every real
    user's copy actually is): a frozen exe's sys.executable IS the whole
    program, so the registered command is just `"<exe>" "%1"`; a plain
    script needs `"<python.exe>" "<launcher.py path>" "%1"` so Windows knows
    to invoke the interpreter with the script as its argument.

    "%1" is the Windows placeholder that gets substituted with the actual
    real-toolbox://... URI the user clicked - it becomes sys.argv[1] in
    dispatch().
    """
    if getattr(sys, "frozen", False):
        command = f'"{sys.executable}" "%1"'
    else:
        command = f'"{sys.executable}" "{Path(__file__).resolve()}" "%1"'

    key_path = r"Software\Classes\real-toolbox"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        # The (Default) value's exact text doesn't matter functionally, but
        # is conventionally a human-readable description of the protocol.
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:real-toolbox Protocol")
        # This specific empty-string value under this specific name is what
        # tells Windows "real-toolbox is a URI scheme, not a file
        # extension" - without it, Windows won't treat real-toolbox://... as
        # a protocol to hand off at all.
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
    show_message("設定完成！之後在 MT Toolbox 網頁上點擊工具連結就會自動啟動。")


def dispatch():
    """Decide what this invocation of the program is actually being asked to
    do, based on sys.argv, and do it. Called (wrapped in error handling) by
    main() - see main()'s docstring for why the error handling lives one
    level up instead of here.

    Five cases, checked in this order:

      1. `real-toolbox-launcher.exe --apply-update <new-exe> <old-exe> [<self-exe>]` -
         hidden, internal-only verb: this is what maybe_self_update() spawns
         (from a throwaway COPY of the current exe, not the real one - see
         apply_update's docstring for why that distinction is critical, not
         cosmetic) as a separate detached process to swap a downloaded
         update into place. The optional 4th argument is that throwaway
         copy's own path, used for best-effort self-cleanup after a
         successful swap. Never invoked by a user directly, and never
         registered as the real-toolbox:// protocol handler.

      2. `real-toolbox-launcher.exe --version` - explicit, on-demand version
         check for anyone who wants to confirm it without triggering
         anything else (--register, a real launch, etc). See
         show_message's docstring for the OTHER, passive way a version
         is visible: every message box this program ever shows carries
         LAUNCHER_VERSION in its title by default, so a user doesn't
         strictly need to know this flag exists at all.

      3. `real-toolbox-launcher.exe --set-install-dir <path>` - explicit
         admin-ish command a user runs directly from a terminal to relocate
         where tools get installed. See set_install_dir().

      4. `real-toolbox-launcher.exe` with no arguments at all, OR
         `real-toolbox-launcher.exe --register` explicitly - the one-time
         setup step. No-arguments is treated the same as --register
         specifically so that double-clicking the freshly downloaded exe in
         File Explorer (which runs it with zero arguments) "just works" as
         an install step, without requiring the user to know to open a
         terminal and type a flag. See register_protocol().

      5. Anything else - assumed to be a real-toolbox://launch/... URI, the
         normal case triggered by clicking a link on the web page (Windows
         passes the clicked URI as the sole argument, per the "%1" in the
         registered command - see register_protocol()). Parsed by
         parse_launch_path, then guarded by the launch-lock (see
         acquire_launch_lock's docstring for why) before actually calling
         launch().

         maybe_self_update() is called LAST, in the `finally` alongside
         releasing the launch-lock - so it always runs whether launch()
         succeeded or raised (e.g. "this tool isn't available yet"), but
         deliberately not before or during the tool's own launch. apply_update
         (the detached helper
         maybe_self_update spawns) can only successfully swap this process's
         exe file out once this process has actually exited, and it only
         retries for a bounded window (see apply_update's docstring) rather
         than waiting indefinitely - so the less work this process still has
         left to do after spawning that helper, the better its chances of
         winning that race. Checking last, right before this function
         returns and the process exits, minimizes that window to essentially
         nothing. (An earlier version of this code called maybe_self_update()
         before the tool launch instead, and real testing showed the race
         losing consistently - the tool's own download could easily
         outlast apply_update's retry budget on its own.)
    """
    if len(sys.argv) >= 4 and sys.argv[1] == "--apply-update":
        self_path = sys.argv[4] if len(sys.argv) >= 5 else None
        apply_update(sys.argv[2], sys.argv[3], self_path)
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--version":
        show_message(f"目前安裝的版本：v{LAUNCHER_VERSION}")
        return

    if len(sys.argv) >= 3 and sys.argv[1] == "--set-install-dir":
        set_install_dir(sys.argv[2])
        return

    if len(sys.argv) < 2 or sys.argv[1] == "--register":
        register_protocol()
        return

    tool_id, sub_id = parse_launch_path(sys.argv[1])
    # lock_key distinguishes sub-tools of the same parent tool from each
    # other (e.g. ledtool_arcadyan's cam/roi/led are locked independently),
    # so launching two *different* sub-tools of the same parent
    # simultaneously is not blocked by this guard - only re-launching the
    # exact same (tool, sub-tool) pair while it's already mid-flight is.
    lock_key = tool_id if sub_id is None else f"{tool_id}__{sub_id}"
    lock_file = acquire_launch_lock(lock_key)
    if lock_file is None:
        # Another invocation for the same tool is already mid-flight (e.g. the
        # user double-clicked the launch button); back off silently instead of
        # racing it or popping up a redundant message box.
        return
    try:
        launch(tool_id, sub_id)
    finally:
        release_launch_lock(lock_file)
        # In the finally, not after the try/finally block - launch() raising
        # (a genuinely failed launch, or a deliberate SystemExit like "this
        # tool isn't available yet") must not skip the self-update check;
        # a self-update opportunity shouldn't depend on the requested tool
        # having launched successfully.
        maybe_self_update()


def main():
    """Entry point. All of dispatch()'s actual work is wrapped here in a
    single top-level try/except specifically so there is exactly ONE place
    in the whole program responsible for turning a failure into user-visible
    feedback (a message box) - individual functions deeper in the call stack
    just raise (usually SystemExit with a human-readable Chinese message;
    see e.g. find_tool, find_exe, parse_launch_path) and trust that whatever
    called them, transitively, eventually unwinds to here.

    SystemExit is handled separately from a bare Exception because
    SystemExit's message (raised throughout this file specifically to serve
    as user-facing text - see the module's various `raise SystemExit(f"...")`
    call sites) is itself the whole error message and needs no further
    context; a genuinely unexpected Exception (a real bug) instead gets its
    full traceback shown, plus logged to DEBUG_LOG, since that's the only
    diagnostic trail available for a windowless program with no console.
    """
    try:
        dispatch()
    except SystemExit as e:
        show_message(str(e), icon=MB_ICONERROR)
    except Exception:
        dbg(f"unhandled exception:\n{traceback.format_exc()}")
        show_message(f"發生未預期的錯誤：\n\n{traceback.format_exc()}", icon=MB_ICONERROR)


if __name__ == "__main__":
    main()
