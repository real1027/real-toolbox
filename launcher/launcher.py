"""real-toolbox Launcher.

Handles the real-toolbox:// custom URI protocol: given
real-toolbox://launch/<tool-id>, looks up <tool-id> in manifest.json,
downloads/extracts the tool if the local copy is missing or outdated,
then runs its exe. Contains no per-tool logic - everything comes from
the manifest.
"""

import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import winreg
import zipfile
from pathlib import Path

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
    raise SystemExit(f"Tool '{tool_id}' not found in manifest")


def download_and_extract(tool, version_dir):
    version_dir.parent.mkdir(parents=True, exist_ok=True)
    zip_path = version_dir.parent / f"{tool['id']}.zip"
    urllib.request.urlretrieve(tool["download_url"], zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(version_dir)
    zip_path.unlink(missing_ok=True)


def find_exe(root_dir, exe_name):
    for path in root_dir.rglob(exe_name):
        return path
    raise SystemExit(f"{exe_name} not found under {root_dir} after extraction")


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
    raise SystemExit(f"Sub-tool '{sub_id}' not found under '{tool['id']}'")


def launch(tool_id, sub_id=None):
    manifest = load_manifest(MANIFEST_URL)
    tool = find_tool(manifest, tool_id)
    if tool.get("status") == "coming_soon":
        raise SystemExit(f"'{tool_id}' is not available yet")
    exe_name = resolve_exe_name(tool, sub_id)
    version = resolve_live_version(tool.get("download_url", "")) or tool["latest_version"]
    state = load_state()

    version_dir = TOOLS_DIR / tool_id / version
    if state.get(tool_id) != version or not version_dir.exists():
        tool_dir = TOOLS_DIR / tool_id
        if tool_dir.exists():
            shutil.rmtree(tool_dir, ignore_errors=True)
        download_and_extract(tool, version_dir)
        state[tool_id] = version
        save_state(state)

    exe_path = find_exe(version_dir, exe_name)
    subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))


def parse_launch_path(uri):
    match = re.match(r"real-toolbox://launch/([^/?#]+)(?:/([^/?#]+))?", uri)
    if not match:
        raise SystemExit(f"Invalid real-toolbox URI: {uri}")
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
    print(f"安裝路徑已設定為: {resolved}")
    print("（下次啟動工具時，會安裝到這個路徑；已下載的舊工具不會自動搬移。）")


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
    print(f"Registered real-toolbox:// -> {command}")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--set-install-dir":
        set_install_dir(sys.argv[2])
        input("按 Enter 鍵關閉視窗...")
        return

    if len(sys.argv) < 2 or sys.argv[1] == "--register":
        register_protocol()
        print("\n設定完成！之後在 real-toolbox 網頁上點擊工具連結就會自動啟動。")
        input("按 Enter 鍵關閉視窗...")
        return

    tool_id, sub_id = parse_launch_path(sys.argv[1])
    lock_key = tool_id if sub_id is None else f"{tool_id}__{sub_id}"
    lock_file = acquire_launch_lock(lock_key)
    if lock_file is None:
        print(f"'{lock_key}' 已經在啟動中，請稍候，不用重複點擊。")
        return
    try:
        launch(tool_id, sub_id)
    finally:
        release_launch_lock(lock_file)


if __name__ == "__main__":
    main()
