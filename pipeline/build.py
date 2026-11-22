#!/usr/bin/env python3
"""주가 갱신 스크립트 (표준 라이브러리만 사용).

1순위 야후 차트 → 막히면 Stooq CSV. 종목마다 결과를 바로 로그에 찍고,
전체 실행은 6분을 넘기지 않는다. 실패한 종목은 이전 값을 유지한다.
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
YAHOO_HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
DEADLINE = time.time() + 6 * 60


def log(*a):
    print(*a, flush=True)


def http_get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def metrics(dates, c, h):
    """날짜·종가·고가 배열 → 화면에 쓰는 지표."""
    if len(c) < 30:
        return None
    last = c[-1]
    hi_idx = max(range(len(h)), key=lambda i: h[i])

    def ret(n):
        return round(last / c[-1 - n] - 1, 4) if len(c) > n else None

    return {
        "d": dates, "c": c, "last": last, "asof": dates[-1],
        "hi52": h[hi_idx], "hi52_date": dates[hi_idx], "off": round(last / h[hi_idx] - 1, 4),
        "chg1d": ret(1), "r1m": ret(20), "r3m": ret(61), "r6m": ret(122), "r1y": round(last / c[0] - 1, 4),
    }


def parse_yahoo(payload):
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
    return metrics(dates, c, h)


def from_yahoo(ticker):
    why = "?"
    for host in YAHOO_HOSTS:
        url = f"https://{host}/v8/finance/chart/{ticker}?range=1y&interval=1d"
        try:
            data = parse_yahoo(json.loads(http_get(url)))
            if data:
                return data, "ok"
            why = "응답 형식 다름"
        except urllib.error.HTTPError as e:
            why = f"HTTP {e.code}"
            if e.code == 404:
                break
        except Exception as e:  # 타임아웃, 연결 거부 등
            why = type(e).__name__
        time.sleep(1)
    return None, why


def parse_stooq(text):
    lines = text.strip().splitlines()
    if len(lines) < 31 or not lines[0].lower().startswith("date"):
        return None
    head = [x.strip().lower() for x in lines[0].split(",")]
    try:
        ci, hi = head.index("close"), head.index("high")
    except ValueError:
        return None
    dates, c, h = [], [], []
    for ln in lines[-245:]:
        p = ln.split(",")
        try:
            cv, hv = float(p[ci]), float(p[hi])
        except (ValueError, IndexError):
            continue
        dates.append(p[0])
        c.append(round(cv, 2))
        h.append(round(hv, 2))
    return metrics(dates, c, h)


def from_stooq(code):
    url = f"https://stooq.com/q/d/l/?s={code.lower()}.jp&i=d"
    try:
        text = http_get(url)
        data = parse_stooq(text)
        if data:
            return data, "ok"
        return None, "응답: " + text.strip()[:60].replace("\n", " ")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, type(e).__name__


def main():
    companies = json.loads(COMPANIES.read_text(encoding="utf-8"))["companies"]
    prev = {}
    if PRICES.exists():
        try:
            prev = json.loads(PRICES.read_text(encoding="utf-8")).get("t", {})
        except Exception:
            prev = {}

    out, ok, kept, missing = {}, 0, [], []
    use_yahoo, yahoo_ok, yahoo_fail = True, 0, 0
    for co in companies:
        code, ticker = co["code"], co.get("ticker", co["code"] + ".T")
        if time.time() > DEADLINE:
            log(f"{code} 건너뜀 (시간 제한 6분 초과)")
            data, src, why = None, "-", "시간 초과"
        else:
            data, src, why = None, "-", ""
            if use_yahoo:
                data, why = from_yahoo(ticker)
                src = "yahoo"
                if data:
                    yahoo_ok += 1
                else:
                    yahoo_fail += 1
                    log(f"{code} yahoo 실패: {why}")
                    if yahoo_ok == 0 and yahoo_fail >= 3:
                        use_yahoo = False
                        log(">> 야후가 막힌 것으로 판단, 남은 종목은 Stooq 로 수집")
            if not data:
                data, why = from_stooq(code)
                src = "stooq"
                if not data:
                    log(f"{code} stooq 실패: {why}")
        if data:
            out[code] = data
            ok += 1
            log(f"{code} OK ({src}) {data['asof']} 종가 {data['last']}")
        elif code in prev:
            out[code] = prev[code]
            kept.append(code)
        else:
            missing.append(code)
        time.sleep(0.3)

    log(f"== 갱신 {ok} / 이전값 유지 {len(kept)} {kept} / 데이터 없음 {len(missing)} {missing}")
    if ok == 0:
        log("모든 종목 수집 실패 — prices.json 을 덮어쓰지 않습니다.")
        sys.exit(1)

    PRICES.write_text(
        json.dumps(
            {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Yahoo Finance / Stooq", "t": out},
            ensure_ascii=False, separators=(",", ":"),
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
