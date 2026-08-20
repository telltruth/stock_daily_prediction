# 台股開盤＋收盤雙預測規格

本規格是 08:30 與 12:55 兩條正式預測 pipeline 的共同輸出與驗證規格。

搭配方式：
- 08:30：`MORNING_PROMPT.md` + `DUAL_PREDICTION_SPEC.md` + `MARKET_DATA_SPEC.md`
- 12:55：`NOON_PROMPT.md` / `PROMPT.md` + `DUAL_PREDICTION_SPEC.md`
- 驗證：`EVALUATION_PROMPT.md` + `MARKET_DATA_SPEC.md`

若個別 Prompt 與本規格在輸出格式、機率單位、預測目標、基準價、樣本不可修改、protocol validity 或統計方式上衝突，以本規格為準。

目前 protocol：`dual-v3-20260820`。

## 1. 統一預測目標

每份正式預測同時預測同一 `target_date`：

### A. 開盤方向
- 基準：前一個實際台股交易日官方收盤價 `reference_close`
- bullish：target_date 官方開盤 > reference_close
- bearish：target_date 官方開盤 < reference_close
- gap = `(target_open / reference_close - 1) * 100`

### B. 收盤方向
- 基準同一 reference_close
- bullish：target_date 官方收盤 > reference_close
- bearish：target_date 官方收盤 < reference_close
- return = `(target_close / reference_close - 1) * 100`

開盤與收盤各自輸出 bull/bear probability，且各自合計 1.00。

### Exact-flat
若實際 open 或 close 恰等於 reference_close：
- actual direction = flat
- direction hit / Brier = N/A
- range hit 仍以 0.0% 驗證

## 2. 08:30 正式預測

`run_type: scheduled_0830`

- target_date = 今天的實際交易日。
- information_cutoff 固定為 target_date `08:30:00+08:00`。
- 實際 task 可在 cutoff 後啟動；不得使用 cutoff 後資訊。
- `generated_at` 必須 >= information_cutoff；若 task 提早啟動，不得在 cutoff 前 commit 正式 report。
- reference_close 依 `MARKET_DATA_SPEC.md` 取得。
- `reports/YYYYMMDD_0830.md` 已存在則 `skipped_duplicate`。

## 3. 12:55 正式預測

`run_type: scheduled_1255`

- target_date = 下一個實際台股交易日。
- information_cutoff 固定為執行交易日 `12:55:00+08:00`。
- 實際 task 應安排在 12:55 之後啟動；不得使用 cutoff 後資料。
- `generated_at` 必須 >= information_cutoff；若 generated_at < cutoff，該 report 視為 `protocol_valid: false`。
- reference_date = 執行日；reference_close = `pending_official_close`，驗證時再使用執行日最終官方收盤。

### 12:55 data quality
至少檢查以下四組核心盤中訊號：
1. TAIEX 精確盤中 snapshot（current/open/high/low/change）
2. 台積電精確 current/change
3. 台指期近月或可驗證期現貨基差
4. 成交量 + 市場廣度（至少漲跌家數或 up/down volume）

- `full`：至少 3/4 組可由可信來源取得，且必須包含第 1 組 TAIEX snapshot。
- `degraded`：至少有 TAIEX 可驗證盤中方向/幅度，但未達 full；仍可形成預測，但 primary 0830-vs-1255 matched comparison 不納入。
- 若連 TAIEX 盤中結構都無法可靠確認，且資訊不足以形成有品質的正式預測：`failed_data_source`。

## 4. 強制 YAML metadata

每份新 protocol report 最上方必須有：

```yaml
---
target_date: YYYY-MM-DD
generated_at: YYYY-MM-DDTHH:MM:SS+08:00
information_cutoff: YYYY-MM-DDTHH:MM:SS+08:00
run_type: scheduled_0830 | scheduled_1255
protocol_version: dual-v3-20260820
prompt_version: morning-v3-20260820 | noon-v3-20260820
protocol_valid: true | false
data_quality: full | degraded
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
- probability 一律 0~1 小數。
- open bull + bear = 1.00；close bull + bear = 1.00。
- confidence 0~10。
- gap/return 使用百分點，例如 +0.35% 寫 0.35。
- metadata 與正文一致。
- 已 commit 正式預測 immutable。

## 5. protocol validity

新 report 的 `protocol_valid` 只有在以下全部成立時可為 true：
- generated_at >= information_cutoff
- 未使用 cutoff 後資訊
- run_type / target_date / reference_date 正確
- probability / range metadata 合法
- report 為該 run_type + target_date 唯一正式版本

舊 report 若缺新 metadata，不修改原檔；evaluation 依原始 generated_at / cutoff / commit 時間判斷為 `legacy` 或 `protocol_valid=false`。

## 6. 正式樣本狀態

- success：report 建立並 commit。
- skipped：非實際交易日。
- skipped_duplicate：正式 report 已存在。
- failed_data_source：必要可信資料不足。

不得用猜測資料把失敗執行強行轉 success。

## 7. 評估指標

四條 pipeline 分開：
- scheduled_0830.open
- scheduled_0830.close
- scheduled_1255.open
- scheduled_1255.close

每條至少維護：
- direction hit rate
- Brier all / last20 / last60
- range hit rate
- range width 平均值：`forecast_high_pct - forecast_low_pct`
- range miss distance：命中為 0；未命中為實際值到最近邊界的距離
- custom range score：`range_width_pct + 2 * range_miss_distance_pct`，越低越好
- calibration / confidence buckets

100% range hit 不得單獨解讀為準確；必須同時看 range width / range score。

## 8. Matched-date comparison

0830 vs 1255 的 primary comparison 只使用同一 target_date 同時具備：
- 有效 scheduled_0830 report
- 前一交易日有效 scheduled_1255 report
- protocol_valid = true
- 1255 data_quality = full

才構成 matched pair。

不得用不同樣本日期或不同市場 regime 的兩組 all-time 樣本直接宣稱哪個時間點較準。

另外保留：
- all-sample descriptive stats
- legacy / degraded descriptive stats
- matched protocol-valid comparison

樣本少於 20 pairs 時必須標註不足。
