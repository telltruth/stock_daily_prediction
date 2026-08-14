# 台股開盤＋收盤雙預測規格

本規格是 08:30 與 12:55 兩條正式預測 pipeline 的共同輸出與驗證規格。

搭配方式：
- 08:30：`MORNING_PROMPT.md` + `DUAL_PREDICTION_SPEC.md`
- 12:55：`NOON_PROMPT.md` / `PROMPT.md` + `DUAL_PREDICTION_SPEC.md`

若個別 Prompt 與本規格在「輸出格式、機率單位、預測目標、基準價、樣本不可修改」上衝突，以本規格為準。

## 1. 統一預測目標

每一份正式預測都必須同時預測同一個 `target_date` 的兩個事件：

### A. 開盤方向
- 基準：前一個台股交易日的官方收盤價 `reference_close`
- `open_bullish`：`target_date` 的 TAIEX 官方開盤價 > `reference_close`
- `open_bearish`：`target_date` 的 TAIEX 官方開盤價 < `reference_close`
- 同時預測開盤跳空幅度區間：`(target_open / reference_close - 1) * 100%`

### B. 收盤方向
- 基準：同一個 `reference_close`
- `close_bullish`：`target_date` 的 TAIEX 官方收盤價 > `reference_close`
- `close_bearish`：`target_date` 的 TAIEX 官方收盤價 < `reference_close`
- 同時預測收盤報酬區間：`(target_close / reference_close - 1) * 100%`

開盤與收盤各自必須輸出偏多／偏空機率，且各自合計 100%。不能用一組機率代表兩者。

### Exact-flat 邊界案例
若實際官方開盤價或收盤價恰好等於 `reference_close`：
- 該 leg 的實際方向標記為 `flat`。
- direction hit 與 Brier Score 記為 `N/A`，不得硬塞成 bullish 或 bearish。
- range hit 仍照實際報酬 `0.0%` 驗證。
- `flat` 是驗證結果的邊界狀態，不代表正式預測可以省略 bull / bear 機率；預測時仍必須輸出兩者且合計 1.00。

## 2. 08:30 正式預測

`run_type: scheduled_0830`

- 僅在台股實際交易日執行。
- `target_date = 今天`。
- 預測今天 09:00 開盤與今天 13:30 收盤。
- 固定 `information_cutoff = target_date 08:30:00+08:00`。
- 即使實際 automation 執行／搜尋時間稍晚，也不得使用 cutoff 之後才可得的資訊。
- 主要使用：昨夜 S&P 500、Nasdaq、SOX、TSMC ADR、NVIDIA/AMD/Broadcom/Micron、台指期夜盤、美元、USD/TWD、2Y/10Y 美債殖利率、VIX/MOVE、Brent/WTI、戰爭與地緣政治、當日上午最新亞洲期貨與重大公司消息。
- 對「開盤」而言，隔夜市場、台指期夜盤、TSMC ADR、USD/TWD 權重應高於中長期基本面。
- 對「收盤」而言，除隔夜資訊外，也要考慮台股近期籌碼、技術面、估值、事件風險與可能的日內均值回歸。
- 執行前若 `reports/YYYYMMDD_0830.md` 已存在，必須 `skipped_duplicate`，不得覆寫或產生第二個正式樣本。
- `reference_close` 必須是前一個實際交易日的 TAIEX 官方收盤價；可信來源全部失敗時必須 `failed_data_source`，不得猜測並不得建立正式 report。

## 3. 12:55 正式預測

`run_type: scheduled_1255`

- 僅在台股實際交易日執行。
- `target_date = 下一個實際台股交易日`。
- 同時預測該日 09:00 開盤與 13:30 收盤。
- 除 `PROMPT.md` 的完整宏觀／戰爭／Fed／油價／財報／籌碼框架外，必須加入今天 09:00~12:55 的 TAIEX、台積電、主要權值、成交量、市場廣度、族群輪動、台指期與匯率盤中結構。
- 注意：12:55 時「今天官方收盤」尚未形成，因此 `reference_close` 在產生預測時可以先記為 `pending_official_close`；不可假裝已知今日收盤。驗證時以今日最終官方收盤作為實際 reference close。正文中應明確說明此點。

## 4. 強制 YAML metadata

每份正式報告最上方必須有：

```yaml
---
target_date: YYYY-MM-DD
generated_at: YYYY-MM-DDTHH:MM:SS+08:00
information_cutoff: YYYY-MM-DDTHH:MM:SS+08:00
run_type: scheduled_0830 | scheduled_1255
reference_date: YYYY-MM-DD
reference_close: number | pending_official_close
open_bull_probability: 0.00
open_bear_probability: 0.00
open_confidence: 0.0
open_gap_low_pct: -0.0
open_gap_high_pct: 0.0
close_bull_probability: 0.00
close_bear_probability: 0.00
close_confidence: 0.0
close_return_low_pct: -0.0
close_return_high_pct: 0.0
---
```

強制規則：
- YAML probability 欄位一律使用 `0~1` 小數，不使用 `0~100` 整數百分比。
- `open_bull_probability + open_bear_probability = 1.00`。
- `close_bull_probability + close_bear_probability = 1.00`。
- 例如正文 `67% / 33%`，YAML 必須寫成 `0.67 / 0.33`，不得寫 `67 / 33`。
- `open_confidence`、`close_confidence` 使用 `0~10`。
- `open_gap_*_pct` 與 `close_return_*_pct` 使用「百分點」數值，例如 `+0.35%` 寫 `0.35`，不是 `0.0035`。
- metadata 與正文數字必須完全一致。
- 已 commit 的正式預測不得事後改機率、區間或方向。

## 5. 正文最終輸出格式

至少包含：

### 開盤預測
- 🟢 開高機率：XX%
- 🔴 開低機率：XX%
- 預估開盤跳空：X% ~ Y%
- 開盤信心度：X/10
- 一句結論：`結論：target_date 台股開盤偏高/偏低，機率 XX%。`

### 收盤預測
- 🟢 收紅機率：XX%
- 🔴 收黑機率：XX%
- 預估收盤報酬：X% ~ Y%
- 收盤信心度：X/10
- 一句結論：`結論：target_date 台股收盤偏多/偏空，機率 XX%。`

### 共同分析
- 最重要的 3 個變數
- 偏多劇本
- 偏空劇本
- 未來 24 小時重大事件
- 預測失效條件
- 已知事實與推論必須分開

## 6. 正式樣本狀態

- `success`：正式 report 已建立並 commit，可納入後續 evaluation / stats。
- `skipped`：非實際交易日，本來就不應執行；不建立樣本。
- `skipped_duplicate`：同一正式 report 已存在；不覆寫、不建立第二份樣本。
- `failed_data_source`：應執行，但必要可信資料無法取得；不建立樣本。
- 不得把 `failed_data_source` 記成一般 `skipped`，因為兩者對回測資料品質的意義不同。
- 不得用臆測資料將失敗執行強行轉成 `success`。

## 7. 比較目的

08:30 與 12:55 兩套模型必須分開統計，以回答：
- 哪個時間點的開盤方向更準？
- 哪個時間點的收盤方向更準？
- 哪個時間點的機率校準與 Brier Score 更好？
- 額外取得盤中資訊後，12:55 是否真的提高隔日預測品質？
