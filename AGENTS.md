# Repository Guidelines

## Project Structure & Module Organization
This repository is centered on [`twse_daily.py`](/Users/lewis/develop/lewis/stock-app/twse_daily.py), the main Python script that fetches TWSE and TPEx market data and writes `dailylog_YYYYMMDD.csv`. [`watchlist.json`](/Users/lewis/develop/lewis/stock-app/watchlist.json) stores the editable stock lists for `twse` and `tpex`. Reference notes live in [`README.txt`](/Users/lewis/develop/lewis/stock-app/README.txt) and [`README_FINAL.txt`](/Users/lewis/develop/lewis/stock-app/README_FINAL.txt). Small HTML/JS files such as [`index.html`](/Users/lewis/develop/lewis/stock-app/index.html) and [`app.js`](/Users/lewis/develop/lewis/stock-app/app.js) are incidental and not part of the export pipeline.

## Build, Test, and Development Commands
Use Python 3.10+ when possible.

- `python3 -m pip install requests`: install the only required runtime dependency.
- `python3 twse_daily.py`: fetch the current trading day and generate a CSV in the repo root.
- `python3 twse_daily.py 20251031`: fetch a specific date in `YYYYMMDD` format.
- `python3 -m py_compile twse_daily.py`: quick syntax validation before committing.

Generated `*.csv` files are ignored by Git and should stay out of commits.

## Coding Style & Naming Conventions
Follow existing Python style in [`twse_daily.py`](/Users/lewis/develop/lewis/stock-app/twse_daily.py): 4-space indentation, snake_case for functions, UPPER_CASE for module constants, and short helper functions for endpoint builders and parsers. Keep network parsing defensive because upstream JSON fields vary. Prefer standard library modules plus `requests`; do not add extra dependencies without a clear need.

For JSON config, preserve the current shape:

```json
{"twse":["2330"],"tpex":["3293"]}
```

## Testing Guidelines
There is no formal test suite yet. For each change, run `python3 -m py_compile twse_daily.py` and at least one manual execution against a known date. When changing parsing logic, verify both TWSE and TPEx output columns and confirm the generated CSV header still matches the row length.

## Commit & Pull Request Guidelines
Recent commits use short, lowercase summaries such as `add 2301` and `stop tracking CSV files`. Keep commit messages brief, imperative, and scoped to one change. For pull requests, include:

- a short description of the behavioral change
- sample command(s) used for verification
- a note if API behavior or expected CSV columns changed
- a sample output snippet or screenshot only when the change affects exported data format
