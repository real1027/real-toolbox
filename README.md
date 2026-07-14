# MT Toolbox

產測內部工具的統一入口與啟動器。開一個網頁、點一下工具名稱，本機的 Launcher 就會自動檢查版本、下載（如果需要）、然後執行——不用再手動找 exe、對版本。

**線上網址：** https://real1027.github.io/real-toolbox/

## 架構

```
瀏覽器（entry page）──點連結──▶ real-toolbox://launch/<tool-id>
                                        │
                                        ▼
                              本機 Launcher（已註冊此協定）
                                        │
                          讀 manifest.json，比對本機版本
                                        │
                        需要時下載 zip、解壓、執行對應 exe
```

- **entry page**（[index.html](index.html) + [assets/](assets/)）：靜態頁面，部署在 GitHub Pages。讀 [manifest.json](manifest.json)，畫出工具清單，每個工具是一個 `real-toolbox://launch/<tool-id>` 連結。
- **manifest.json**：每個工具一筆資料（欄位說明見下方）。
- **Launcher**（[launcher/launcher.py](launcher/launcher.py)）：本機執行檔，註冊 `real-toolbox://` 自訂協定。收到呼叫後讀 manifest、比對本機版本、需要時下載解壓、執行對應工具。完全通用，不寫死任何特定工具邏輯。

## 給使用者：第一次使用

1. 下載 Launcher：[real-toolbox-launcher.exe](https://github.com/real1027/real-toolbox/releases/download/launcher-v1.0.0/real-toolbox-launcher.exe)
2. 雙擊執行一次（跳出黑色視窗屬正常，跑完按 Enter 關閉）——這一步會把 `real-toolbox://` 這個連結類型註冊到你的電腦
3. 回到網頁點任一工具的「啟動」，瀏覽器問是否開啟 real-toolbox 連結時選「開啟」（通常只會問這一次）
4. 之後每次點擊都會自動檢查版本、下載（如有需要）、執行

工具預設安裝在 `D:\___ARC_MT_TOOLS___`。想改路徑：

```
real-toolbox-launcher.exe --set-install-dir D:\你想要的路徑
```

（這個路徑是給 Launcher 自己記的設定，跟 `%LOCALAPPDATA%` 下的 config 檔分開存放，所以就算改到的磁碟機在某台機器上不存在，也不會卡死覆寫機制本身。）

## manifest.json 欄位

```jsonc
{
  "id": "sfisemulator_arcadyan",   // 唯一代號，同時是 real-toolbox://launch/<id> 的 id
  "name": "SFIS Emulator",          // 畫面顯示名稱
  "icon": "repeat",                 // Lucide icon 名稱（見 assets/app.js 的 ICONS）
  "description": "...",             // 卡片上的簡短說明
  "latest_version": "1.3.1",        // 對應 Release tag
  "download_url": "...",            // Release permalink，指向打包好的 zip
  "exe_name": "SfisSimulator.exe"    // zip 解壓後要執行的檔案
}
```

- `status: "coming_soon"`：卡片顯示成停用狀態（尚未提供 `download_url`/`exe_name` 時的佔位用）。
- `type: "link"` + `url`：純外部連結（例如儀器租借系統），不透過 Launcher，直接開新分頁。
- `sub_tools: [{ id, name, exe_name }, ...]`：一個工具裡有多個進入點（例如 LED AOI 的 CAM/ROI/LED），共用同一份 `download_url`/`latest_version`，畫面上會顯示多顆啟動按鈕，對應 `real-toolbox://launch/<id>/<sub-id>`。

## 想把自己的工具接進來？

看 [CONTRIBUTING.md](CONTRIBUTING.md)——裡面說明你的 GitLab repo/Release 要怎麼準備，以及要提供哪些欄位。

## 本機開發測試

```
# 起一個本地伺服器預覽頁面（manifest.json 用 fetch 讀取，不能直接用 file:// 開）
python -m http.server 8532

# 改 Launcher 後重新打包
cd launcher
python -m PyInstaller --onefile --name real-toolbox-launcher --console launcher.py
```

`launcher.py` 支援環境變數覆寫，方便本機測試不同 manifest 來源或安裝路徑：

- `REAL_TOOLBOX_MANIFEST_URL`：覆寫 manifest.json 來源（預設是線上網址）
- `REAL_TOOLBOX_INSTALL_DIR`：覆寫安裝路徑（預設是 `D:\___ARC_MT_TOOLS___`，優先權高於 `--set-install-dir` 寫的 config）
