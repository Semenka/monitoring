# ADNOC Onshore South East — Production Dashboard

[![CI](https://github.com/semenka/monitoring/actions/workflows/ci.yml/badge.svg)](https://github.com/semenka/monitoring/actions/workflows/ci.yml)

Interactive Streamlit dashboard for analyzing oil / water / gas production and
water / gas injection on ADNOC Onshore South East assets — starting with the
four Schlumberger OFM databases **QW_MN**, **ASAB**, **SAHIL**, and **SHAH** —
with Field / Reservoir / Well drill-down, GOR / WCT ratios, and BHP / THP
pressures. The skeleton is **schema-config-driven** so adding more OFM
databases is a config change, not a code change.

## Supported databases

| Field (config)             | Source OFM file(s)                                                      | Size        | Drive file IDs |
|----------------------------|-------------------------------------------------------------------------|-------------|----------------|
| **QW_MN** (`qw_mn.yaml`)   | `OFM_WQMN_24032026.mdb`                                                 | 220 MB      | single |
| **SHAH** (`shah.yaml`)     | `OFM_SHAH_24032026.mdb`                                                 | 752 MB      | single |
| **SAHIL** (`sahil.yaml`)   | `OFM_SAHIL_26032026_{1,2}_1.mdb`                                        | ~1.2 GB     | 2 parts |
| **ASAB** (`asab.yaml`)     | `OFM_ASAB_25032026_{1,2}_1.mdb` + `OFM_ASAB_26032026_3_1.mdb`           | ~3.0 GB     | 3 parts |

Multi-part OFM exports are concatenated transparently by the loader.

Demo configs (`sample*.yaml`) ship synthetic data so the dashboard is usable
immediately without any download.

## Features

- Filters at **Field / Reservoir / Well** level, plus date range, aggregation
  (Daily / Monthly / Yearly) and multi-entity picker.
- Dashboards per level:
  - **Field & Reservoir:** oil / water / gas production, water / gas injection,
    GOR, WCT.
  - **Well:** oil / water / gas production, water / gas injection, BHP / THP
    (when mapped).
- Built-in tabs: Overview · Production · Injection · Ratios · Wells table ·
  Data quality.
- **Extensible metric registry** — adding a new parameter is ~10 lines and it
  appears automatically in the relevant tab.
- **Portable across OFM databases** via per-DB YAML config.

## Project layout

```
app.py                      # Streamlit main app
streamlit_app.py            # Streamlit Cloud entrypoint
packages.txt                # apt packages for Streamlit Cloud (mdbtools)
configs/                    # Per-database schema mappings
  qw_mn.yaml, asab.yaml, sahil.yaml, shah.yaml
  sample.yaml, sample_asab.yaml, sample_sahil.yaml, sample_shah.yaml
data/
  raw/                      # drop *.mdb files here
  staging/<db>/*.csv        # mdb-export dumps (auto-generated)
  warehouse/<db>.duckdb     # canonical store (auto-generated)
src/monitoring/
  config.py                 # pydantic DBConfig loader
  io/{mdb_extract,warehouse,gdrive}.py
  domain/{schema,hierarchy,queries}.py
  transforms/{aggregate,derived,units}.py
  charts/{registry,metrics,builders}.py
  ui/{sidebar,pages,components}.py
scripts/
  convert_mdb.py            # ETL CLI
  generate_sample.py        # synthesizes demo datasets
  verify.py                 # sanity checks
.github/workflows/ci.yml    # CI runs tests + builds all sample warehouses
tests/                      # pytest suite
```

## Quick start — demo with synthetic data

```bash
sudo apt-get install -y mdbtools     # system package for reading .mdb files
pip install -r requirements.txt

# 1. Generate synthetic OFM-shaped CSVs for all four fields
python scripts/generate_sample.py

# 2. Build the DuckDB warehouses
python scripts/convert_mdb.py --config configs/sample.yaml --force
python scripts/convert_mdb.py --config configs/sample_asab.yaml --force
python scripts/convert_mdb.py --config configs/sample_sahil.yaml --force
python scripts/convert_mdb.py --config configs/sample_shah.yaml --force

# 3. Launch
streamlit run app.py
```

The sidebar shows a **Database** dropdown — pick any of the four demo datasets
to explore Field / Reservoir / Well dashboards.

## Running with the real ADNOC databases

The `.mdb` files are in a private Google Drive folder (`ADNOC/<field>/`).
Download each locally into `data/raw/` using the exact filenames referenced in
the YAML configs. Then inspect the real schema and adjust the config if
needed:

```bash
python scripts/convert_mdb.py --config configs/qw_mn.yaml --tables-only
mdb-schema data/raw/OFM_WQMN_24032026.mdb | less

# Edit configs/qw_mn.yaml so columns map to the real OFM names, then:
python scripts/convert_mdb.py --config configs/qw_mn.yaml --force
```

Same flow for `asab.yaml`, `sahil.yaml`, `shah.yaml`. The Drive file IDs are
baked into each config under `gdrive_file_ids`, so `--download` will try
`gdown` first; if the file isn't publicly shareable, fall back to manual
download via the Drive UI.

## Adding another OFM database

1. Drop the `.mdb` file(s) into `data/raw/`.
2. Copy `configs/qw_mn.yaml` to `configs/<new>.yaml`.
3. Edit `mdb_file` (single) or `mdb_files` (list for multi-part exports) and
   adjust `tables.*.source` / `columns.*` to match real OFM names.
4. `python scripts/convert_mdb.py --config configs/<new>.yaml`.
5. Relaunch Streamlit — the new DB appears in the sidebar selector.

## Adding a new metric (extensibility)

```python
# src/monitoring/charts/metrics.py
@register_metric("wor", "Water-Oil Ratio", unit="bbl/bbl",
                 needs=[S.OIL_VOL, S.WATER_VOL], kind="ratio")
def _wor(df):
    return df[S.WATER_VOL] / df[S.OIL_VOL].replace(0, pd.NA)

register_chart("wor_trend", "Water-Oil Ratio", ["wor"], kind="line",
               applicable_levels=("field", "reservoir"))
```

The new chart shows up on Field/Reservoir Ratios tab at next app reload.

## Deployment

The repo is designed to deploy directly to **Streamlit Community Cloud**:

1. Push the repo to GitHub (already automated on the
   `claude/adnoc-production-dashboard-Ee28Y` branch).
2. Go to https://share.streamlit.io → **New app** → pick `semenka/monitoring`,
   main file `streamlit_app.py`.
3. Streamlit Cloud reads `packages.txt` (installs `mdbtools`) and
   `requirements.txt` automatically.
4. On first launch, `streamlit_app.py` builds the demo warehouses and renders
   the dashboard. To enable real data, upload `.mdb` files into `data/raw/`
   and trigger a reboot.

Alternatives:

- **Local**: `streamlit run app.py` (see Quick start above).
- **Docker**: a one-file Dockerfile would install `mdbtools` + `pip install -r
  requirements.txt` then `streamlit run app.py`; skipped here to keep the repo
  light.
- **GitHub Actions**: CI runs tests + builds all sample warehouses + verifies
  the Streamlit UI imports on every push (`.github/workflows/ci.yml`).

## Configuration (YAML)

Single-file example:

```yaml
name: SHAH
mdb_file: data/raw/OFM_SHAH_24032026.mdb
gdrive_file_ids: [1FkBgBx62ctqzixnK4O30ne1R4QIgJZNy]
tables:
  entity:  {source: ENTITIES,    columns: {entity_id: ENT_ID, name: ENT_NAME, level: ENT_TYPE, parent_id: ENT_PARENT}}
  monthly: {source: MONTHLY,     date_col: PRD_DATE, entity_col: ENT_ID,
            columns: {oil_vol: OIL_VOL, water_vol: WATER_VOL, gas_vol: GAS_VOL,
                      wtr_inj: WTR_INJ, gas_inj: GAS_INJ, days_on: DAYS_ON,
                      bhp: null, thp: null}}
  static:  {source: WELL_HEADER, columns: {well_type: WELL_TYPE, status: STATUS, completion_date: COMP_DATE}}
units: {oil_vol: bbl, water_vol: bbl, gas_vol: mscf, wtr_inj: bbl, gas_inj: mscf}
level_values: {field: FIELD, reservoir: RESERVOIR, well: WELL}
```

Multi-part example (ASAB):

```yaml
name: ASAB
mdb_files:
  - data/raw/OFM_ASAB_25032026_1_1.mdb
  - data/raw/OFM_ASAB_25032026_2_1.mdb
  - data/raw/OFM_ASAB_26032026_3_1.mdb
gdrive_file_ids: [1qdYFWZ0Y8vdo9CZnDwu6td86ZvEHOgEM, 1Zbrky_U1NxdoON_UQ-wnUNvNc1-8Ngcx, 1yDS2Ui-ue_3Bz1hHdihGD7CvD27wkCO_]
...
```

Canonical column names on the left; real OFM column names on the right. Set a
value to `null` if the column is missing — the dashboard will still run and
simply hide the corresponding charts.

## Verification

```bash
python scripts/verify.py --config configs/sample.yaml   # row counts, negatives
pytest -q                                                # unit tests
```

CI runs the same checks plus the Streamlit UI import smoke-test across all
four sample warehouses on every push.

## Open items before going live on real data

- For each real DB, run `mdb-schema` and update the `tables.*.source` and
  `columns.*` mappings to the real OFM names.
- Confirm whether the primary production table is monthly or daily.
- Confirm unit conventions expected by the asset team (SI vs. field).
