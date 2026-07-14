"""real-toolbox Launcher.

Handles the real-toolbox:// custom URI protocol: given
real-toolbox://launch/<tool-id>, looks up <tool-id> in manifest.json,
downloads/extracts the tool if the local copy is missing or outdated,
then runs its exe. Contains no per-tool logic - everything comes from
the manifest.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import winreg
import zipfile
from pathlib import Path

DEFAULT_APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "real-toolbox"
CONFIG_FILE = DEFAULT_APP_DIR / "config.json"


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


def launch(tool_id):
    manifest = load_manifest(MANIFEST_URL)
    tool = find_tool(manifest, tool_id)
    state = load_state()

    version_dir = TOOLS_DIR / tool_id / tool["latest_version"]
    if state.get(tool_id) != tool["latest_version"] or not version_dir.exists():
        tool_dir = TOOLS_DIR / tool_id
        if tool_dir.exists():
            shutil.rmtree(tool_dir, ignore_errors=True)
        download_and_extract(tool, version_dir)
        state[tool_id] = tool["latest_version"]
        save_state(state)

    exe_path = find_exe(version_dir, tool["exe_name"])
    subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))


def parse_tool_id(uri):
    match = re.match(r"real-toolbox://launch/([^/?#]+)", uri)
    if not match:
        raise SystemExit(f"Invalid real-toolbox URI: {uri}")
    return match.group(1)


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

    launch(parse_tool_id(sys.argv[1]))


if __name__ == "__main__":
    main()
