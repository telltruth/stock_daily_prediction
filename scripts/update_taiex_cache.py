#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

TZ8 = timezone(timedelta(hours=8))
CACHE = Path("market_data/taiex_ohlc.json")
HEADERS = {"User-Agent": "Mozilla/5.0 stock_daily_prediction/taiex-cache"}


def parse_num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if not s or s in {"--", "-"}:
        return None
    return float(s)


def parse_roc_date(s):
    s = str(s).strip()
    parts = s.split("/")
    if len(parts) != 3:
        return None
    y, m, d = map(int, parts)
    if y < 1911:
        y += 1911
    return f"{y:04d}-{m:02d}-{d:02d}"


def fetch_json(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def extract_month_payload(payload, source):
    out = {}
    fields = payload.get("fields") or []
    rows = payload.get("data") or []
    # Expected columns: 日期, 開盤指數, 最高指數, 最低指數, 收盤指數
    if len(fields) < 5:
        return out
    for row in rows:
        if len(row) < 5:
            continue
        date = parse_roc_date(row[0])
        if not date:
            continue
        out[date] = {
            "date": date,
            "open": parse_num(row[1]),
            "high": parse_num(row[2]),
            "low": parse_num(row[3]),
            "close": parse_num(row[4]),
            "verified": True,
            "source_type": "twse_official",
            "source_endpoint": source,
        }
    return out


def extract_openapi(payload, source):
    out = {}
    if not isinstance(payload, list):
        return out
    for obj in payload:
        if not isinstance(obj, dict):
            continue
        date_raw = obj.get("日期") or obj.get("Date") or obj.get("date")
        date = parse_roc_date(date_raw) if date_raw else None
        if not date:
            continue
        def get(*names):
            for n in names:
                if n in obj:
                    return parse_num(obj[n])
            return None
        out[date] = {
            "date": date,
            "open": get("開盤指數", "OpenIndex", "open"),
            "high": get("最高指數", "HighestIndex", "high"),
            "low": get("最低指數", "LowestIndex", "low"),
            "close": get("收盤指數", "ClosingIndex", "close"),
            "verified": True,
            "source_type": "twse_official",
            "source_endpoint": source,
        }
    return out


def month_starts(now):
    first = now.replace(day=1)
    prev = (first - timedelta(days=1)).replace(day=1)
    return [first, prev]


def fetch_all():
    now = datetime.now(TZ8)
    records = {}
    errors = []

    hosts = ["www.twse.com.tw", "wwwc.twse.com.tw"]
    paths = [
        "/rwd/zh/afterTrading/MI_5MINS_HIST?response=json&date={date}",
        "/indicesReport/MI_5MINS_HIST?response=json&date={date}",
    ]
    for month in month_starts(now):
        qdate = month.strftime("%Y%m%d")
        got_month = False
        for host in hosts:
            for path in paths:
                url = f"https://{host}" + path.format(date=qdate)
                try:
                    payload = fetch_json(url)
                    parsed = extract_month_payload(payload, url)
                    if parsed:
                        records.update(parsed)
                        got_month = True
                        break
                except Exception as e:
                    errors.append(f"{url}: {e}")
            if got_month:
                break

    # OpenAPI is an additional official fallback/merge source.
    openapi = "https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST"
    try:
        parsed = extract_openapi(fetch_json(openapi), openapi)
        for k, v in parsed.items():
            records.setdefault(k, v)
    except Exception as e:
        errors.append(f"{openapi}: {e}")

    if not records:
        print("No TWSE official records fetched", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        return None
    return records


def main():
    existing = {"version": 1, "updated_at": None, "records": {}}
    if CACHE.exists():
        existing = json.loads(CACHE.read_text(encoding="utf-8"))
    records = existing.setdefault("records", {})

    fetched = fetch_all()
    if not fetched:
        return 2

    now = datetime.now(TZ8).isoformat(timespec="seconds")
    changed = False
    for date, new in sorted(fetched.items()):
        if new.get("open") is None or new.get("close") is None:
            continue
        new["verified_at"] = now
        old = records.get(date)
        if old and old.get("verified"):
            # Official conflict guard: never silently replace a different verified O/C.
            old_open, old_close = old.get("open"), old.get("close")
            if old_open is not None and abs(float(old_open) - float(new["open"])) > 1e-6:
                print(f"data_conflict open {date}: {old_open} vs {new['open']}", file=sys.stderr)
                continue
            if old_close is not None and abs(float(old_close) - float(new["close"])) > 1e-6:
                print(f"data_conflict close {date}: {old_close} vs {new['close']}", file=sys.stderr)
                continue
            merged = dict(old)
            for key in ("open", "high", "low", "close"):
                if merged.get(key) is None and new.get(key) is not None:
                    merged[key] = new[key]
            # Upgrade provenance when direct TWSE fetch succeeds.
            merged["verified"] = True
            merged["source_type"] = "twse_official"
            merged["source_endpoint"] = new["source_endpoint"]
            merged["verified_at"] = now
            if merged != old:
                records[date] = merged
                changed = True
        else:
            records[date] = new
            changed = True

    if changed:
        existing["version"] = 1
        existing["updated_at"] = now
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Updated {CACHE}")
    else:
        print("Cache already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
