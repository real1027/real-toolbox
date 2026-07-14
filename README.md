# MT Toolbox

（顯示名稱是 **MT Toolbox**；底層 repo 名稱、GitHub URL、`real-toolbox://` 自訂協定都還是沿用最初的 `real-toolbox` 這個名字沒有改——詳見下方「命名說明」。）

產測開發工具的統一入口與啟動器。開一個網頁、點一下工具名稱，本機的 Launcher 就會自動檢查版本、下載（如果需要）、然後執行——不用再手動找 exe、對版本。

**線上網址：** https://real1027.github.io/real-toolbox/

---

## 目錄

- [整體架構](#整體架構)
- [給使用者：第一次使用](#給使用者第一次使用)
- [manifest.json 欄位完整說明](#manifestjson-欄位完整說明)
- [Launcher 內部機制](#launcher-內部機制)
  - [版本比對：自動讀取 GitLab Release，不用手動維護版號](#版本比對自動讀取-gitlab-release不用手動維護版號)
  - [內容指紋比對（ETag／檔案大小）：版號沒改但內容換了的保險機制](#內容指紋比對etag檔案大小版號沒改但內容換了的保險機制)
  - [防止重複啟動的鎖機制](#防止重複啟動的鎖機制)
  - [安裝路徑的決定順序](#安裝路徑的決定順序)
  - [無 console 視窗、用原生訊息框溝通](#無-console-視窗用原生訊息框溝通)
  - [下載進度小視窗](#下載進度小視窗)
  - [關於「等很久」：防毒軟體掃描新 exe 是正常現象](#關於等很久防毒軟體掃描新-exe-是正常現象)
- [網頁端機制](#網頁端機制)
  - [「啟動」→「啟動中…」的切換邏輯](#啟動啟動中的切換邏輯)
  - [「已完成安裝，不再顯示」的記憶機制](#已完成安裝不再顯示的記憶機制)
- [命名說明：MT Toolbox vs real-toolbox](#命名說明mt-toolbox-vs-real-toolbox)
- [想把自己的工具接進來？](#想把自己的工具接進來)
- [本機開發測試](#本機開發測試)

---

## 整體架構

```
瀏覽器（entry page）──點連結──▶ real-toolbox://launch/<tool-id>[/<sub-id>]
                                        │
                          （瀏覽器可能先跳出一次性的「是否開啟」確認框）
                                        │
                                        ▼
                              本機 Launcher（已註冊此協定）
                                        │
                    讀 manifest.json → 比對本機版本／內容指紋
                                        │
                        需要時：刪舊版 → 下載 zip → 解壓 → 記錄新版本
                                        │
                              找到指定的 exe，執行
```

三個部分：

- **entry page**（[index.html](index.html) + [assets/app.js](assets/app.js) + [assets/style.css](assets/style.css)）：純靜態頁面，沒有任何後端、沒有 build 流程，直接部署在 GitHub Pages。讀 [manifest.json](manifest.json)，畫出工具清單卡片，每個可啟動的工具是一個 `real-toolbox://launch/<tool-id>` 連結。
- **manifest.json**：所有工具的共用資料來源，Launcher 跟網頁讀的是同一份檔案，兩邊不會對工具清單有認知落差。欄位說明見下方。
- **Launcher**（[launcher/launcher.py](launcher/launcher.py)，用 PyInstaller 打包成單一 exe）：使用者電腦上執行的小程式，負責註冊 `real-toolbox://` 這個自訂 URI 協定、解析點擊的連結、比對版本、下載解壓、執行對應 exe。**完全通用，不寫死任何特定工具的邏輯**——新增工具只需要改 `manifest.json`，永遠不需要改這個程式本身。

瀏覽器基於安全考量，網頁本身無法直接執行本機的 .exe 檔案，這也是為什麼整套系統要繞道「自訂協定 + 本機常駐程式」這個組合的根本原因；第一次點擊時瀏覽器跳出的「是否要開啟 real-toolbox 連結？」確認框，是瀏覽器自己的安全機制，沒辦法從這邊消除（但通常只會被問一次）。

## 給使用者：第一次使用

1. 下載 Launcher：[real-toolbox-launcher.exe](https://github.com/real1027/real-toolbox/releases/download/launcher-v1.0.0/real-toolbox-launcher.exe)
2. 雙擊執行一次，跳出「設定完成」的提示視窗後按確定——這一步會把 `real-toolbox://` 這個連結類型註冊到你的電腦（寫入 `HKEY_CURRENT_USER`，不需要系統管理員權限）
3. 回到網頁點任一工具的「啟動」，瀏覽器問是否開啟 real-toolbox 連結時選「開啟」（通常只會問這一次）
4. 之後每次點擊都會自動檢查版本、下載（如有需要）、執行

工具預設安裝在 `D:\___ARC_MT_TOOLS___`。想改路徑：

```
real-toolbox-launcher.exe --set-install-dir D:\你想要的路徑
```

（這個路徑本身是寫進 `%LOCALAPPDATA%\real-toolbox\config.json`，跟實際安裝目錄分開存放——這樣設計是為了避免「改到的磁碟機在某台機器上不存在」時，連帶讓覆寫機制本身也讀不到，見下方「安裝路徑的決定順序」。）

## manifest.json 欄位完整說明

```jsonc
{
  "id": "sfisemulator_arcadyan",     // 唯一代號，同時是 real-toolbox://launch/<id> 的 <id>
  "name": "SFIS Emulator",           // 畫面顯示名稱
  "icon": "database",                // Lucide icon 名稱，見下方「目前可用的圖示」
  "description": "...",              // 卡片上的簡短說明
  "latest_version": "1.3.1",         // 對應 Release tag（純顯示用，見下方版本比對機制）
  "download_url": "...",             // Release permalink，指向打包好的 zip
  "exe_name": "SfisSimulator.exe"     // zip 解壓後要執行的檔案
}
```

**特殊欄位／變化型：**

- `status: "coming_soon"`：卡片顯示成停用狀態（灰階、按鈕不可點、顯示「即將推出」標籤）。用於已經決定要收錄、但還沒有真正的 `download_url`/`exe_name` 可以填的佔位項目。
- `type: "link"` + `url`：純外部連結（例如儀器租借系統、Error Code 查詢系統），這種工具本身就是一個網頁系統，不透過 Launcher 下載執行，卡片按鈕會顯示「前往」，直接開新分頁連過去。
- `sub_tools: [{ id, name, exe_name }, ...]`：一個工具裡有多個獨立進入點（例如 LED AOI 的 CAM / ROI / LED 三支程式），共用同一份 `download_url`/`latest_version`（同一個 zip 裡打包三支 exe），畫面上會顯示一欄多顆啟動按鈕，各自對應 `real-toolbox://launch/<id>/<sub-id>`。

**目前可用的圖示**（定義在 [assets/app.js](assets/app.js) 的 `ICONS`，全部來自 [Lucide](https://lucide.dev)，ISC 授權）：`camera`、`database`、`file-diff`、`box`、`radio`、`clipboard-check`、`search`、`wrench`、`repeat`。想用清單以外的 icon，只要是 Lucide 官網上找得到的都可以加，加的地方就是 `assets/app.js` 的 `ICONS` 物件。

**注意：目前沒有「公司內部／個人」這種分類欄位。** 這個欄位最初有規劃過（`category: internal | personal`），但這個部署的實際用途上所有工具都是產測開發工具，這個區分沒有意義，所以連同網頁上的分類 tab、卡片上的分類標籤都已經整個拿掉了。

## Launcher 內部機制

以下這幾個機制都是實際踩過坑之後加上去的，各自要解決的問題都不一樣，`launcher/launcher.py` 裡每個函式的 docstring 也有更細的技術說明，這裡是給不想直接看程式碼的人的摘要版。

### 版本比對：自動讀取 GitLab Release，不用手動維護版號

`manifest.json` 裡的 `latest_version` **只是網頁卡片上顯示用的字樣**，Launcher 實際判斷「要不要重新下載」時，不是看這個欄位，而是每次啟動時都主動去問工具的 GitLab Release 永久連結：

```
下載連結：.../-/releases/permalink/latest/downloads/<檔名.zip>
去掉 /downloads/<檔名.zip> 之後：.../-/releases/permalink/latest
```

對後面這個網址發一個 HEAD request，GitLab 回應的 redirect（`Location` header）會直接寫出目前真正指向哪個 tag，例如 `.../-/releases/v1.3.1`。Launcher 解析出 `1.3.1` 這個字串，拿來跟本機記錄的版本比對，決定要不要重新下載。

**這代表工具作者之後每次發新版，只要照常打新 tag、建新 Release、上傳新 zip，完全不用再通知任何人更新 manifest.json**——`manifest.json` 只有在「第一次上架」這個工具時才需要編輯。這個機制只認得「GitLab Release permalink」這種下載連結格式；如果某個工具的 `download_url` 不是這個格式，或是這次的網路請求失敗（離線、內網連不到等等），Launcher 會退回去用 `manifest.json` 裡寫的 `latest_version` 判斷，這種情況下發新版還是要通知維護者更新那個欄位。

### 內容指紋比對（ETag／檔案大小）：版號沒改但內容換了的保險機制

版本號比對有一個沒辦法自己解決的漏洞：如果工具作者重新上傳了一個修正過的 zip，但忘記打新的 tag（版本號沒變），單靠版本比對會誤判成「沒有變化，不用重新下載」。

為了堵住這個漏洞，Launcher 額外對下載連結發一個 HEAD request，記錄回應的 `ETag`（如果伺服器有給，例如 GitLab 的「repo 內原始檔案」serving 方式會給）跟 `Content-Length`（幾乎所有伺服器都會給，例如 GitLab 的 Generic Package Registry 沒有 ETag 但有這個）。這兩個值跟上次成功安裝時記錄的值只要有一個不一樣，即使版本號沒變，也會強制重新下載。

這是保險機制，不是取代版本比對——真的建議工具作者每次異動都老實打新版號（見 [onboarding.html](onboarding.html)），這個機制只是避免忘記打版號時整個系統一直卡在舊內容。

### 防止重複啟動的鎖機制

因為網頁完全收不到 Launcher 有沒有成功執行的回應（見下方「網頁端機制」），如果第一次下載某個工具要花比較久的時間，畫面上又沒有明顯變化，使用者可能會以為沒點到、又點了一次「啟動」。如果沒有防範，兩次呼叫會同時搶著刪除／重新建立同一個版本資料夾、同時下載，甚至同時啟動兩份工具。

做法是在 `APP_DIR/locks/` 底下，針對每個工具（如果是多進入點工具，精確到每個子程式）建立一個帶時間戳記的鎖檔，20 秒內的重複呼叫會直接安靜結束、不做任何事，讓第一個呼叫把整個流程走完。

### 安裝路徑的決定順序

1. 環境變數 `REAL_TOOLBOX_INSTALL_DIR`（主要給本機開發測試用）
2. `%LOCALAPPDATA%\real-toolbox\config.json` 裡記錄的 `install_dir`（透過 `--set-install-dir` 指令寫入）
3. 都沒有的話，預設 `D:\___ARC_MT_TOOLS___`

第 2 點的設定檔之所以固定放在 `%LOCALAPPDATA%`（每個 Windows 帳號一定存在、一定可寫），而不是放在「目前設定的安裝目錄」底下，是刻意設計成這樣：如果設定檔本身也跟著安裝目錄跑，一旦某台機器根本沒有 D 槽（預設值指向的磁碟機），程式會連「去哪裡讀取『請改用別的路徑』這個設定」都做不到，整個覆寫機制形同失效。固定放在使用者設定檔底下就沒有這個雞生蛋蛋生雞的問題。

### 無 console 視窗、用原生訊息框溝通

Launcher 用 PyInstaller 的 `--windowed` 模式打包，完全沒有 console 視窗——早期版本用 `--console` 打包，導致每次點擊啟動都會閃一下黑色視窗，看起來像出錯了。因為沒有 console 可以印訊息，程式改用兩種管道跟使用者溝通：

- `ctypes` 呼叫 Windows 原生的 `MessageBoxW`：用在「設定完成」這類一次性確認，以及任何錯誤訊息。
- 下方的下載進度小視窗：只在真的有下載動作發生時才出現。

### 下載進度小視窗

只有在需要下載/解壓時才會跳出來（版本沒變、內容沒變、資料夾也還在的正常情況——也就是絕大多數的啟動——完全不會看到這個視窗，啟動應該要感覺是瞬間的）。用 tkinter 刻的簡單視窗，一個文字說明（「正在下載.../正在解壓...」）加一個跑動的進度條（不是真的百分比，因為要準確算百分比需要知道總檔案大小，而且不是所有伺服器都會回報）。

如果 tkinter 本身在某些受限環境（例如某些遠端桌面 session）建立視窗失敗，Launcher 會安靜地退回成完全沒有視窗的模式繼續下載，不會因為這個錦上添花的 UI 失敗就讓整個啟動流程跟著失敗。

### 關於「等很久」：防毒軟體掃描新 exe 是正常現象

開發過程中實際遇過「剛裝好新 Launcher、點擊啟動、感覺像沒反應」的回報，用暫時加的除錯 log 追蹤後確認：**Launcher 自己的 Python 邏輯只花約 1 秒就執行完**，真正拖時間的是 **Windows Defender／防毒軟體對一個全新建置／下載的 exe 做首次掃描**，這是作業系統層級的行為，跟這支程式的邏輯無關，也沒辦法用程式碼消除。這個發現同時也是網頁端把「啟動中…」逾時時間從 6 秒一路調到 60 秒（見下方）、以及在網頁上加註解說明的原因。同一個檔案只要掃過一次，之後再執行就不會再等。

## 網頁端機制

### 「啟動」→「啟動中…」的切換邏輯

`real-toolbox://` 這種自訂協定連結，網頁完全收不到「有沒有真的啟動成功」的回應——瀏覽器把連結交給 Launcher（或先跳出自己的確認框）之後，這件事就跟網頁的 JavaScript 完全無關了。所以這整套機制只是盡力而為的體驗補強，不是真的狀態回報：

- 點擊當下：按鈕文字換成「啟動中…」，加上 `is-loading` class（CSS 設定 `pointer-events: none`，這才是真正擋掉「再點也沒用」的機制，不是額外寫的 JS 防連點邏輯），並啟動一個 60 秒的計時器（這個數字從一開始的 6 秒一路調大，見上一節防毒掃描的發現）。
- 如果瀏覽器分頁在計時器跑完之前失去焦點（`document.hidden` 變成 `true`）——通常代表跳出了系統的「是否開啟」確認框，或 Launcher／工具本身變成前景視窗——就立刻恢復成「啟動」，不用等滿 60 秒。這只是一個猜測性質的訊號，使用者剛好切去別的視窗也會觸發同樣的邏輯，不是 100% 準確。
- 60 秒後不管有沒有偵測到分頁失焦，都會恢復成「啟動」，讓使用者至少可以再試一次。

### 「已完成安裝，不再顯示」的記憶機制

網頁本身沒辦法檢查使用者電腦上有沒有安裝 Launcher（瀏覽器基於安全考量，不允許網頁程式碼讀取任意本機路徑或登錄檔），所以沒辦法做到「自動偵測已安裝就不顯示安裝說明」。做法是改用使用者自己確認：安裝說明卡片裡有一個「✓ 已完成安裝，不再顯示」按鈕，按下去會寫一個 `localStorage` 標記，這台電腦、這個瀏覽器之後開啟這個頁面就不會再自動展開安裝說明，右上角會留一個「工具啟動教學」的按鈕可以隨時叫回來。

## 命名說明：MT Toolbox vs real-toolbox

專案原本命名為 real-toolbox，後來因為「不是只有公司內部使用」把畫面上顯示的名稱改成 **MT Toolbox**（`<title>`、頁首、brand 圖示都已更新）。但以下這些底層的識別名稱**維持原樣沒有改**：

- GitHub repo 名稱：`real1027/real-toolbox`
- 網站網址：`https://real1027.github.io/real-toolbox/`
- 自訂 URI 協定：`real-toolbox://`
- Launcher 檔名、Release tag（`launcher-v1.0.0`）等

沒有一併改名是刻意的決定：協定名稱一旦改了，所有已經在使用者電腦上註冊過的 `real-toolbox://` 對應關係都要重新註冊一次；repo 改名也可能影響已經發出去的連結。如果之後要一併把這些底層名稱也改成 `mt-toolbox`，這會是一個需要另外規劃、會影響既有使用者的較大改動。

## 想把自己的工具接進來？

看 [CONTRIBUTING.md](CONTRIBUTING.md)（repo 內部版本）或 [onboarding.html](onboarding.html)（給一般使用者看的完整版，網頁上「工具上架說明」連結點進去的就是這份）——裡面說明你的 GitLab repo/Release 要怎麼準備、要提供哪些欄位、多進入點工具跟純外部連結工具要怎麼處理。

## 本機開發測試

```
# 起一個本地伺服器預覽頁面（manifest.json 用 fetch 讀取，不能直接用 file:// 開）
python -m http.server 8532

# 改 Launcher 後重新打包（--windowed：沒有 console 視窗）
cd launcher
python -m PyInstaller --onefile --windowed --name real-toolbox-launcher launcher.py
```

`launcher.py` 支援環境變數覆寫，方便本機測試不同 manifest 來源或安裝路徑，不用改程式碼：

- `REAL_TOOLBOX_MANIFEST_URL`：覆寫 manifest.json 來源（預設是線上網址），可以指向本機的檔案路徑
- `REAL_TOOLBOX_INSTALL_DIR`：覆寫安裝路徑（預設是 `D:\___ARC_MT_TOOLS___`），優先權高於 `--set-install-dir` 寫的 config

**開發時的一個重要提醒**：`--register` 指令會把 `real-toolbox://` 協定指向「當下正在執行的那個 exe/腳本」，如果在同一台機器上反覆對開發用的版本執行 `--register` 測試，會把這台機器上真正在使用的註冊值覆蓋掉（開發過程中真的發生過這個問題，導致一次「SFIS Emulator 突然開啟不了」的誤報）。在別人也在正常使用同一台機器的情況下測試 `--register`，測完記得幫忙重新指回正式版的 Launcher。
