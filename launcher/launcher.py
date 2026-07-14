"""real-toolbox Launcher.

Handles the real-toolbox:// custom URI protocol: given
real-toolbox://launch/<tool-id>, looks up <tool-id> in manifest.json,
downloads/extracts the tool if the local copy is missing or outdated,
then runs its exe. Contains no per-tool logic - everything comes from
the manifest.

Runs windowless (no console flash). Feedback for --register/--set-install-dir
and for errors is a native message box instead of console output, since
there's no console to print to.
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

MB_ICONINFORMATION = 0x40
MB_ICONERROR = 0x10

# Crash-diagnostic log only (not a running trace) - there's no console to see
# a traceback on, so unexpected failures get appended here in addition to the
# message box, in case someone needs to debug a remote machine after the fact.
DEBUG_LOG = Path(os.environ.get("TEMP", str(Path.home()))) / "real-toolbox-debug.log"


def dbg(msg):
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.time():.3f} {msg}\n")
    except OSError:
        pass


def show_message(text, icon=MB_ICONINFORMATION, title="MT Toolbox Launcher"):
    ctypes.windll.user32.MessageBoxW(0, text, title, icon)


# Config always lives under the per-user profile (guaranteed to exist and be
# writable) so it can redirect DEFAULT_APP_DIR even when that path's drive
# isn't available on a given machine.
CONFIG_FILE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "real-toolbox" / "config.json"
DEFAULT_APP_DIR = Path(r"D:\___ARC_MT_TOOLS___")


def resolve_app_dir():
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


APP_DIR = resolve_app_dir()
TOOLS_DIR = APP_DIR / "tools"
STATE_FILE = APP_DIR / "installed.json"

DEFAULT_MANIFEST_URL = "https://real1027.github.io/real-toolbox/manifest.json"
MANIFEST_URL = os.environ.get("REAL_TOOLBOX_MANIFEST_URL", DEFAULT_MANIFEST_URL)


def load_manifest(manifest_url):
    if manifest_url.startswith("http://") or manifest_url.startswith("https://"):
        with urllib.request.urlopen(manifest_url, timeout=10) as resp:
            return json.load(resp)
    with open(manifest_url, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def find_tool(manifest, tool_id):
    for tool in manifest.get("tools", []):
        if tool["id"] == tool_id:
            return tool
    raise SystemExit(f"在工具清單裡找不到 '{tool_id}'")


class ProgressWindow:
    """Small always-on-top window shown only while an actual download/extract
    is happening (a cold install or a version bump) - the common case of
    "already installed, just launch" never creates this window at all."""

    def __init__(self, tool_name):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.root = tk.Tk()
        self.root.title("MT Toolbox")
        width, height = 360, 120
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        self.label = tk.Label(self.root, text=f"正在準備 {tool_name} ...", pady=12, font=("Segoe UI", 10))
        self.label.pack()

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=300, mode="indeterminate")
        self.progress.pack(pady=6)
        self.progress.start(12)

        self.root.update()

    def set_status(self, text):
        self.label.config(text=text)
        self.root.update()

    def pump(self):
        self.root.update()

    def close(self):
        self.progress.stop()
        self.root.destroy()


class NullProgress:
    """No-op stand-in used when the progress window itself can't be created
    (e.g. some restricted/remote desktop sessions) - downloads should still
    proceed silently rather than the whole launch failing over a UI nicety."""

    def set_status(self, text):
        pass

    def pump(self):
        pass

    def close(self):
        pass


def make_progress_window(tool_name):
    try:
        return ProgressWindow(tool_name)
    except Exception:
        dbg(f"ProgressWindow failed:\n{traceback.format_exc()}")
        return NullProgress()


def download_and_extract(tool, version_dir, progress=None):
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
    for path in root_dir.rglob(exe_name):
        return path
    raise SystemExit(f"解壓後找不到 {exe_name}（資料夾：{root_dir}）")


PERMALINK_MARKER = "/-/releases/permalink/latest/downloads/"
LOCK_TTL_SECONDS = 20


def resolve_live_version(download_url):
    """Ask the GitLab release permalink what tag it currently points at.

    download_url is normally .../-/releases/permalink/latest/downloads/<file>,
    a URL that always resolves to the newest release without manifest.json
    needing to be updated on every version bump. Stripping the /downloads/<file>
    suffix gives the permalink page itself, whose redirect target embeds the
    real tag name - so the Launcher can self-heal instead of trusting a
    manually-maintained latest_version field. Falls back to manifest.json's
    latest_version (return None) for anything that isn't this GitLab pattern,
    or if the lookup fails for any reason (e.g. offline, internal network
    unreachable from this machine).
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
    tag = location.rstrip("/").rsplit("/", 1)[-1]
    if tag[:1] in ("v", "V") and tag[1:2].isdigit():
        tag = tag[1:]
    return tag or None


def acquire_launch_lock(key):
    """Guard against a user mashing the launch button while a slow
    download/extract is still running - a second invocation within
    LOCK_TTL_SECONDS just backs off instead of racing the first one."""
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
    if lock_file:
        lock_file.unlink(missing_ok=True)


def resolve_exe_name(tool, sub_id):
    if sub_id is None:
        return tool["exe_name"]
    for sub in tool.get("sub_tools", []):
        if sub["id"] == sub_id:
            return sub["exe_name"]
    raise SystemExit(f"在 '{tool['id']}' 裡找不到子程式 '{sub_id}'")


def launch(tool_id, sub_id=None):
    manifest = load_manifest(MANIFEST_URL)
    tool = find_tool(manifest, tool_id)
    if tool.get("status") == "coming_soon":
        raise SystemExit(f"'{tool['name']}' 還沒上架，敬請期待。")
    exe_name = resolve_exe_name(tool, sub_id)
    version = resolve_live_version(tool.get("download_url", "")) or tool["latest_version"]
    state = load_state()

    version_dir = TOOLS_DIR / tool_id / version
    needs_download = state.get(tool_id) != version or not version_dir.exists()

    if needs_download:
        progress = make_progress_window(tool["name"])
        try:
            tool_dir = TOOLS_DIR / tool_id
            if tool_dir.exists():
                shutil.rmtree(tool_dir, ignore_errors=True)
            download_and_extract(tool, version_dir, progress=progress)
            state[tool_id] = version
            save_state(state)
        finally:
            progress.close()

    exe_path = find_exe(version_dir, exe_name)
    subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))


def parse_launch_path(uri):
    match = re.match(r"real-toolbox://launch/([^/?#]+)(?:/([^/?#]+))?", uri)
    if not match:
        raise SystemExit(f"不是合法的 real-toolbox 連結：{uri}")
    return match.group(1), match.group(2)


def set_install_dir(path):
    resolved = str(Path(path).resolve())
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}
    cfg["install_dir"] = resolved
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    show_message(
        f"安裝路徑已設定為：\n{resolved}\n\n"
        "下次啟動工具時會安裝到這個路徑；已下載的舊工具不會自動搬移。"
    )


def register_protocol():
    if getattr(sys, "frozen", False):
        command = f'"{sys.executable}" "%1"'
    else:
        command = f'"{sys.executable}" "{Path(__file__).resolve()}" "%1"'

    key_path = r"Software\Classes\real-toolbox"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:real-toolbox Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
    show_message("設定完成！之後在 MT Toolbox 網頁上點擊工具連結就會自動啟動。")


def dispatch():
    if len(sys.argv) >= 3 and sys.argv[1] == "--set-install-dir":
        set_install_dir(sys.argv[2])
        return

    if len(sys.argv) < 2 or sys.argv[1] == "--register":
        register_protocol()
        return

    tool_id, sub_id = parse_launch_path(sys.argv[1])
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


def main():
    try:
        dispatch()
    except SystemExit as e:
        show_message(str(e), icon=MB_ICONERROR)
    except Exception:
        dbg(f"unhandled exception:\n{traceback.format_exc()}")
        show_message(f"發生未預期的錯誤：\n\n{traceback.format_exc()}", icon=MB_ICONERROR)


if __name__ == "__main__":
    main()
