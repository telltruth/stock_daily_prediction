# TAIEX 官方市場資料取得與快取規格

本規格供 `scheduled_0830` 與 evaluation pipeline 共同使用，目的為避免 TWSE 單一端點或搜尋索引暫時失效造成正式樣本大量缺漏。

## 1. 權威資料

正式基準與實績以 TWSE 官方 TAIEX 資料為準。非 TWSE 來源只能交叉檢查，不得在官方值可得時覆蓋官方值。

需要的欄位至少包含：
- trading_date
- open
- close

high / low 可取得時一併保存。

## 2. 固定取得順序

對指定交易日 D，依序嘗試：

1. repo `market_data/taiex_ohlc.json` 中 `verified: true` 且日期完全等於 D 的快取。
2. TWSE 官方「發行量加權股價指數歷史資料」月資料：`indicesReport/MI_5MINS_HIST`。查詢時應直接指定 D 所在月份，不依賴搜尋引擎索引。
3. TWSE OpenAPI 對應的 `indicesReport/MI_5MINS_HIST`。
4. TWSE 官方「每日收盤行情 / MI_INDEX」或其他可直接確認 TAIEX open/close 的官方 endpoint。
5. repo 已存在的 `evaluations/YYYYMMDD.md`，但只有該 evaluation 明確記錄資料來自 TWSE official historical TAIEX，且日期完全匹配時才可作 fallback。

禁止把搜尋結果摘要、新聞報導、第三方網站數值當成正式 primary source。第三方可用來 cross-check，但不可取代官方值。

## 3. Persistent cache

快取檔固定為：

`market_data/taiex_ohlc.json`

每當 evaluation 成功取得某交易日的官方資料時，必須把該日 observation 寫入或補齊 cache。至少保存：

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

若官方來源只取得 close，可先保存 close；後續取得完整 OHLC 時補齊。不得用推估值補欄位。

## 4. 快取一致性

- 只有 TWSE 官方資料或已明確記錄 TWSE 官方來源的既有 evaluation 可寫入 `verified: true`。
- 若不同 TWSE 官方 endpoint 對同一日期數值不同，停止自動覆寫，標記 `data_conflict` 並保留既有 verified value，待後續重新確認。
- 若 TWSE 日後正式修正資料，可更新 cache，但必須記錄 `revision_from` / `revision_reason`；不得修改任何既有 prediction report。

## 5. 08:30 使用方式

0830 取得 `reference_close` 時優先讀 cache。若 cache 沒有前一交易日，再直接查 TWSE 官方 endpoint；只有全部官方路徑與已驗證 repo fallback 都失敗時才 `failed_data_source`。

0830 不得因搜尋引擎尚未索引昨日資料而直接失敗。

## 6. Evaluation 使用方式

Evaluation 取得 target_date D 與前一交易日 P 的官方實績時，必須先看 cache，再查 TWSE 官方 endpoint。只要任一官方路徑成功，就要把 D / P 可得資料回寫 cache。

官方資料取得失敗只讓該 target_date 保持 pending；backlog 不得永久放棄，後續每次 evaluation 繼續重查。
