TWSE Daily Export (CSV)
=======================

這套檔案會在你的機器上抓台股收盤所需資料並輸出 **單列 CSV**，你可以直接把那一列貼到 Google Sheet 的 `DailyLog`。

檔案
- twse_daily.py：主程式（Python 3.8+）
- watchlist.json：自選股清單（可自行修改代碼）

安裝
  python3 --version          # 建議 3.10 以上
  python3 -m pip install --upgrade pip
  python3 -m pip install requests

使用
  # 抓今天
  python3 twse_daily.py

  # 抓指定交易日（YYYYMMDD）
  python3 twse_daily.py 20251031

執行後會輸出 `dailylog_YYYYMMDD.csv`（含表頭與一列資料），你可以開啟 CSV，整列複製後貼到 Google Sheet。

常見問題
- 若遇到連線被拒/302/307：程式已實作 Cookie/Referer/Redirect 的處理，一般重試即可；仍失敗請稍後再試。
- 若同日資料尚未上架：收盤價可能為空白（等待官方資料更新後再跑）。
