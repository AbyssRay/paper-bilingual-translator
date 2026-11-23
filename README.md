# 學術期刊繁體中文精譯與離線雙語閱讀器 (`paper-bilingual-translator`)

本專案採用**「翻譯產製」與「閱讀渲染」解耦的雙軌架構**，將英文雙欄學術期刊 PDF 精譯為台灣慣用學術繁體中文 Markdown（`.md`），並搭配完全離線（Zero-CDN）的單一 HTML 雙欄閱讀器進行同步對照閱讀。

```text
[Google Drive: Paper_Translate (僅第一層 PDF，忽略子資料夾)]
   │
   ├──► (軌道 A: extract_blocks.py + paper-bilingual-translator Skill) ──► [帶 sync 座標的 *_zh.md]
   │                                                                                 │
   └──► (軌道 B: BilingualReader.html — Zero-CDN 單一離線網頁) ◄─────────────────────┘
                     │
                     ▼
        [左：原版 PDF + 透明感應框 / 右：繁中譯文 + KaTeX 公式]
                 (支援左指右亮、右指左亮雙向同步對齊)
```

---

## 專案結構

```text
.
├── BilingualReader.html                     # 軌道 B：Zero-CDN 離線單檔雙欄閱讀器（目前版本：V2）
├── CHANGELOG.md                             # 版本更新紀錄
├── paper-bilingual-translator/              # 軌道 A：Antigravity Agent Skill
│   ├── SKILL.md                             # 三階段精譯工作流與 Google Drive 讀取規範
│   └── scripts/
│       └── extract_blocks.py                # PyMuPDF 雙欄座標提取腳本
├── requirements.txt                         # Python 相依套件 (pymupdf)
└── README.md
```

---

## 完整工作流程（Workflow）

### 1. 前置準備
* **Python 環境**：安裝 `PyMuPDF`（用於 `extract_blocks.py`）：
  ```bash
  pip install -r requirements.txt
  ```
* **Google Drive 來源規範**：
  * 欲翻譯的英文期刊 `.pdf` 請直接放置於 Google Drive 的 **`Paper_Translate`** 資料夾**第一層**。
  * **僅讀取 `Paper_Translate` 資料夾內的直接檔案（Non-recursive），更深層的子資料夾將自動忽略不予處理。**

---

### 2. 軌道 A：PDF 座標提取與三階段精譯

#### 步驟 1：提取雙欄文字區塊與正規化座標
```bash
python3 paper-bilingual-translator/scripts/extract_blocks.py "paper.pdf" --format md -o "paper_extracted.md"
```
* 自動過濾頁首、頁尾與頁碼，並還原跨行連字號（hyphenation）。
* 偵測雙欄排版（以全寬標題、摘要、跨欄圖表分段，先左欄由上至下、再右欄由上至下），為每個段落生成 `0.0 ~ 1.0` 正規化座標標記：
  ```markdown
  <!-- sync: {"id": "p1_b12", "page": 1, "bbox": [0.0631, 0.5576, 0.1683, 0.5741]} -->
  ```

#### 步驟 2：三階段學術繁中精譯（`paper-bilingual-translator` Skill）
1. **Pass 1（全域語境與術語抽取）**：閱讀 Title、Abstract、章節標題與 Conclusions，建立英繁專有名詞對照表。
2. **Pass 2（結構化逐節精譯）**：逐節翻譯並完整保留每段上方的 `<!-- sync: ... -->` 標記；首次出現的關鍵術語採「繁體中文（原文）」格式標註。
3. **Pass 3（台灣學術繁中潤飾與公式鎖定）**：強制轉換為台灣慣用學術與工程詞彙（如：雷射、資訊、強健性、擔體、模擬、最佳化），鎖定所有 LaTeX 公式（`$...$`）與文獻引用編號，最終輸出 `<原檔名>_zh.md` 並寫回 `Paper_Translate` 資料夾。

---

### 3. 軌道 B：離線雙欄同步閱讀（`BilingualReader.html`）

1. 直接雙擊本機的 `BilingualReader.html`（支援 `file://` 協議，無需任何網路連線或外部 CDN，內建 `PDF.js`、`marked.js` 與 `KaTeX` 及其字型）。
2. 點擊工具列按鈕（或直接將檔案拖曳進視窗）載入原版 `.pdf` 與翻譯後的 `*_zh.md`。
3. 享受**左指右亮、右指左亮**的雙向懸停高亮與平滑置中捲動對照體驗，並可隨時縮放 PDF、拖曳調整左右欄寬度或切換閱讀設定：
   * 按 **`S`** 鍵可快速開關「同步對齊」，避免滑鼠游標移往工具列時誤觸其他段落而跑開；暫停時會鎖定當前高亮段落，點擊任一段落仍可單次手動對齊。
   * 工具列支援**輸入頁碼按 `Enter` 跳轉**與上／下一頁按鈕，並可按 **`P`** 鍵切換**「符合完整一頁」**（自動依視窗寬高縮放顯示完整單頁，並可用**滑鼠滾輪**或 `PageUp`／`PageDown` 快速翻頁，右側雙向同步時也會自動切頁）。
   * 按 **`B`** 鍵或點擊工具列**「📑 側邊欄」**可開啟／隱藏左側邊欄，檢視**「頁面縮圖」**與**「PDF 書籤目錄」**，點擊即可直接跳轉至對應頁面。
   * 點擊工具列左上角的 **`V2`** 標記可開啟內建的快捷鍵與版本更新紀錄視窗。

---

### 4. 版本發布與雲端同步流程（Release Workflow）

每次更新 `BilingualReader.html` 並推送（`git push`）至 GitHub 時，需同步執行以下發布流程：
1. 更新 `BilingualReader.html` 內的 `<title>`、工具列版本徽章（`V<N>`）與內建版本更新紀錄視窗，並同步維護 [`CHANGELOG.md`](./CHANGELOG.md) 與 `README.md`。
2. 提交並推送變更至 GitHub 遠端儲存庫（`git push`）。
3. 將最新版的 `BilingualReader.html` 更名為 **`BilingualReader_V<版本號>.html`**（例如 `BilingualReader_V2.html`），上傳至 Google Drive 的 **`Paper_Translate` 資料夾主層**（Folder ID: `1tSvWXtaXRlWVBxhE9dV8ABa9OCXloIlI`）：
   ```bash
   cp BilingualReader.html /tmp/BilingualReader_V2.html
   gdrive mutate upload /tmp/BilingualReader_V2.html --parent 1tSvWXtaXRlWVBxhE9dV8ABa9OCXloIlI --mime-type "text/html"
   ```
   （若同版號檔案已存在於主層，則以 `gdrive mutate update <FILE_ID> /tmp/BilingualReader_V<N>.html` 原地更新。）

---

## 版本更新紀錄

目前版本：**V2**（完整變更請見 [`CHANGELOG.md`](./CHANGELOG.md)）。
* **V2 (2026-11-23)**：新增 `S` 鍵「同步對齊」快捷鍵與高亮鎖定、頁碼輸入跳轉與上／下一頁控制、`P` 鍵「符合完整一頁」（支援滑鼠滾輪快速翻頁）、`B` 鍵可隱藏側邊欄（頁面縮圖與 PDF 書籤跳轉）、修正放大 PDF 時水平捲軸無法捲至左右邊界的問題、新增工具列 `V2` 版本更新紀錄視窗，並建立推送同步上傳 `BilingualReader_V<N>.html` 至 Google Drive `Paper_Translate` 主層的發布流程。
* **V1 (2026-11-23)**：初始版本發布（雙欄座標提取、三階段繁中精譯與 Zero-CDN 離線雙欄閱讀器）。
