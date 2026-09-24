# DK NASCAR DFS

> **Generated repository — do not edit here.**
>
> Every file in this repo is copied from `edge_search`, which is the single
> source of truth. Regenerate with:
>
> ```bash
> python3 scripts/mirror_app.py --app nascar --push
> ```
>
> An edit made here will be silently overwritten on the next mirror. Make it in
> `edge_search` instead. Last mirrored 2026-09-24.

NASCAR scores place differential, laps led and fastest laps, none of which any sportsbook prices. The model is built on NASCAR's own public timing feeds rather than on odds. Read `NASCAR_STATUS.md` first.

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)

1. share.streamlit.io → **New app** → this repo
2. **Main file** = `app.py`
3. No secrets are required. This app never calls a paid odds API.

Streamlit Cloud runs on a datacenter IP, which DraftKings blocks
(`DRAFTKINGS_ACCESS.md`), so it cannot scrape. It reads committed snapshots
instead — `data/odds_snapshot_*.json` for prices and `data/draftables_snapshot/`
for salaries. Both are pushed from the desktop; this app is a reader.

## Tests

```bash
pytest -q
```
