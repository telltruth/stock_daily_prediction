# TAIEX 官方市場資料取得與快取規格

本規格供 `scheduled_0830` 與 evaluation pipeline 共同使用，目的為避免 TWSE 單一端點、ChatGPT 執行環境網路限制或搜尋索引延遲造成正式樣本大量缺漏。

## 1. 權威資料

正式基準與實績以 TWSE 官方 TAIEX 資料為準。非 TWSE 來源只能交叉檢查，不得在官方值可得時覆蓋官方值。

需要的欄位至少包含 trading_date / open / close；high / low 可取得時一併保存。

## 2. 固定取得順序

對指定交易日 D，依序嘗試：

1. repo `market_data/taiex_ohlc.json` 中 `verified: true` 且日期完全等於 D 的快取。
2. TWSE 官方「發行量加權股價指數歷史資料」月資料 `indicesReport/MI_5MINS_HIST`，直接指定 D 所在月份，不依賴搜尋引擎索引。
3. TWSE OpenAPI `indicesReport/MI_5MINS_HIST`。
4. TWSE 官方 `MI_INDEX` 或其他可直接確認 TAIEX open/close 的官方 endpoint。
5. repo 已存在的 evaluation，但只有該 evaluation 明確記錄資料來自 TWSE official historical TAIEX 且日期完全匹配時才可 fallback。

禁止把搜尋結果摘要、新聞報導、第三方網站數值當正式 primary source。第三方只能 cross-check。

## 3. Persistent cache

快取檔固定：`market_data/taiex_ohlc.json`。

每筆至少保存：

```json
{
  "date": "YYYY-MM-DD",
  "open": 0.0,
  "high": null,
  "low": null,
  "close": 0.0,
  "verified": true,
  "source_type": "twse_official",
  "source_endpoint": "...",
  "verified_at": "YYYY-MM-DDTHH:MM:SS+08:00"
}
```

只取得 close 時可先保存 close；後續再補 OHLC。不得推估缺值。

## 4. GitHub Actions 官方資料抓取器

repo 內：
- `scripts/update_taiex_cache.py`
- `.github/workflows/twse-market-data-cache.yml`

GitHub runner 直接向 TWSE 官方 endpoint 抓本月與前月資料並更新 cache，作為 ChatGPT task 外的獨立資料通道。

排程（Asia/Taipei）：
- 08:15 平日安全刷新，供 08:30 pipeline 使用
- 19:30 平日盤後刷新，供 20:00 evaluation 使用
- 20:30 平日 retry，供 21:00 evaluation 使用

若第一次官方 endpoint 失敗，script 會嘗試 TWSE `www` / `wwwc` 路徑與 OpenAPI；只有取得官方資料才寫 verified cache。

## 5. 快取一致性

- 只有 TWSE 官方資料或明確記錄 TWSE 官方來源的既有 evaluation 可寫 `verified: true`。
- 不同 TWSE 官方 endpoint 對同一日期 O/C 衝突時，不得靜默覆寫；標記/回報 `data_conflict`，保留既有 verified value 待重查。
- 官方日後修正資料可更新 cache，但不得修改既有 prediction report。

## 6. 08:30 使用方式

0830 優先讀 cache；cache 無前一交易日才查 TWSE 官方 endpoint。全部官方/verified fallback 皆失敗才 `failed_data_source`。

不得因搜尋引擎尚未索引昨日資料直接失敗。

## 7. Evaluation 使用方式

Evaluation 取得 target_date D 與前一交易日 P 的 official data 時先看 cache，再查 TWSE endpoint。任何官方路徑成功後，都要把 D/P 可得資料補入 cache。

官方資料暫時失敗只讓該 target_date pending；backlog 不得永久放棄，後續 20:00 / 21:00 與未來交易日持續重查。
