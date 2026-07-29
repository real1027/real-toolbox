# MT Toolbox — 給 AI Agent 的上架前置作業指示

> **這份文件是寫給 AI Agent（例如 Claude Code）執行用的，不是給人看的說明文件。**
> 如果你是人類，想看好讀版說明，請改看 [CONTRIBUTING.md](CONTRIBUTING.md) 或
> [onboarding.html](https://real1027.github.io/real-toolbox/onboarding.html)。
>
> **給人類的使用方式**：把這份文件連同你已經 build 好的工具（執行檔＋所有相依檔案）
> 一起交給你自己的 AI Agent，跟它說「照著 `AGENT_ONBOARDING.md` 的步驟，幫我完成
> MT Toolbox 上架前置作業」。Agent 跑完之後會產出一個「manifest 欄位區塊」，把那個
> 區塊**原封不動**貼給 MT Toolbox 維護者（`real_chang`）就完成了。

---

## 給 Agent 的任務總覽

你的任務是幫使用者完成把一個工具接進 [MT Toolbox](https://real1027.github.io/real-toolbox/) 所需的**所有前置作業**，最後產出一份可以直接貼給維護者的 manifest 欄位區塊。你不需要、也沒有權限直接修改 MT Toolbox 這個 repo 本身——你只需要：

1. 確認使用者的 GitLab repo/專案設定正確
2. 幫忙打包、上傳 Release
3. 用 `curl` 實際驗證下載連結能匿名使用
4. 整理出最終欄位，用固定格式輸出給使用者

**每一步都要實際驗證，不要用「應該可以」帶過。** 尤其是 Step 4 的匿名下載驗證，這是最容易漏掉、也最容易讓使用者在別人電腦上才發現失敗的一步。

---

## Step 0：跟使用者確認以下資訊

在動手之前，先跟使用者確認（如果對話裡已經有就不用重複問）：

- 這個工具目前的原始碼／build 產物在哪裡（本機路徑，或現有的 GitLab repo）
- 這個工具是「一般單一 exe」、「一個工具裡有多個獨立 exe（多進入點）」、還是「其實只是一個外部網址，不需要下載執行」
- 有沒有現成的 GitLab 專案可以放 Release，還是需要新開一個

如果使用者選的是「純外部連結」類型，直接跳到 [附錄 C：純外部連結類型](#附錄-c純外部連結類型)，不需要走下面 Step 1–4。

---

## Step 1：確認/建立可以匿名下載的 GitLab 專案

MT Toolbox 的 Launcher 是在使用者電腦上執行的獨立程式，**不會、也不能幫忙登入**去下載檔案。所以工具的下載來源必須是一個 **Public** 的 GitLab 專案。

- 如果使用者現有的開發 repo 就是公開的（或可以直接公開），可以直接用。
- 如果現有 repo 是私有的（例如公司內部的開發用 repo），**不要**把整個私有 repo 公開，而是：
  1. 開一個新的、獨立的 public 專案，只用來放 Release 附件（例如 `http://10.118.53.32/tools/<project-name>`，跟原本私有的開發用 repo 分開）
  2. 開發還是在私有 repo 進行，只有要發布給 MT Toolbox 用的 Release 才放進這個新的 public 專案

如果你（Agent）有 GitLab CLI（`glab`）或 API token 可以用，可以直接幫使用者建立這個專案；如果沒有，明確告訴使用者要自己手動在 GitLab 網頁上建立一個新專案並設成 Public，你再接手後續步驟。

---

## Step 2：把 build 好的東西打包成一個 zip

檢查使用者提供的 build 產物資料夾，確認裡面有：

- 主程式 exe（可能不只一個，見下方「多進入點」）
- 執行時需要的所有相依檔案：設定檔（`.ini`）、資料庫/資料檔（`.csv` 等）、圖片、DLL 等
- **不要**打包進去：原始碼、build 工具本身產生的中間檔（例如 PyInstaller 的 `build/` 資料夾）

打包成一個 zip（檔名自訂，例如 `<tool-id>.zip`）。zip 內部要不要有子資料夾都沒關係——MT Toolbox 的 Launcher 解壓後會在整個資料夾底下**遞迴搜尋**你告訴它的 exe 檔名。但務必檢查：

- 同一個 zip 裡**不要有兩個同名的 exe**（就算在不同子資料夾也不行），否則 Launcher 無法判斷要執行哪一個
- 記下每一支 exe **實際的檔名**（含副檔名、大小寫），這會是最後要交給維護者的 `exe_name` 欄位，必須跟 zip 裡的檔名完全一致

---

## Step 3：建立 GitLab Release，取得永久連結（permalink）

1. 決定版本號，建議照 [SemVer](https://semver.org/lang/zh-TW/) 規則（例如 `v1.0.0`）：有破壞性變更升 MAJOR、加功能升 MINOR、修 bug 升 PATCH
2. 在這個 tag 上建立一個 GitLab Release
3. 把 Step 2 打包好的 zip 當作 Release 的附件上傳
4. 記下這個下載連結的**永久連結（permalink）**格式，這是最後要交給維護者的 `download_url`：

   ```
   http://<gitlab-host>/<namespace>/<project>/-/releases/permalink/latest/downloads/<你的zip檔名.zip>
   ```

   這個網址的意思是「這個專案最新一個 Release 的這個附件」，之後每次發新版只要照常打新 tag、上傳同名的 zip，這個網址完全不用改，**MT Toolbox 的 Launcher 會自動偵測到新版，不需要再更新 manifest.json 的版本號**。

如果你（Agent）有辦法透過 GitLab API 或 `glab` CLI 直接建立 Release、上傳附件，就直接做；沒有的話，明確列出上面 1–3 的手動步驟請使用者操作，你負責產生正確的 permalink 網址格式給使用者核對，並在使用者做完後接手 Step 4 的驗證。

---

## Step 4：驗證匿名下載（不要跳過，也不要只用「應該沒問題」帶過）

實際執行下面這行指令（把網址換成 Step 3 的 permalink）：

```bash
curl -sL -o /dev/null -w "%{http_code}\n" "http://<gitlab-host>/<namespace>/<project>/-/releases/permalink/latest/downloads/<你的zip檔名.zip>"
```

**判讀結果：**

- 回應 `200` → 通過，可以往下走 Step 5。
- 回應 `302`，或指令輸出裡出現 `/users/sign_in` 相關字樣 → 代表這個專案還不是 Public，或路徑打錯了。回頭檢查 Step 1（專案有沒有真的設成 Public）跟 Step 3 的網址格式，修好之後**重新驗證一次**，不要假設「應該修好了」。
- 網路根本連不到（`curl` 直接失敗、connection refused 之類）→ 這通常代表這個 GitLab 只能在內網存取，你自己（Agent）如果沒有內網連線，就沒辦法代替使用者驗證這一步，明確告訴使用者「這一步需要你自己在能連到內網的機器上執行這行指令並回報結果」，不要跳過或假裝驗證過。

這一步沒有真的通過，MT Toolbox 的 Launcher 到使用者端一定會下載失敗——這是所有步驟裡最容易被輕忽、但影響最大的一步。

---

## Step 5：整理並輸出最終欄位

驗證都通過之後，跟使用者確認以下資訊（有些你已經從前面步驟知道了）：

| 欄位 | 說明 |
|---|---|
| `id` | 工具的唯一代號，只能用英數字和底線（例如 `relay_board_checker`）|
| 顯示名稱 | 畫面上要顯示的名稱 |
| 簡短描述 | 一兩句話說明工具做什麼——可以直接摘要使用者的 README 或口頭描述 |
| 版本號 | Step 3 的 tag（例如 `1.0.0`，不用加 `v`）|
| 下載連結 | Step 3/4 驗證過的 permalink 網址 |
| exe 檔名 | Step 2 記下的實際檔名 |
| 圖示（選填）| 見下方「圖示選擇」|

### 圖示選擇

從 [Lucide](https://lucide.dev)（開源、ISC 授權）挑一個跟工具用途貼切的圖示名稱。目前 MT Toolbox 裡已經在用的：`camera`、`database`、`file-diff`、`radio`、`clipboard-check`、`box`、`search`、`circuit-board`。不在這個清單裡也沒關係，只要是 Lucide 官網上找得到的 icon 名稱都可以，交給維護者加。不指定的話，畫面上會用工具名稱前兩個字當預設圖示。

### 多進入點工具（一個工具裡有好幾支獨立的 exe）

不用拆成好幾個工具、好幾份 zip。維護者只需要一份 zip、一個版本號、一個下載連結，但要額外提供**每一支子程式**的：

- 子程式代號（例如 `cam`）
- 顯示名稱（例如「CAM 相機能力偵測」）
- 對應的 exe 檔名（例如 `CAM.exe`）

### 最終輸出格式

跑完上面所有步驟後，用這個格式輸出（單一 exe 工具範例）：

```
工具上架資訊：
- id: relay_board_checker
- 顯示名稱: Relay Board Bench Checker
- 簡短描述: 驗證產線上使用的 Relay 板功能是否正常，支援逐路 Relay ON/OFF、GPIO/ADC/INA219/INA233/MLX90614 量測。
- 版本號: 1.0.0
- 下載連結: http://10.118.53.32/tools/relay_board_checker/-/releases/permalink/latest/downloads/relay_board_checker.zip
- exe 檔名: RelayBoardChecker.exe
- 圖示建議: circuit-board
- 匿名下載驗證: 已用 curl 確認回應 200
```

多進入點工具，額外附上：

```
- 子程式:
  - id: cam, 顯示名稱: CAM 相機能力偵測, exe: CAM.exe
  - id: roi, 顯示名稱: ROI 框選, exe: ROI.exe
```

把這個區塊**完整貼給使用者**，請他們原封不動轉交給 MT Toolbox 維護者（`real_chang`）。到這裡你的任務就完成了——manifest.json 本身是維護者手動維護的檔案，不需要（也不應該）由你直接修改。

---

## 附錄 C：純外部連結類型

如果使用者要放的其實只是一個外部網址（例如某個內部系統的網頁入口），不需要 zip、不需要 exe、不需要 GitLab Release，Step 1–4 全部跳過。直接跟使用者確認：

- `id`（唯一代號）
- 顯示名稱
- 簡短描述
- 圖示（選填，見上方圖示選擇）
- 完整網址

用這個格式輸出：

```
工具上架資訊（純外部連結）：
- id: instrument_rental_system
- 顯示名稱: 儀器設備租借系統
- 簡短描述: 儀器設備租借申請入口。
- 圖示建議: box
- 網址: http://your-internal-system/...
```
