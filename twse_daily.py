#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
twse_daily.py  (FINAL)
----------------------
抓取台股（上市 TWSE + 上櫃 TPEx）每日資料 → 輸出單列 CSV（含表頭），供你貼到 Google Sheet 的 DailyLog。

涵蓋：
- TWSE：三大法人金額總表（BFI82U）
- TWSE：自選股三大法人（T86）
- TWSE：自選股收盤價（STOCK_DAY）
- TPEx：自選股三大法人（多候選端點）
- TPEx：自選股收盤價（多候選端點）

使用：
  pip install requests
  python3 twse_daily.py            # 抓今天
  python3 twse_daily.py 20251031   # 抓指定日

輸出：dailylog_YYYYMMDD.csv
"""

import sys
import time
import csv
import json
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests

# ===== 自選股（可用 watchlist.json 覆寫） =====
WATCHLIST_TWSE = ['2258','2308','2317','2330','2357','2454','2753']   # 上市
WATCHLIST_TPEX = ['3293','6763']                                       # 上櫃（已將 3293 移到這裡）

def load_watchlist():
    p = Path(__file__).with_name("watchlist.json")
    if p.exists():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
            tw = cfg.get("twse") or WATCHLIST_TWSE
            tp = cfg.get("tpex") or WATCHLIST_TPEX
            return list(map(str, tw)), list(map(str, tp))
        except Exception:
            pass
    return WATCHLIST_TWSE, WATCHLIST_TPEX

def ymd_today(): return dt.datetime.now().strftime("%Y%m%d")
def ymd_to_roc(ymd: str) -> str:
    # 20251103 -> "114/11/03"
    return f"{int(ymd[:4]) - 1911}/{ymd[4:6]}/{ymd[6:8]}"

# ====== TWSE RWD endpoints ======
def twse_url_t86(ymd):     return f"https://www.twse.com.tw/rwd/zh/fund/T86?date={ymd}&selectType=ALL&response=json"
def twse_url_bfi82u(ymd):  return f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?date={ymd}&response=json"
def twse_url_stock_day(yyyymm, code):
    return f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?response=json&date={yyyymm}01&stockNo={code}"

# ====== TPEx candidates（多候選）======
def tpex_price_candidates(roc_date: str, code: str) -> list[str]:
    base = "https://www.tpex.org.tw"
    # 以 quick_tpex_probe 的結果，這個是可用的 JSON 端點
    return [
        f"{base}/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&d={roc_date}&s={code}"
    ]

def tpex_t86_candidates(roc_date: str, code: Optional[str]=None) -> List[str]:
    base = "https://www.tpex.org.tw"
    urls = [
        f"{base}/web/stock/3insti/daily_trade/3itrade_result.php?l=zh-tw&se=AL&t=D&d={roc_date}",
        f"{base}/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&se=AL&t=D&d={roc_date}",
    ]
    if code:
        urls += [
            f"{base}/web/stock/3insti/daily_trade/3itrade_result.php?l=zh-tw&se=AL&t=D&d={roc_date}&s={code}",
            f"{base}/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&se=AL&t=D&d={roc_date}&s={code}",
        ]
    return urls

# ====== 基礎 Session / 取 JSON（處理 Cookie、Referer、Redirect）======
def make_session(seed_full_url: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) PythonRequests",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    try: s.get(seed_full_url, timeout=15)
    except Exception: pass
    return s

def fetch_json_with_referer(s: requests.Session, url: str, referer: str) -> Optional[Dict[str, Any]]:
    hdr = {
        "Accept": "application/json, text/javascript,*/*;q=0.1",
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r1 = s.get(url, headers=hdr, allow_redirects=False, timeout=30)
    ct1 = r1.headers.get("Content-Type","")
    if r1.ok and "application/json" in ct1: return r1.json()
    if r1.status_code in (301,302,307):
        loc = r1.headers.get("Location")
        if loc and not loc.startswith("http"):
            from urllib.parse import urlparse
            p=urlparse(referer); loc=f"{p.scheme}://{p.netloc}{loc}"
        if loc:
            r2 = s.get(loc, headers=hdr, timeout=30)
            ct2 = r2.headers.get("Content-Type","")
            if r2.ok and "application/json" in ct2: return r2.json()
    return None

def fetch_json_try(s: requests.Session, urls: List[str], referer: str) -> Optional[Dict[str, Any]]:
    for u in urls:
        obj = fetch_json_with_referer(s, u, referer)
        if obj: return obj
    return None

# ====== TWSE 解析 ======
def parse_bfi82u(obj: Dict[str, Any]):
    fxBuy=fxSell=fxNet=""
    itBuy=itSell=itNet=""
    propBuy=propSell=propNet=""
    totalNet=""

    rows = (obj.get("data") or [])
    prop_parts = {"buy": [], "sell": [], "net": []}

    def n(x):
        try: return float(str(x).replace(",", ""))
        except: return None

    for r in rows:
        label = str(r[0] or "").replace(" ", "")
        buy, sell, net = r[1], r[2], r[3]
        if ("外資" in label or "外資及陸資" in label) and ("自營商" not in label) and ("合計" not in label):
            fxBuy, fxSell, fxNet = buy, sell, net; continue
        if "投信" in label and ("合計" not in label):
            itBuy, itSell, itNet = buy, sell, net; continue
        if "自營商" in label:
            if "合計" in label:
                propBuy, propSell, propNet = buy, sell, net
            else:
                if n(buy)  is not None: prop_parts["buy"].append(n(buy))
                if n(sell) is not None: prop_parts["sell"].append(n(sell))
                if n(net)  is not None: prop_parts["net"].append(n(net))
            continue
        if ("三大法人" in label or "合計" in label) and ("買賣超" in label):
            totalNet = net; continue

    if propNet == "" and (prop_parts["buy"] or prop_parts["sell"] or prop_parts["net"]):
        sbuy=sum([x for x in prop_parts["buy"] if x is not None])
        ssell=sum([x for x in prop_parts["sell"] if x is not None])
        snet=sum([x for x in prop_parts["net"] if x is not None])
        propBuy,propSell,propNet = f"{int(sbuy):,}",f"{int(ssell):,}",f"{int(snet):,}"
    return [fxBuy,fxSell,fxNet, itBuy,itSell,itNet, propBuy,propSell,propNet, totalNet]

def build_t86_map(obj: Dict[str, Any]):
    out = {}
    for r in (obj.get("data") or []):
        code = str(r[0]).strip()
        out[code] = {
            "fx": _to_num(r[2]),
            "it": _to_num(r[3]),
            "prop": _to_num(r[4]),
            "sum": _to_num(r[5]),
        }
    return out

def pick_close_for_date(obj: Dict[str, Any], ymd: str):
    if not obj or not obj.get("data") or not obj.get("fields"): return ""
    f = obj["fields"]
    if "日期" not in f or "收盤價" not in f: return ""
    d_idx=f.index("日期"); c_idx=f.index("收盤價")
    roc = ymd_to_roc(ymd)
    for row in obj["data"]:
        if str(row[d_idx]).strip()==roc:
            return _to_num(row[c_idx])
    return ""

# ====== TPEx 解析 ======
def tpex_pick_close(obj: dict, ymd: str) -> str:
    """
    stk_quote_result.php 這個 JSON 通常長這樣：
      { "columns":[{"sTitle":"證券代號"},...,{"sTitle":"收盤"}], "aaData":[ ["3293","...","...","收盤","..."], ... ] }
    沒有日期欄位，所以直接從 columns 找出「收盤/收盤價/Close」所在欄，然後從 aaData 取值。
    """
    if not obj:
        return ""

    rows = obj.get("aaData") or obj.get("data") or []
    cols = obj.get("columns") or obj.get("cols") or []

    # 找出收盤價欄位 index
    close_idx = None
    titles = []
    for i, c in enumerate(cols):
        t = str(c.get("sTitle") or c.get("title") or "")
        titles.append(t)
        if any(k in t for k in ("收盤價", "收盤", "Close", "ClosingPrice")):
            close_idx = i
            break

    # 如果找不到欄位，就退而求其次：抓列中最後一個像價格的數字
    def last_numeric(row):
        for x in reversed(row):
            v = _to_num(x)
            if isinstance(v, float) and v >= 0:
                return v
        return ""

    if isinstance(rows, list) and rows:
        # 端點如果有傳 s=代碼，通常只有一列；否則就取最後一列視為當日
        r = rows[0] if len(rows) == 1 else rows[-1]
        if isinstance(r, list):
            if close_idx is not None and close_idx < len(r):
                return _to_num(r[close_idx])
            else:
                return last_numeric(r)
        elif isinstance(r, dict):
            # 少數會回 dict：直接優先抓常見鍵
            v = r.get("收盤價") or r.get("收盤") or r.get("Close") or r.get("ClosingPrice")
            return _to_num(v)

    return ""

def tpex_build_t86_map(obj: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    out={}
    if not obj: return out
    rows = obj.get("aaData") or obj.get("data") or obj.get("items") or []
    for r in rows:
        code = None
        if isinstance(r, list):
            for x in r:
                s=str(x).strip()
                if s.isdigit() and 4<=len(s)<=6:
                    code=s; break
            if not code: continue
            nums=[_to_num(x) for x in r if _to_num(x)!=""]
            if len(nums)>=4:
                fx,it,prop,sumv = nums[-4:]
                out[code]={"fx":fx,"it":it,"prop":prop,"sum":sumv}
        elif isinstance(r, dict):
            code = str(r.get("證券代號") or r.get("股票代號") or r.get("Code") or r.get("code") or "").strip()
            if not code: continue
            fx   = _to_num(r.get("外資買賣超股數") or r.get("外資") or r.get("Foreign") or r.get("frgn_net"))
            itv  = _to_num(r.get("投信買賣超股數") or r.get("投信") or r.get("IT") or r.get("inv_trust_net"))
            prop = _to_num(r.get("自營商買賣超股數") or r.get("自營商") or r.get("Dealer") or r.get("dealer_net"))
            sumv = _to_num(r.get("三大法人買賣超股數") or r.get("合計") or r.get("Total") or r.get("sum"))
            out[code]={"fx":fx,"it":itv,"prop":prop,"sum":sumv}
    return out

# ====== 小工具 ======
def _to_num(x):
    try:
        s=str(x).replace(",","").strip()
        if s=="" or s=="-": return ""
        return float(s)
    except Exception:
        return ""

def build_header(w_twse, w_tpex):
    base = [
        'Date(YYYYMMDD)',
        '外資買進金額','外資賣出金額','外資買賣超',
        '投信買進金額','投信賣出金額','投信買賣超',
        '自營商買進金額','自營商賣出金額','自營商買賣超',
        '三大法人合計買賣超'
    ]
    per=[]
    for c in w_twse: per += [f"{c}_收盤價",f"{c}_外資張",f"{c}_投信張",f"{c}_自營商張",f"{c}_合計張"]
    for c in w_tpex: per += [f"{c}_收盤價",f"{c}_外資張",f"{c}_投信張",f"{c}_自營商張",f"{c}_合計張"]
    return base+per

# ====== Main ======
def main():
    ymd = (sys.argv[1] if len(sys.argv)>1 else ymd_today()).strip()
    if len(ymd)!=8 or not ymd.isdigit():
        print("請輸入 YYYYMMDD，例如：20251031"); return 1
    yyyymm = ymd[:6]; roc = ymd_to_roc(ymd)

    w_twse, w_tpex = load_watchlist()

    # --- TWSE ---
    twse_seed = "https://www.twse.com.tw/rwd/zh/fund/BFI82U"
    twse = make_session(twse_seed)
    bfi_obj  = fetch_json_with_referer(twse, twse_url_bfi82u(ymd), twse_seed) or {}
    bfi      = parse_bfi82u(bfi_obj)
    t86_obj  = fetch_json_with_referer(twse, twse_url_t86(ymd),  "https://www.twse.com.tw/rwd/zh/fund/T86") or {}
    t86_map  = build_t86_map(t86_obj)
    price_twse={}
    for code in w_twse:
        sd_obj = fetch_json_with_referer(twse, twse_url_stock_day(yyyymm, code), "https://www.twse.com.tw/rwd/zh/afterTrading/stockDay") or {}
        time.sleep(0.25)
        price_twse[code] = pick_close_for_date(sd_obj, ymd)

    # --- TPEx ---
    tpex_seed = "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43.php?l=zh-tw"
    tpex = make_session(tpex_seed)

    price_tpex={}
    tpex_map={}
    for code in w_tpex:
        pobj = fetch_json_try(tpex, tpex_price_candidates(roc, code), tpex_seed)
        price_tpex[code] = tpex_pick_close(pobj, ymd) if pobj else ""

    t86_tpex_obj = fetch_json_try(tpex, tpex_t86_candidates(roc), "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade.php?l=zh-tw")
    if t86_tpex_obj:
        full_map = tpex_build_t86_map(t86_tpex_obj)
        for code in w_tpex:
            tpex_map[code] = full_map.get(code, {})

    # --- 組合輸出列 ---
    base = [ymd] + bfi
    per_twse=[]
    for code in w_twse:
        m=t86_map.get(code,{})
        per_twse += [price_twse.get(code,""), m.get("fx",""), m.get("it",""), m.get("prop",""), m.get("sum","")]

    per_tpex=[]
    for code in w_tpex:
        m=tpex_map.get(code,{})
        per_tpex += [price_tpex.get(code,""), m.get("fx",""), m.get("it",""), m.get("prop",""), m.get("sum","")]

    header = build_header(w_twse, w_tpex)
    row = base + per_twse + per_tpex

    out = Path(f"dailylog_{ymd}.csv")
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(row)
    print(f"✅ 輸出 {out.name}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
