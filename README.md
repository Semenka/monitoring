# ADNOC Onshore South East — Production Dashboard

Interactive Streamlit dashboard for analyzing oil / water / gas production and
water / gas injection on ADNOC Onshore South East assets, starting from the
**QW_MN** Schlumberger OFM database (`OFM_WQMN_24032026.mdb`). The skeleton is
**schema-config-driven** so swapping to another OFM database (e.g. ASAB) is a
config change, not a code change.

## Features

- Filters at **Field / Reservoir / Well** level, plus date range, aggregation
  (Daily / Monthly / Yearly), and a multi-entity picker.
- Per-level dashboards:
  - **Field & Reservoir:** oil / water / gas production, water / gas injection,
    GOR, WCT.
  - **Well:** oil / water / gas production, water / gas injection, BHP / THP
    (when mapped).
- Built-in tabs: Overview · Production · Injection · Ratios · Wells table ·
  Data quality.
- **Extensible metrics registry** — adding a new parameter is ~10 lines and it
  appears automatically in the relevant tab.
- **Portable across OFM databases** via per-DB YAML config (see
  `configs/qw_mn.yaml`).

## Project layout

```
app.py                      # Streamlit entrypoint
configs/                    # Per-database schema mappings
  qw_mn.yaml                #   real OFM column names for QW_MN
  sample.yaml               #   synthetic dataset for dev/demo
data/
  raw/                      # drop *.mdb here
  staging/<db>/*.csv        # mdb-export dumps
  warehouse/<db>.duckdb     # canonical store built on first run
src/monitoring/
  config.py                 # pydantic DBConfig loader
  io/
    mdb_extract.py          # mdbtools wrappers
    warehouse.py            # DuckDB canonical-views builder
    gdrive.py               # optional gdown-based fetcher
  domain/
    schema.py               # canonical column constants
    hierarchy.py            # entity tree helpers
    queries.py              # fetch_production(con, FilterState)
  transforms/
    aggregate.py, derived.py, units.py
  charts/
    registry.py             # @register_metric / @register_chart
    metrics.py              # built-in metric + chart definitions
    builders.py             # Plotly chart builders
  ui/
    sidebar.py, pages.py, components.py
scripts/
  convert_mdb.py            # ETL CLI
  generate_sample.py        # synthesizes a QW_MN-like demo dataset
  verify.py                 # basic sanity checks
tests/                      # pytest suite
```

## Quick start (demo with synthetic data)

```bash
sudo apt-get install -y mdbtools
pip install -r requirements.txt

# 1. Generate synthetic OFM-shaped CSVs
python scripts/generate_sample.py

# 2. Build the DuckDB warehouse
python scripts/convert_mdb.py --config configs/sample.yaml --force

# 3. Launch the dashboard
streamlit run app.py
```

Select **SAMPLE** in the Database dropdown. You’ll see 3 fields (Qusahwira,
Mender, Bida Al Qemzan), 6 reservoirs, 24 wells with ~10 years of monthly data.

## Run with the real QW_MN database

The `.mdb` is 220 MB and lives in a private Google Drive folder. Download it
manually (UI) to `data/raw/OFM_WQMN_24032026.mdb`, then:

```bash
# Inspect OFM table + column names and edit configs/qw_mn.yaml to match
python scripts/convert_mdb.py --config configs/qw_mn.yaml --tables-only
mdb-schema data/raw/OFM_WQMN_24032026.mdb | less

# Once configs/qw_mn.yaml is aligned with the real schema:
python scripts/convert_mdb.py --config configs/qw_mn.yaml --force
streamlit run app.py
```

If the file is publicly shareable, `--download` will fetch it via `gdown` using
`GDRIVE_FILE_ID_QW_MN` from `.env`.

## Migrating to a different OFM database (e.g. ASAB)

1. Drop `OFM_ASAB_25032026_1_1.mdb` into `data/raw/`.
2. Inspect the schema:
   ```bash
   mdb-tables -1 data/raw/OFM_ASAB_25032026_1_1.mdb
   mdb-schema data/raw/OFM_ASAB_25032026_1_1.mdb | head -200
   ```
3. Copy `configs/qw_mn.yaml` to `configs/asab.yaml` and adjust
   `tables.*.source` and each `columns.*` RHS to the real ASAB names.
4. Build and launch:
   ```bash
   python scripts/convert_mdb.py --config configs/asab.yaml
   streamlit run app.py
   ```
5. ASAB now appears in the Database dropdown. No Python changes needed.

## Adding a new metric (extensibility example)

```python
# src/monitoring/charts/metrics.py
@register_metric("wor", "Water-Oil Ratio", unit="bbl/bbl",
                 needs=[S.OIL_VOL, S.WATER_VOL], kind="ratio")
def _wor(df):
    return df[S.WATER_VOL] / df[S.OIL_VOL].replace(0, pd.NA)

register_chart("wor_trend", "Water-Oil Ratio", ["wor"], kind="line",
               applicable_levels=("field", "reservoir"))
```
The new chart appears on Field/Reservoir Ratios tabs at next app reload.

## Configuration (YAML)

```yaml
name: QW_MN
mdb_file: data/raw/OFM_WQMN_24032026.mdb
tables:
  entity:
    source: ENTITIES                # real OFM table name
    columns: {entity_id: ENT_ID, name: ENT_NAME, level: ENT_TYPE, parent_id: ENT_PARENT}
  monthly:
    source: MONTHLY
    date_col: PRD_DATE
    entity_col: ENT_ID
    columns:
      oil_vol: OIL_VOL
      water_vol: WATER_VOL
      gas_vol: GAS_VOL
      wtr_inj: WTR_INJ
      gas_inj: GAS_INJ
      days_on: DAYS_ON
      bhp: null                     # null == column missing in this DB
      thp: null
  static:
    source: WELL_HEADER
    columns: {well_type: WELL_TYPE, status: STATUS, completion_date: COMP_DATE}
units: {oil_vol: bbl, gas_vol: mscf, water_vol: bbl}
level_values: {field: FIELD, reservoir: RESERVOIR, well: WELL}
```

Canonical columns on the left; real OFM columns on the right. Set a value to
`null` if the column is missing — the dashboard will still run and simply hide
the corresponding charts.

## Verification

```bash
python scripts/verify.py --config configs/sample.yaml   # row counts, negatives
pytest -q                                                # unit tests
```

The dashboard’s **Data quality** tab exposes the same checks live, plus a
hierarchy-reconciliation panel (wells → reservoirs → fields).

## Open items before going live on QW_MN

- Discover the real OFM table + column names via `mdb-schema` and update
  `configs/qw_mn.yaml` accordingly.
- Confirm whether the primary production table is monthly or daily.
- Confirm unit conventions expected by the asset team (SI vs. field).
