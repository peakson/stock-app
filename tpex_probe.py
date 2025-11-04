# quick_tpex_probe.py（簡版）
from twse_daily import make_session, tpex_price_candidates, tpex_t86_candidates, tpex_pick_close, tpex_build_t86_map, ymd_to_roc

ymd = "20251031"
roc = ymd_to_roc(ymd)
seed = "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43.php?l=zh-tw"
s = make_session(seed)

def fetch(s, url, referer):
    import requests
    h = {"Accept":"application/json, text/javascript,*/*;q=0.1","Referer":referer,"X-Requested-With":"XMLHttpRequest"}
    r = s.get(url, headers=h, timeout=30)
    print(r.status_code, r.headers.get("Content-Type"), url)
    try:
        return r.json()
    except: 
        print(r.text[:200]); return None

for code in ["3293","6763"]:
    print("\n=== TPEX PRICE", code, "===")
    for u in tpex_price_candidates(roc, code):
        obj = fetch(s,u,seed)
        if obj:
            print("→ close:", tpex_pick_close(obj, ymd)); break

print("\n=== TPEX T86 (full table) ===")
obj = fetch(s, tpex_t86_candidates(roc)[0], "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade.php?l=zh-tw")
if obj:
    mp = tpex_build_t86_map(obj)
    print("3293:", mp.get("3293"))
    print("6763:", mp.get("6763"))

