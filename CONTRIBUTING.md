# 把你的工具接進 real-toolbox

想讓別人可以直接從 real-toolbox 網頁點一下就啟動你的工具，只要照著下面的步驟，把你的 GitLab repo 準備好、把資訊丟給 real-toolbox 維護者加進 `manifest.json` 就好。你的工具本身完全不用改，Launcher 不會有任何針對特定工具寫死的邏輯。

## 1. Repo 要能匿名下載

你的工具 repo（可以跟 real-toolbox 分開放）必須設成 **Public**，這樣 Launcher 才能在不登入的情況下下載檔案。如果目前是放在需要登入的私有專案下，參考 `sfisemulator_arcadyan` 的作法：把 repo 搬到一個獨立的 public 專案（例如 `http://10.118.53.32/tools/<your-project>`），跟内部私有的開發用 repo 分開。

## 2. 把 build 好的東西打包成一個 zip

一個 zip 裡面要包含：

- 主程式 exe（可以不只一個，見下方「多個進入點」）
- 執行時需要的所有依賴檔案、設定檔（`.ini`）、資料庫檔（`.csv`）、資源檔等
- 不需要包含原始碼、build 工具本身

Launcher 解壓後會在整個資料夾底下遞迴搜尋你指定的 exe 檔名，所以 zip 內部要不要有子資料夾都沒關係，只要檔名對得上、不要重複就好。

## 3. 建立 GitLab Release，並設定「永久連結」

1. 打 tag，例如 `v1.0.0`
2. 在這個 tag 上建立一個 GitLab Release
3. 把打包好的 zip 當作 Release 的附件上傳
4. 使用 GitLab 的 Release **permalink** 網址，而不是某個特定版本的連結：

   ```
   http://10.118.53.32/tools/<your-project>/-/releases/permalink/latest/downloads/<zip檔名.zip>
   ```

   這個網址永遠指向「最新一個 Release」的附件，所以之後每次發新版，只要照常打新 tag、建新 Release、上傳新 zip，這個網址完全不用改。

5. 找一台沒登入的瀏覽器（或用無痕視窗）測試這個 permalink 網址，確認不會被導去登入頁、可以直接下載——這一步很重要，沒測過的話 Launcher 到使用者端會下載失敗。

## 4. 把這些資訊交給 real-toolbox 維護者

- **顯示名稱**：畫面上要顯示的工具名稱
- **簡短描述**：一兩句話說明工具做什麼（可以直接給 README 內容，我們會摘要）
- **版本號**：對應你目前的 release tag（例如 `1.0.0`）——這個之後會自動更新，見下方第 5 節
- **下載連結**：上面第 3 步的 permalink 網址
- **exe 檔名**：zip 解壓後真正要執行的檔案名稱
- **圖示**：想要的話可以指定一個 [Lucide](https://lucide.dev) icon 名稱，不指定的話畫面上會用工具名稱前兩個字當預設圖示

### 如果你的工具有多個進入點（像 LED AOI 有 CAM / ROI / LED 三支程式）

不用拆成三個工具、三個 zip。一份 zip、一個版本號、一個下載連結就好，只要額外告訴我們每個子程式的：

- 子程式代號（例如 `cam`）
- 顯示名稱（例如「CAM 相機能力偵測」）
- 對應的 exe 檔名（例如 `CAM.exe`）

畫面上會變成同一張卡片裡有好幾顆啟動按鈕，各自對應一支 exe。

### 如果你要放的其實只是一個外部網址（不是可執行的工具）

例如儀器設備租借系統這種本身就是網頁的東西，不需要 zip、不需要 exe，只要給我們那個網址就好，畫面上會顯示成「前往」按鈕，直接開新分頁連過去，不會透過 Launcher。

## 5. 之後每次發新版

照常打新 tag、建新 Release、上傳新 zip（permalink 網址不用變）就好——**不需要再通知 real-toolbox 維護者更新 `manifest.json`**。Launcher 每次啟動工具前，會自己去問你 Release permalink 實際指到哪個 tag（不是讀 manifest 裡寫死的版號），有新版就自動抓新的下來、換掉舊的再執行。`manifest.json` 裡的 `latest_version` 只影響網頁卡片上顯示的版本號字樣，會慢慢過時沒關係，不影響實際下載/執行的正確性。

（這個機制只認得「GitLab Release permalink」這種下載連結格式；如果你的 `download_url` 不是這個格式，Launcher 會退回用 `manifest.json` 裡寫的 `latest_version` 判斷版本，這時候發新版還是要麻煩通知維護者更新。）
