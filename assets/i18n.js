// =============================================================================
// Shared trilingual (zh-Hant / en / vi) support for both index.html and
// onboarding.html. Loaded before each page's own script (app.js for
// index.html; onboarding.html has no other script at all).
//
// Deliberately does NOT translate manifest.json's per-tool "name"/
// "description" fields - those stay exactly as each tool's onboarder wrote
// them. Only this site's own fixed chrome (headings, buttons, instructions,
// the onboarding guide's prose) is translated - translating every tool's
// data in three languages would make onboarding a new tool require three
// times the writing, which isn't worth it for what's currently a small,
// slow-changing tool list. See TRANSLATIONS below for what IS covered.
//
// How a page uses this:
//   - Any element whose text should be translated gets data-i18n="some.key"
//     (dot-path into TRANSLATIONS) - applyTranslations() sets its
//     textContent. For elements that need real inline markup (a <code> tag,
//     a link) inside the translated text, use data-i18n-html instead, which
//     sets innerHTML - the translation string itself then contains that
//     markup, kept in sync across all three languages by hand.
//   - <div id="lang-switcher"></div> anywhere in the page becomes a row of
//     language toggle buttons once initLanguageSwitcher() runs.
//   - Call initI18n() once at page load (after the DOM the above relies on
//     already exists) - it applies translations, wires the switcher, and
//     sets <html lang="..."> for accessibility/screen readers.
// =============================================================================

const I18N_LANG_KEY = 'mt_toolbox_lang';
const SUPPORTED_LANGS = ['zh', 'en', 'vi'];
const DEFAULT_LANG = 'zh';
const LANG_LABELS = { zh: '中文', en: 'EN', vi: 'VI' };
const LANG_HTML_ATTR = { zh: 'zh-Hant', en: 'en', vi: 'vi' };

const TRANSLATIONS = {
  zh: {
    nav: {
      setupReopen: '工具啟動教學',
      onboardingLink: '工具上架說明',
      backToList: '← 回到工具清單',
    },
    index: {
      subtitle: '產測開發工具啟動器',
      setup: {
        title: '第一次使用？先安裝 Launcher',
        step1Prefix: '下載 Launcher：',
        step2: '雙擊執行一次，跳出「設定完成」的小提示視窗後按確定——這一步會把 <code>real-toolbox://</code> 這個連結類型註冊到你的電腦。',
        step3: '回到這頁點下方任一工具的「啟動」，瀏覽器會詢問是否開啟 real-toolbox 連結，選「開啟」即可，通常之後不會再問。',
        step4: 'Launcher 會自動檢查版本、下載（如有需要）、然後執行工具。第一次下載某個工具時會跳出一個小視窗顯示進度，之後同版本再啟動就不會再出現。',
        step5: 'Launcher 之後有更新時會自動在背景下載並替換自己，不需要手動處理；只有這次的安裝需要手動下載一次。',
        note1: '工具預設安裝在 <code>D:\\___ARC_MT_TOOLS___</code>。想改路徑可執行：<code>real-toolbox-launcher.exe --set-install-dir D:\\你想要的路徑</code>',
        note2: '第一次執行全新的 Launcher 或全新下載的工具時，防毒軟體可能會先掃描檔案，感覺上會多等幾秒鐘，這是正常現象，不代表沒有啟動成功；同一個檔案之後再啟動就不會再等。',
        dismissBtn: '✓ 已完成安裝，不再顯示',
      },
      emptyState: '目前還沒有工具。',
      card: {
        launch: '啟動',
        launching: '啟動中…',
        comingSoon: '即將推出',
        externalLink: '外部連結',
        goto: '前往',
      },
      errorPrefix: '無法載入工具清單：',
    },
    ob: {
      intro: '這份文件是給「想把自己的工具放上 MT Toolbox」的人看的。整套流程設計成<strong>不需要改你的工具本身</strong>，Launcher 也不會有任何針對特定工具寫死的邏輯——你只要照著下面的步驟，把 GitLab 準備好、把資訊交給維護者就完成了。',
      overview: {
        title: '整體流程一覽',
        items: [
          '把你的工具 repo 設成 <strong>Public</strong>（或搬到一個新的 public 專案）',
          '把 build 好的東西打包成一個 <strong>zip</strong>',
          '在 GitLab 建立 <strong>Release</strong>，把 zip 當附件上傳，用 <strong>permalink</strong> 網址',
          '驗證這個 permalink 網址不用登入就能下載',
          '把必要欄位交給 MT Toolbox 維護者，等對方加進 <code>manifest.json</code>',
          '之後每次發新版，只要照常發 Release 就好——<strong>版本號會自動更新，不用再通知任何人</strong>',
        ],
      },
      step1: {
        title: 'Step 1：Repo 要能匿名下載',
        p1: 'Launcher 是在使用者電腦上執行的小程式，它下載你的工具時<strong>不會、也不能幫你登入</strong>。所以你的工具 repo 必須設成 Public，Launcher 才抓得到檔案。',
        p2: '如果你的工具目前放在需要登入的私有專案（例如公司內部的開發用 repo）底下，不用把整個私有專案公開，做法是：<strong>另外開一個獨立的 public 專案</strong>專門放 Release 附件，例如 <code>http://10.118.53.32/tools/&lt;your-project&gt;</code>，跟你私有的開發用 repo 分開。開發還是在私有 repo 進行，只有要發布的 Release 才放到這個 public 專案。',
      },
      step2: {
        title: 'Step 2：把 build 好的東西打包成一個 zip',
        p1: '一個 zip 裡面要包含：',
        item1: '主程式 exe（可以不只一個，見下方「多個進入點」小節）',
        item2: '執行時需要的所有依賴檔案：設定檔（<code>.ini</code>）、資料庫/資料檔（<code>.csv</code> 等）、圖片、DLL 等',
        p2: '不需要包含：原始碼、build 工具本身（例如 PyInstaller 產生的中間檔）。',
        p3: 'Launcher 解壓後，會在整個解壓出來的資料夾底下<strong>遞迴搜尋</strong>你告訴它的 exe 檔名，所以 zip 裡面要不要包資料夾、要包幾層都沒關係，只要：',
        item3: '你提供給維護者的 exe 檔名跟 zip 裡實際的檔名完全一致（含副檔名、大小寫盡量一致）',
        item4: '同一個 zip 裡不要有兩個同名的 exe（不同資料夾也不行），不然 Launcher 會抓到不確定是哪一個',
      },
      step3: {
        title: 'Step 3：建立 GitLab Release，並使用「永久連結」',
        item1: '打一個 tag，例如 <code>v1.0.0</code>（建議照 <a href="https://semver.org/lang/zh-TW/" target="_blank" rel="noopener">SemVer</a> 規則：破壞性變更升 MAJOR、加功能升 MINOR、修 bug 升 PATCH）',
        item2: '在這個 tag 上建立一個 GitLab Release',
        item3: '把打包好的 zip 當作 Release 的附件上傳',
        item4Prefix: '之後所有人（包含 Launcher）都要用這個<strong>永久連結</strong>網址去下載，而不是某個特定版本的連結：',
        item4Suffix: '這個網址的意思是「這個專案最新一個 Release 的這個附件」，所以你以後每次發新版，只要照常打新 tag、建新 Release、上傳同名的 zip，這個網址完全不用改，永遠自動指向最新版。',
      },
      step4: {
        title: 'Step 4：驗證匿名下載（很重要，不要跳過）',
        p1: '找一台<strong>沒登入</strong>的瀏覽器（或直接開無痕視窗）貼上你的 permalink 網址，確認：',
        item1: '不會被導去登入頁（<code>/users/sign_in</code>）',
        item2: '可以直接觸發下載，或至少回應 200',
        p2: '如果你有終端機，也可以直接測試（<code>-L</code> 會跟著轉址）：',
        p3: '看到 <code>200</code> 才算過關。如果看到 <code>302</code> 或被導到登入頁，代表這個專案還不是 Public，或路徑打錯了——這一步沒測過，Launcher 到使用者端一定會下載失敗。',
      },
      step5: {
        title: 'Step 5：把這些資訊交給 MT Toolbox 維護者',
        th1: '欄位', th2: '說明', th3: '範例',
        row1c1: 'id', row1c2: '工具的唯一代號，只能用英數字和底線，之後會出現在啟動連結裡',
        row2c1: '顯示名稱', row2c2: '畫面上要顯示的名稱',
        row3c1: '簡短描述', row3c2: '一兩句話說明工具做什麼；可以直接給 README 內容，維護者會幫忙摘要',
        row4c1: '版本號', row4c2: '對應你目前的 release tag 就好（例如 1.0.0）；這個欄位只影響網頁上顯示的版本字樣，之後會過時也沒關係，見下方說明',
        row5c1: '下載連結', row5c2: 'Step 3 做出來的 permalink 網址',
        row6c1: 'exe 檔名', row6c2: 'zip 解壓後真正要執行的檔案名稱',
        row7c1: '圖示（選填）', row7c2: '想要的話可以從下面的圖示清單挑一個；不指定就用工具名稱前兩個字當預設圖示',
      },
      icons: {
        title: '目前可用的圖示',
        p1Prefix: '圖示來自',
        p1Suffix: '（開源、ISC 授權）。目前系統裡已經有這些可以直接用：',
        camera: '相機／影像相關',
        database: '資料庫／模擬資料',
        fileDiff: '比對／差異',
        radio: 'RF／無線訊號',
        clipboardCheck: '報告／檢查清單／認證',
        box: '一般設備／打包',
        wrench: '維修／工具',
        p2: '想要清單以外的圖示也可以，跟維護者說一聲，只要 Lucide 官網上找得到的 icon 都能加。',
      },
      subTools: {
        title: '如果你的工具有多個進入點（例如一套工具裡有好幾支獨立的 exe）',
        p1: '不用拆成好幾個工具、好幾份 zip。一份 zip、一個版本號、一個下載連結就好，只要額外告訴維護者每個子程式的：',
        item1: '子程式代號（例如 <code>cam</code>）',
        item2: '顯示名稱（例如「CAM 相機能力偵測」）',
        item3: '對應的 exe 檔名（例如 <code>CAM.exe</code>）',
        p2: '畫面上會變成同一張卡片裡有好幾顆啟動按鈕，各自對應一支 exe，共用同一個版本號跟下載連結。',
      },
      linkTool: {
        title: '如果你要放的其實只是一個外部網址（不是可執行的工具）',
        p1: '例如某個內部系統的網頁入口，不需要 zip、不需要 exe，只要給維護者那個網址就好。畫面上會顯示成「前往」按鈕，直接開新分頁連過去，完全不會透過 Launcher。',
      },
      example: {
        title: 'manifest.json 範例',
        intro: '維護者實際會把你的資料寫成類似這樣的一筆（你不用自己動手改這個檔案，這裡列出來只是讓你知道你提供的資訊最後會變成什麼樣子）：',
        single: '一般單一 exe 工具：',
        multi: '多個進入點的工具：',
        link: '純外部連結：',
      },
      newVersion: {
        title: '之後每次發新版，要做什麼？',
        p1: '只要照常打新 tag、建新 Release、上傳新 zip（permalink 網址不用變）就好。<strong>不需要再通知維護者更新 manifest.json。</strong>',
        p2: '原理：Launcher 每次啟動你的工具前，不是看 <code>manifest.json</code> 裡寫死的版本號，而是直接去問你的 Release permalink「你現在實際指到哪一個 tag」，有新版就自動抓新的下來、換掉舊的再執行。<code>manifest.json</code> 裡的版本號只影響網頁卡片上顯示的字樣，就算過時了也不影響使用者實際抓到、跑到的一定是最新版。',
        note: '（這個自動判斷機制只認得「GitLab Release permalink」這種下載連結格式。如果你的下載連結不是這個格式，Launcher 會退回去讀 <code>manifest.json</code> 裡寫的版本號，這種情況下發新版還是要麻煩通知維護者更新。）',
        p3: '另外 Launcher 也會順便檢查下載連結的 ETag／檔案大小有沒有變——所以就算你不小心「內容換了但忘記打新 tag」，Launcher 還是會抓到差異、自動重新下載，不會一直卡在舊版本。當然還是建議每次異動都老實打新版號，這只是多一層保險。',
      },
      checklist: {
        title: '上架前檢查清單',
        item1: 'Repo（或另外開的 public 專案）設成 Public 了嗎？',
        item2: 'zip 裡的 exe 檔名跟你要提供的 <code>exe_name</code> 完全一致嗎？',
        item3: 'zip 裡有沒有依賴檔案漏包（ini／csv／DLL／圖片）？',
        item4: '用沒登入的瀏覽器或 <code>curl</code> 測過 permalink 網址，回應是 200 嗎？',
        item5: 'exe 可以在乾淨的資料夾（沒有你開發機上其他殘留檔案）直接執行嗎？',
      },
      help: {
        title: '有問題怎麼辦？',
        p1: '照著上面步驟卡關、或不確定怎麼設定 GitLab Release，直接找 MT Toolbox 維護者（<code>real_chang</code>）就好。',
      },
    },
  },

  en: {
    nav: {
      setupReopen: 'Launcher Setup Guide',
      onboardingLink: 'Add a Tool',
      backToList: '← Back to tool list',
    },
    index: {
      subtitle: 'Production-Test Dev Tool Launcher',
      setup: {
        title: 'First time here? Install the Launcher first',
        step1Prefix: 'Download the Launcher: ',
        step2: 'Run it once (double-click). When the "Setup complete" prompt appears, click OK - this registers the <code>real-toolbox://</code> link type on your computer.',
        step3: 'Come back to this page and click "Launch" on any tool. If your browser asks whether to open a real-toolbox link, choose "Open" - it usually only asks once.',
        step4: 'The Launcher checks the version automatically, downloads if needed, then runs the tool. The first time it downloads a given tool, a small progress window appears; it won’t show again for the same version.',
        step5: 'The Launcher updates itself automatically in the background when a new version is available - no action needed. Only this first install needs a manual download.',
        note1: 'Tools install to <code>D:\\___ARC_MT_TOOLS___</code> by default. To change the path, run: <code>real-toolbox-launcher.exe --set-install-dir D:\\your\\path</code>',
        note2: 'The first time a brand-new Launcher or a freshly downloaded tool runs, antivirus software may scan the file first, which can take a few extra seconds - this is normal and doesn’t mean it failed. The same file won’t be scanned again next time.',
        dismissBtn: '✓ Already set up, don’t show again',
      },
      emptyState: 'No tools yet.',
      card: {
        launch: 'Launch',
        launching: 'Launching…',
        comingSoon: 'Coming soon',
        externalLink: 'External link',
        goto: 'Open',
      },
      errorPrefix: 'Failed to load the tool list: ',
    },
    ob: {
      intro: 'This guide is for anyone who wants to add their own tool to MT Toolbox. The whole process is designed so <strong>you never have to modify your tool itself</strong>, and the Launcher never has any tool-specific logic hard-coded into it - just follow the steps below to prepare your GitLab project and hand the details to the maintainer.',
      overview: {
        title: 'Overview',
        items: [
          'Make your tool’s repo <strong>Public</strong> (or move it to a new public project)',
          'Package your built output into a <strong>zip</strong>',
          'Create a GitLab <strong>Release</strong>, upload the zip as an asset, and use its <strong>permalink</strong> URL',
          'Verify the permalink URL can be downloaded without logging in',
          'Send the required fields to the MT Toolbox maintainer to add to <code>manifest.json</code>',
          'From then on, just cut a normal Release for every new version - <strong>the version number updates itself, no need to notify anyone</strong>',
        ],
      },
      step1: {
        title: 'Step 1: The repo needs to be downloadable anonymously',
        p1: 'The Launcher is a small program that runs on the end user’s machine - it <strong>can’t and won’t</strong> log in on their behalf when downloading your tool. So your tool’s repo must be set to Public, or the Launcher can’t reach the file.',
        p2: 'If your tool currently lives in a private project that requires login (e.g. an internal dev repo), you don’t need to make the whole project public - instead, <strong>create a separate public project</strong> just for hosting the Release asset, e.g. <code>http://10.118.53.32/tools/&lt;your-project&gt;</code>, kept apart from your private dev repo. Development still happens in the private repo; only the Releases you actually publish go into this public project.',
      },
      step2: {
        title: 'Step 2: Package your build into a zip',
        p1: 'One zip should contain:',
        item1: 'The main exe(s) - can be more than one, see "Multiple entry points" below',
        item2: 'Every dependency it needs at runtime: config files (<code>.ini</code>), database/data files (<code>.csv</code>, etc.), images, DLLs, and so on',
        p2: 'Not needed: source code, or the build tooling itself (e.g. PyInstaller’s intermediate files).',
        p3: 'After extracting, the Launcher <strong>recursively searches</strong> the whole extracted folder for the exe filename you gave it, so it doesn’t matter whether or how deeply the zip nests folders, as long as:',
        item3: 'The exe filename you give the maintainer exactly matches the real filename inside the zip (including extension and, as much as possible, letter case)',
        item4: 'There are no two files with the same exe name anywhere in the zip (even in different folders) - otherwise the Launcher can’t tell which one is meant',
      },
      step3: {
        title: 'Step 3: Create a GitLab Release with a "permalink"',
        item1: 'Cut a tag, e.g. <code>v1.0.0</code> (following <a href="https://semver.org/" target="_blank" rel="noopener">SemVer</a> is recommended: MAJOR for breaking changes, MINOR for new features, PATCH for bug fixes)',
        item2: 'Create a GitLab Release on that tag',
        item3: 'Upload the packaged zip as the Release’s asset',
        item4Prefix: 'Everyone - including the Launcher - should then download it via the <strong>permalink</strong> URL, not a version-specific link:',
        item4Suffix: 'This URL means "this project’s newest Release, this asset" - so every time you ship a new version, just tag, create a Release, and upload a zip with the same filename as usual; this URL never has to change and always points at the latest version automatically.',
      },
      step4: {
        title: 'Step 4: Verify anonymous downloads (important - don’t skip this)',
        p1: 'Using a browser that’s <strong>not logged in</strong> (or a private/incognito window), open your permalink URL and confirm:',
        item1: 'It does NOT redirect to a login page (<code>/users/sign_in</code>)',
        item2: 'It either triggers a download directly, or at least responds with 200',
        p2: 'If you have a terminal, you can test it directly (<code>-L</code> follows redirects):',
        p3: 'A <code>200</code> means it’s working. If you see <code>302</code> or get redirected to a login page, the project still isn’t Public, or the path is wrong - if this step hasn’t been verified, the Launcher will fail to download on the end user’s machine.',
      },
      step5: {
        title: 'Step 5: Send this information to the MT Toolbox maintainer',
        th1: 'Field', th2: 'Description', th3: 'Example',
        row1c1: 'id', row1c2: 'A unique identifier - letters/numbers/underscores only. Shows up in the launch link.',
        row2c1: 'Display name', row2c2: 'The name shown on the page',
        row3c1: 'Short description', row3c2: 'A sentence or two about what the tool does - README content works fine, the maintainer will summarize it',
        row4c1: 'Version number', row4c2: 'Your current release tag is fine (e.g. 1.0.0). This only affects the version text shown on the page - it’s OK if it goes stale later, see below',
        row5c1: 'Download link', row5c2: 'The permalink URL from Step 3',
        row6c1: 'exe filename', row6c2: 'The actual file to run after the zip is extracted',
        row7c1: 'Icon (optional)', row7c2: 'Pick one from the list below if you like; otherwise the first two characters of the tool name are used as a fallback',
      },
      icons: {
        title: 'Currently available icons',
        p1Prefix: 'Icons come from',
        p1Suffix: '(open source, ISC license). These are already available:',
        camera: 'Camera / imaging',
        database: 'Database / simulated data',
        fileDiff: 'Comparison / diff',
        radio: 'RF / wireless signal',
        clipboardCheck: 'Reports / checklists / certification',
        box: 'General equipment / packaging',
        wrench: 'Maintenance / tools',
        p2: 'Icons outside this list are fine too - just mention it to the maintainer; anything findable on the Lucide site can be added.',
      },
      subTools: {
        title: 'If your tool has multiple entry points (e.g. several independent exes in one package)',
        p1: 'No need to split it into multiple tools or multiple zips. One zip, one version, one download link - just also tell the maintainer, for each sub-program:',
        item1: 'A sub-id (e.g. <code>cam</code>)',
        item2: 'A display name (e.g. "CAM Camera Capability Check")',
        item3: 'The matching exe filename (e.g. <code>CAM.exe</code>)',
        p2: 'The page will then show several launch buttons on the same card, each launching a different exe, sharing one version and download link.',
      },
      linkTool: {
        title: 'If what you want to add is really just an external URL (not something to run)',
        p1: 'For example, a web front-end to some internal system - no zip, no exe needed, just give the maintainer the URL. It’ll appear as an "Open" button that opens a new tab directly - the Launcher isn’t involved at all.',
      },
      example: {
        title: 'manifest.json examples',
        intro: 'The maintainer will actually write your data as an entry that looks something like this (you don’t need to edit this file yourself - this is just so you can see what your info turns into):',
        single: 'A normal, single-exe tool:',
        multi: 'A tool with multiple entry points:',
        link: 'A plain external link:',
      },
      newVersion: {
        title: 'What do I do every time I ship a new version?',
        p1: 'Just tag, create a Release, and upload the new zip as usual (the permalink URL doesn’t change). <strong>No need to notify the maintainer to update manifest.json.</strong>',
        p2: 'Why: before launching your tool, the Launcher doesn’t read the hard-coded version number in <code>manifest.json</code> - it asks your Release permalink directly "what tag are you actually pointing at right now," and downloads the new one automatically whenever it differs. The version number in <code>manifest.json</code> only affects the text shown on the web card; even if it goes stale, users still always get the actual latest version.',
        note: '(This automatic check only understands the "GitLab Release permalink" download URL format. If your download URL isn’t in that format, the Launcher falls back to the version written in <code>manifest.json</code>, and in that case you do still need to notify the maintainer on each new release.)',
        p3: 'The Launcher also checks the download URL’s ETag/file size - so even if you accidentally "change the content but forget to bump the tag," it’ll still notice the difference and re-download automatically, rather than getting stuck on the old version forever. That said, it’s still best practice to bump the version tag honestly on every real change - this is just an extra safety net.',
      },
      checklist: {
        title: 'Pre-launch checklist',
        item1: 'Is the repo (or the separate public project) set to Public?',
        item2: 'Does the exe filename inside the zip exactly match the <code>exe_name</code> you’re providing?',
        item3: 'Are any dependency files missing from the zip (ini/csv/DLL/images)?',
        item4: 'Have you tested the permalink URL with a logged-out browser or <code>curl</code>, and gotten a 200?',
        item5: 'Does the exe run correctly from a clean folder (without other leftover files from your dev machine)?',
      },
      help: {
        title: 'Something not working?',
        p1: 'If you get stuck on any of the steps above, or aren’t sure how to set up a GitLab Release, just reach out to the MT Toolbox maintainer (<code>real_chang</code>).',
      },
    },
  },

  vi: {
    nav: {
      setupReopen: 'Hướng dẫn cài Launcher',
      onboardingLink: 'Thêm công cụ',
      backToList: '← Quay lại danh sách công cụ',
    },
    index: {
      subtitle: 'Trình khởi chạy công cụ phát triển kiểm thử sản xuất',
      setup: {
        title: 'Lần đầu sử dụng? Hãy cài đặt Launcher trước',
        step1Prefix: 'Tải Launcher: ',
        step2: 'Nhấp đúp để chạy một lần. Khi hộp thoại "Thiết lập hoàn tất" hiện ra, bấm OK - bước này sẽ đăng ký loại liên kết <code>real-toolbox://</code> trên máy tính của bạn.',
        step3: 'Quay lại trang này và bấm "Khởi động" ở bất kỳ công cụ nào. Nếu trình duyệt hỏi có muốn mở liên kết real-toolbox không, chọn "Mở" - thường chỉ hỏi một lần.',
        step4: 'Launcher sẽ tự động kiểm tra phiên bản, tải xuống nếu cần, rồi chạy công cụ. Lần đầu tải một công cụ sẽ hiện một cửa sổ nhỏ hiển thị tiến trình; các lần sau với cùng phiên bản sẽ không hiện lại.',
        step5: 'Sau này khi có bản cập nhật, Launcher sẽ tự động tải và thay thế chính nó ở chế độ nền, không cần thao tác gì; chỉ có lần cài đặt đầu tiên này mới cần tải thủ công.',
        note1: 'Công cụ sẽ được cài mặc định vào <code>D:\\___ARC_MT_TOOLS___</code>. Muốn đổi đường dẫn, chạy: <code>real-toolbox-launcher.exe --set-install-dir D:\\đường_dẫn_bạn_muốn</code>',
        note2: 'Lần đầu chạy một Launcher hoàn toàn mới hoặc một công cụ vừa tải về, phần mềm diệt virus có thể quét file trước, khiến bạn phải đợi thêm vài giây - đây là hiện tượng bình thường, không có nghĩa là khởi động thất bại; cùng một file thì lần sau sẽ không phải đợi nữa.',
        dismissBtn: '✓ Đã cài đặt xong, không hiển thị lại',
      },
      emptyState: 'Hiện chưa có công cụ nào.',
      card: {
        launch: 'Khởi động',
        launching: 'Đang khởi động…',
        comingSoon: 'Sắp ra mắt',
        externalLink: 'Liên kết ngoài',
        goto: 'Đi tới',
      },
      errorPrefix: 'Không thể tải danh sách công cụ: ',
    },
    ob: {
      intro: 'Tài liệu này dành cho những ai muốn đưa công cụ của mình lên MT Toolbox. Toàn bộ quy trình được thiết kế để <strong>bạn không cần sửa đổi công cụ của mình</strong>, và Launcher cũng không có bất kỳ logic nào viết cứng riêng cho từng công cụ - bạn chỉ cần làm theo các bước dưới đây để chuẩn bị GitLab và gửi thông tin cho người quản trị là xong.',
      overview: {
        title: 'Tổng quan quy trình',
        items: [
          'Đặt repo công cụ của bạn thành <strong>Public</strong> (hoặc chuyển sang một project public mới)',
          'Đóng gói kết quả build thành một file <strong>zip</strong>',
          'Tạo <strong>Release</strong> trên GitLab, tải zip lên làm tệp đính kèm, dùng URL <strong>permalink</strong>',
          'Xác nhận URL permalink có thể tải xuống mà không cần đăng nhập',
          'Gửi các thông tin cần thiết cho người quản trị MT Toolbox để thêm vào <code>manifest.json</code>',
          'Từ đó về sau, mỗi khi ra bản mới chỉ cần phát hành Release như bình thường - <strong>số phiên bản sẽ tự động cập nhật, không cần báo cho ai nữa</strong>',
        ],
      },
      step1: {
        title: 'Bước 1: Repo phải tải xuống được ẩn danh',
        p1: 'Launcher là chương trình nhỏ chạy trên máy của người dùng - nó <strong>không thể và sẽ không</strong> đăng nhập giúp bạn khi tải công cụ. Vì vậy repo công cụ của bạn phải được đặt thành Public thì Launcher mới lấy được file.',
        p2: 'Nếu công cụ của bạn hiện đang nằm trong một project riêng tư cần đăng nhập (ví dụ repo phát triển nội bộ), bạn không cần công khai toàn bộ project riêng tư đó - thay vào đó: <strong>mở một project public riêng biệt</strong> chỉ để chứa tệp đính kèm Release, ví dụ <code>http://10.118.53.32/tools/&lt;your-project&gt;</code>, tách biệt với repo phát triển riêng tư của bạn. Việc phát triển vẫn diễn ra ở repo riêng tư, chỉ có các Release chính thức mới đưa vào project public này.',
      },
      step2: {
        title: 'Bước 2: Đóng gói kết quả build thành một file zip',
        p1: 'Một file zip cần chứa:',
        item1: 'File exe chính (có thể nhiều hơn một, xem mục "Nhiều điểm khởi chạy" bên dưới)',
        item2: 'Tất cả các tệp phụ thuộc cần khi chạy: tệp cấu hình (<code>.ini</code>), tệp dữ liệu/cơ sở dữ liệu (<code>.csv</code>...), hình ảnh, DLL, v.v.',
        p2: 'Không cần bao gồm: mã nguồn, hay bản thân công cụ build (ví dụ các tệp trung gian do PyInstaller tạo ra).',
        p3: 'Sau khi giải nén, Launcher sẽ <strong>tìm kiếm đệ quy</strong> trong toàn bộ thư mục giải nén để tìm tên file exe bạn đã cung cấp, nên zip có bao nhiêu thư mục con hay lồng bao nhiêu lớp cũng không sao, miễn là:',
        item3: 'Tên file exe bạn cung cấp cho người quản trị khớp hoàn toàn với tên file thực tế trong zip (bao gồm phần mở rộng, và nên khớp cả chữ hoa/thường)',
        item4: 'Trong cùng một zip không có hai file exe trùng tên (kể cả ở thư mục khác nhau), nếu không Launcher sẽ không biết chọn file nào',
      },
      step3: {
        title: 'Bước 3: Tạo GitLab Release và sử dụng "liên kết cố định" (permalink)',
        item1: 'Tạo một tag, ví dụ <code>v1.0.0</code> (khuyến nghị theo quy tắc <a href="https://semver.org/" target="_blank" rel="noopener">SemVer</a>: thay đổi phá vỡ tương thích thì tăng MAJOR, thêm tính năng thì tăng MINOR, sửa lỗi thì tăng PATCH)',
        item2: 'Tạo một GitLab Release trên tag đó',
        item3: 'Tải file zip đã đóng gói lên làm tệp đính kèm của Release',
        item4Prefix: 'Sau đó tất cả mọi người (kể cả Launcher) đều phải dùng URL <strong>permalink</strong> này để tải xuống, chứ không phải liên kết của một phiên bản cụ thể:',
        item4Suffix: 'URL này có nghĩa là "tệp đính kèm này của Release mới nhất trong project này" - vì vậy mỗi lần ra bản mới, bạn chỉ cần tạo tag mới, tạo Release mới, tải lên zip cùng tên như thường lệ, URL này hoàn toàn không cần đổi, luôn tự động trỏ đến phiên bản mới nhất.',
      },
      step4: {
        title: 'Bước 4: Xác minh tải xuống ẩn danh (rất quan trọng, đừng bỏ qua)',
        p1: 'Dùng một trình duyệt <strong>chưa đăng nhập</strong> (hoặc mở cửa sổ ẩn danh) dán URL permalink của bạn vào, xác nhận:',
        item1: 'Không bị chuyển hướng đến trang đăng nhập (<code>/users/sign_in</code>)',
        item2: 'Có thể tải xuống trực tiếp, hoặc ít nhất trả về mã 200',
        p2: 'Nếu có terminal, bạn cũng có thể kiểm tra trực tiếp (<code>-L</code> sẽ theo chuyển hướng):',
        p3: 'Thấy mã <code>200</code> mới coi là đạt. Nếu thấy <code>302</code> hoặc bị chuyển đến trang đăng nhập, nghĩa là project chưa Public, hoặc đường dẫn sai - nếu bước này chưa được kiểm tra, Launcher chắc chắn sẽ tải xuống thất bại ở phía người dùng.',
      },
      step5: {
        title: 'Bước 5: Gửi các thông tin sau cho người quản trị MT Toolbox',
        th1: 'Trường thông tin', th2: 'Mô tả', th3: 'Ví dụ',
        row1c1: 'id', row1c2: 'Mã định danh duy nhất của công cụ, chỉ dùng chữ/số/gạch dưới, sau này sẽ xuất hiện trong liên kết khởi chạy',
        row2c1: 'Tên hiển thị', row2c2: 'Tên sẽ hiển thị trên màn hình',
        row3c1: 'Mô tả ngắn', row3c2: 'Một hai câu mô tả công cụ làm gì; có thể đưa thẳng nội dung README, người quản trị sẽ tóm tắt giúp',
        row4c1: 'Số phiên bản', row4c2: 'Dùng đúng tag release hiện tại là được (ví dụ 1.0.0); trường này chỉ ảnh hưởng đến chữ hiển thị trên trang, sau này cũ đi cũng không sao, xem giải thích bên dưới',
        row5c1: 'Liên kết tải xuống', row5c2: 'URL permalink tạo ở Bước 3',
        row6c1: 'Tên file exe', row6c2: 'Tên file thực sự cần chạy sau khi giải nén zip',
        row7c1: 'Biểu tượng (tùy chọn)', row7c2: 'Có thể chọn một biểu tượng từ danh sách bên dưới nếu muốn; nếu không chỉ định sẽ dùng hai ký tự đầu của tên công cụ làm biểu tượng mặc định',
      },
      icons: {
        title: 'Các biểu tượng hiện có',
        p1Prefix: 'Biểu tượng lấy từ',
        p1Suffix: '(mã nguồn mở, giấy phép ISC). Hiện đã có sẵn các biểu tượng sau:',
        camera: 'Máy ảnh／hình ảnh',
        database: 'Cơ sở dữ liệu／dữ liệu mô phỏng',
        fileDiff: 'So sánh／khác biệt',
        radio: 'RF／tín hiệu không dây',
        clipboardCheck: 'Báo cáo／danh sách kiểm tra／chứng nhận',
        box: 'Thiết bị thông thường／đóng gói',
        wrench: 'Bảo trì／công cụ',
        p2: 'Muốn dùng biểu tượng ngoài danh sách này cũng được, chỉ cần báo cho người quản trị - bất kỳ icon nào tìm thấy trên trang Lucide đều có thể thêm vào.',
      },
      subTools: {
        title: 'Nếu công cụ của bạn có nhiều điểm khởi chạy (ví dụ một bộ công cụ gồm nhiều file exe độc lập)',
        p1: 'Không cần tách thành nhiều công cụ, nhiều file zip riêng. Chỉ cần một zip, một số phiên bản, một liên kết tải xuống, và cung cấp thêm cho người quản trị thông tin của từng chương trình con:',
        item1: 'Mã định danh chương trình con (ví dụ <code>cam</code>)',
        item2: 'Tên hiển thị (ví dụ "CAM Kiểm tra khả năng camera")',
        item3: 'Tên file exe tương ứng (ví dụ <code>CAM.exe</code>)',
        p2: 'Trên màn hình sẽ hiển thị nhiều nút khởi động trong cùng một thẻ, mỗi nút tương ứng một file exe, dùng chung một số phiên bản và liên kết tải xuống.',
      },
      linkTool: {
        title: 'Nếu thứ bạn muốn thêm thực ra chỉ là một URL bên ngoài (không phải công cụ có thể chạy)',
        p1: 'Ví dụ như trang web của một hệ thống nội bộ nào đó - không cần zip, không cần exe, chỉ cần cung cấp URL đó cho người quản trị. Trên màn hình sẽ hiển thị thành nút "Đi tới", mở trực tiếp một tab mới, hoàn toàn không thông qua Launcher.',
      },
      example: {
        title: 'Ví dụ manifest.json',
        intro: 'Người quản trị sẽ viết dữ liệu của bạn thành một mục tương tự như thế này (bạn không cần tự sửa file này, liệt kê ở đây chỉ để bạn biết thông tin mình cung cấp cuối cùng sẽ trông như thế nào):',
        single: 'Công cụ một exe thông thường:',
        multi: 'Công cụ có nhiều điểm khởi chạy:',
        link: 'Chỉ là liên kết ngoài:',
      },
      newVersion: {
        title: 'Mỗi lần ra bản mới sau này cần làm gì?',
        p1: 'Chỉ cần tạo tag mới, tạo Release mới, tải zip mới lên như bình thường (URL permalink không đổi). <strong>Không cần báo người quản trị cập nhật manifest.json nữa.</strong>',
        p2: 'Nguyên lý: trước khi khởi chạy công cụ của bạn, Launcher không đọc số phiên bản viết cứng trong <code>manifest.json</code>, mà trực tiếp hỏi permalink Release của bạn "hiện tại đang trỏ đến tag nào" - có bản mới sẽ tự động tải về, thay bản cũ rồi chạy. Số phiên bản trong <code>manifest.json</code> chỉ ảnh hưởng đến chữ hiển thị trên thẻ công cụ trên trang web, dù có cũ đi cũng không ảnh hưởng đến việc người dùng thực sự luôn tải và chạy phiên bản mới nhất.',
        note: '(Cơ chế tự động này chỉ nhận diện được định dạng liên kết tải xuống kiểu "GitLab Release permalink". Nếu liên kết tải xuống của bạn không theo định dạng này, Launcher sẽ quay về đọc số phiên bản viết trong <code>manifest.json</code>, trường hợp này khi ra bản mới vẫn cần báo người quản trị cập nhật.)',
        p3: 'Ngoài ra Launcher cũng sẽ kiểm tra ETag／kích thước file của liên kết tải xuống - nên dù bạn lỡ "thay đổi nội dung nhưng quên tạo tag mới", Launcher vẫn sẽ phát hiện sự khác biệt và tự động tải lại, không bị kẹt mãi ở phiên bản cũ. Tuy nhiên vẫn khuyến khích bạn tạo tag phiên bản mới một cách trung thực mỗi khi có thay đổi thực sự, đây chỉ là một lớp bảo hiểm thêm.',
      },
      checklist: {
        title: 'Danh sách kiểm tra trước khi lên kệ',
        item1: 'Repo (hoặc project public riêng biệt) đã được đặt thành Public chưa?',
        item2: 'Tên file exe trong zip có khớp hoàn toàn với <code>exe_name</code> bạn cung cấp không?',
        item3: 'Zip có thiếu tệp phụ thuộc nào không (ini／csv／DLL／hình ảnh)?',
        item4: 'Đã dùng trình duyệt chưa đăng nhập hoặc <code>curl</code> để kiểm tra URL permalink, kết quả trả về là 200 chưa?',
        item5: 'File exe có chạy được trực tiếp trong một thư mục sạch (không có các tệp còn sót lại khác từ máy phát triển của bạn) không?',
      },
      help: {
        title: 'Gặp vấn đề thì làm sao?',
        p1: 'Nếu bị kẹt ở bước nào trên đây, hoặc không chắc cách thiết lập GitLab Release, cứ liên hệ trực tiếp với người quản trị MT Toolbox (<code>real_chang</code>).',
      },
    },
  },
};

function getLang() {
  const stored = localStorage.getItem(I18N_LANG_KEY);
  return SUPPORTED_LANGS.includes(stored) ? stored : DEFAULT_LANG;
}

function resolveKey(dict, key) {
  return key.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), dict);
}

function t(key) {
  const lang = getLang();
  return resolveKey(TRANSLATIONS[lang], key) ?? resolveKey(TRANSLATIONS[DEFAULT_LANG], key) ?? key;
}

function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.getAttribute('data-i18n'));
  });
  document.querySelectorAll('[data-i18n-html]').forEach((el) => {
    el.innerHTML = t(el.getAttribute('data-i18n-html'));
  });
  document.documentElement.lang = LANG_HTML_ATTR[getLang()];
}

function setLang(lang) {
  if (!SUPPORTED_LANGS.includes(lang)) return;
  localStorage.setItem(I18N_LANG_KEY, lang);
  applyTranslations();
  updateLangSwitcherUI();
  document.dispatchEvent(new CustomEvent('mt-toolbox-langchange', { detail: { lang } }));
}

function updateLangSwitcherUI() {
  const lang = getLang();
  document.querySelectorAll('.lang-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.lang === lang);
  });
}

function initLanguageSwitcher() {
  const container = document.getElementById('lang-switcher');
  if (!container) return;
  container.innerHTML = SUPPORTED_LANGS
    .map((lang) => `<button class="lang-btn" data-lang="${lang}" type="button">${LANG_LABELS[lang]}</button>`)
    .join('');
  container.addEventListener('click', (e) => {
    const btn = e.target.closest('.lang-btn');
    if (!btn) return;
    setLang(btn.dataset.lang);
  });
  updateLangSwitcherUI();
}

function initI18n() {
  applyTranslations();
  initLanguageSwitcher();
}

initI18n();
