#!/usr/bin/env python3
"""주가 갱신 스크립트 (표준 라이브러리만 사용).

data/companies.json 의 종목을 읽어 야후 차트 엔드포인트에서 1년치 일봉을 받아
data/prices.json 으로 저장한다. 실패한 종목은 이전 값을 그대로 둔다.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "data" / "companies.json"
PRICES = ROOT / "data" / "prices.json"
HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def fetch_json(ticker, attempt):
    host = HOSTS[attempt % len(HOSTS)]
    url = f"https://{host}/v8/finance/chart/{ticker}?range=1y&interval=1d&events=div%2Csplit"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def parse(payload):
    """야후 응답 → 지표 딕셔너리. 쓸 수 없으면 None."""
    try:
        res = payload["chart"]["result"][0]
        ts = res["timestamp"]
        quote = res["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError):
        return None
    off = (res.get("meta") or {}).get("gmtoffset", 32400)
    closes, highs = quote.get("close") or [], quote.get("high") or []
    dates, c, h = [], [], []
    for i, t in enumerate(ts):
        cv = closes[i] if i < len(closes) else None
        if cv is None:
            continue
        hv = highs[i] if i < len(highs) and highs[i] is not None else cv
        dates.append(datetime.fromtimestamp(t + off, tz=timezone.utc).strftime("%Y-%m-%d"))
        c.append(round(float(cv), 2))
        h.append(round(float(hv), 2))
    if len(c) < 30:
        return None

    last = c[-1]
    hi_idx = max(range(len(h)), key=lambda i: h[i])
    hi52 = h[hi_idx]

    def ret(n):
        return round(last / c[-1 - n] - 1, 4) if len(c) > n else None

    return {
        "d": dates,
        "c": c,
        "last": last,
        "asof": dates[-1],
        "hi52": hi52,
        "hi52_date": dates[hi_idx],
        "off": round(last / hi52 - 1, 4),
        "chg1d": ret(1),
        "r1m": ret(20),
        "r3m": ret(61),
        "r6m": ret(122),
        "r1y": round(last / c[0] - 1, 4),
    }


def get(ticker):
    for attempt in range(4):
        try:
            out = parse(fetch_json(ticker, attempt))
            if out:
                return out
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
        time.sleep(1.5 * (attempt + 1))
    return None


def main():
    companies = json.loads(COMPANIES.read_text(encoding="utf-8"))["companies"]
    prev = {}
    if PRICES.exists():
        try:
            prev = json.loads(PRICES.read_text(encoding="utf-8")).get("t", {})
        except Exception:
            prev = {}

    out, ok, kept, missing = {}, 0, [], []
    for co in companies:
        code, ticker = co["code"], co.get("ticker", co["code"] + ".T")
        data = get(ticker)
        if data:
            out[code] = data
            ok += 1
        elif code in prev:
            out[code] = prev[code]
            kept.append(code)
        else:
            missing.append(code)
        time.sleep(0.4)

    print(f"갱신 {ok} / 이전값 유지 {len(kept)} {kept} / 데이터 없음 {len(missing)} {missing}")
    if ok == 0:
        print("모든 종목 수집 실패 — prices.json 을 덮어쓰지 않습니다.")
        sys.exit(1)

    PRICES.write_text(
        json.dumps(
            {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Yahoo Finance", "t": out},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
