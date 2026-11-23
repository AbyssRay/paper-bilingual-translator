# 版本更新紀錄（Changelog）

本文件記錄 `paper-bilingual-translator` 與離線雙欄閱讀器 `BilingualReader.html` 的各版本變更。

---

## V2 (2026-11-23)

### `BilingualReader.html`
- **新增「同步對齊」快捷鍵（`S` 鍵）**：按下 `S` 即可隨時開啟或暫停同步對齊，並於畫面底部顯示即時狀態提示，避免將滑鼠游標移往工具列時誤觸其他段落導致畫面跑開。
- **暫停同步時鎖定當前高亮**：關閉同步對齊後，滑鼠懸停不再變更目前高亮的段落或捲動另一欄；若需對齊特定段落，直接點擊該段落仍可單次手動對齊。
- **新增頁碼跳轉與翻頁控制**：工具列新增可輸入頁碼的輸入框（輸入後按 `Enter` 立即跳轉）以及上一頁（`◀`）／下一頁（`▶`）按鈕。
- **新增「單頁檢視」模式切換（`P` 鍵）**：支援在「連續捲動」與「單頁檢視」間快速切換；單頁模式下可使用 `PageUp`／`PageDown` 翻頁，且從右側譯文觸發雙向同步時會自動切換至對應頁碼。
- **修正放大 PDF 時的水平捲軸錯位問題**：修正 `#pdf-container` 在放大後因 Flexbox 置中導致左側頁面邊緣溢出且水平捲軸無法捲動至最左／最右側的問題，並於縮放時保留目前閱讀頁碼。
- **工具列版本標記與內建更新紀錄視窗**：於左上角新增 `V2` 版本徽章，點擊可檢視快捷鍵說明與完整版本更新紀錄（支援 `Esc` 關閉）。

### 文件與發布流程
- 新增 `CHANGELOG.md` 記錄版本演進，並更新 `README.md` 與 `paper-bilingual-translator/SKILL.md`。
- 確立版本發布流程：每次推送新版本至 GitHub 時，同步將最新版 `BilingualReader.html` 更名為 `BilingualReader_V<版本號>.html` 並上傳至 Google Drive `Paper_Translate` 資料夾主層。

---

## V1 (2026-11-23)

### 初始發布
- **軌道 A（PDF 座標提取與三階段精譯）**：提供 `extract_blocks.py` 雙欄正規化座標提取腳本與 `paper-bilingual-translator` 三階段台灣學術繁體中文精譯 Skill。
- **軌道 B（`BilingualReader.html`）**：Zero-CDN 離線單檔雙欄閱讀器（內建 `PDF.js`、`marked.js`、`KaTeX` 與字型，支援 `file://` 本機開啟），支援拖曳載入 PDF 與 `*_zh.md`、雙向懸停高亮與平滑置中捲動、PDF 縮放與左右欄寬度拖曳調整。
