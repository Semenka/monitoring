# Reservoir monitoring & diagnostic plots from an OFM database

This document inventories the kinds of tables typically present in a
Schlumberger **OFM** (Oil Field Manager) `.mdb` export of an ADNOC asset, and
maps each table to the reservoir-monitoring and well-diagnostic plots it
unlocks.

> **How to derive the actual schema from your `.mdb`**
> ```
> python scripts/inspect_mdb.py --config configs/qw_mn.yaml \
>     --out docs/db_inspection_qw_mn.md
> ```
> The generated Markdown lists every table, its row count, schema, and a
> sample of rows — use it to align `configs/<db>.yaml` with the real OFM
> column names.

---

## Typical OFM tables

OFM organises data into a small number of standard tables; vendor exports may
add custom ones. The most common are:

| Table family               | Typical names                  | Granularity          | Contents                                                            |
|----------------------------|--------------------------------|----------------------|---------------------------------------------------------------------|
| Entity hierarchy           | `ENTITIES`, `HIERARCHY`        | static               | Asset → Field → Reservoir → Well tree, parent-child links           |
| Well header / static       | `WELL_HEADER`, `STATIC_DATA`   | static               | Surface / bottomhole coordinates, well type, status, completion date|
| Monthly production         | `MONTHLY`, `MASTER_MONTHLY`    | monthly per entity   | Oil / water / gas volume, water / gas injection, days on            |
| Daily production           | `DAILY`, `MASTER_DAILY`        | daily per entity     | Same metrics at daily resolution                                    |
| Well tests                 | `WELL_TEST`, `PWT`, `PT`       | per test             | Choke, BHP, THP, flow rates, GOR, WCT, separator readings           |
| Pressure surveys           | `BHP_SURVEY`, `STATIC_PRESSURE`| per survey           | Datum-corrected static reservoir pressure, gauge depth, temperature |
| PVT properties             | `PVT`, `FLUID`                 | per reservoir        | Bubble-point, Bo, Bg, Rs, viscosity, density                        |
| Completions                | `COMPLETIONS`, `PERFS`         | per completion       | Top/bottom MD, perforation intervals, status                        |
| Workovers / interventions  | `WORKOVERS`, `JOBS`            | per event            | Date, job type, cost, duration                                      |
| Reservoir / formation tops | `TOPS`, `FORMATIONS`           | per well per zone    | TVDSS tops, thickness, porosity, Sw                                 |
| Allocations                | `ALLOCATIONS`                  | monthly              | Theoretical / measured / allocated splits across wells              |
| Type curves / forecasts    | `FORECAST`, `TYPECURVE`        | monthly              | Forecasted profile per scenario                                     |
| Reference / look-ups       | `INDEX_TABLE`, `TYPE_DATA`     | static               | Code → label dictionaries (status codes, fluid types, …)            |

---

## Diagnostic plots — what each table enables

### From `MONTHLY` (or `DAILY`) production + injection data

| Plot                                                | Inputs                                          | Use                                                                  |
|-----------------------------------------------------|-------------------------------------------------|----------------------------------------------------------------------|
| Oil / water / gas **rate vs time**                  | volumes ÷ days_on                               | Production trend, decline detection                                  |
| **Cumulative production** (Np, Wp, Gp) vs time      | running sum of monthly volumes                  | Recovery progress, EUR proxy                                         |
| Semilog **decline curve** (log oil rate vs time)    | oil rate vs months                              | Arps decline-rate / b-factor estimation                              |
| **WCT vs time**, **WCT vs Np**                      | water_vol, oil_vol, cumulative oil              | Water breakthrough timing, sweep efficiency                          |
| **GOR vs time**, **GOR vs Np**                      | gas_vol, oil_vol, cumulative oil                | Gas breakthrough, pressure depletion below Pb                        |
| **WOR & WOR derivative** (Chan plot, log-log)       | water_vol/oil_vol vs time                       | Coning vs channeling diagnosis                                       |
| **Recovery curves** (Wp vs Np, Gp vs Np)            | cumulative volumes                              | Sweep & gas-cap behaviour                                            |
| **VRR** — Voidage Replacement Ratio                 | (W_inj + G_inj) / (Np + Wp + Gp at res. cond.)  | Pressure maintenance assessment                                      |
| **Hall plot** (cum_W_inj × WHP) vs cum_W_inj        | water injection vol, injection pressure         | Injectivity decline / formation damage                               |
| **Active well count**, **producer/injector ratio**  | days_on > 0 grouped by month                    | Activity & efficiency over time                                      |

### From `WELL_TEST` data

| Plot                                            | Inputs                                       | Use                                          |
|-------------------------------------------------|----------------------------------------------|----------------------------------------------|
| Test-vs-allocated rate scatter                  | test rate, allocated monthly rate            | Allocation QC                                |
| **PI vs time** (productivity index)             | Q / (Pavg − Pwf) per test                    | Well productivity decline / damage           |
| **IPR curve** (Pwf vs Q)                        | tested choke positions                       | Inflow performance, AOF estimation           |
| Choke-flow correlation                          | rate vs choke / THP                          | Choke calibration                            |

### From `STATIC_PRESSURE` / `BHP_SURVEY`

| Plot                                            | Inputs                                       | Use                                          |
|-------------------------------------------------|----------------------------------------------|----------------------------------------------|
| **P/Z plot** (gas reservoir material balance)   | static pressure, Z factor (PVT)              | OGIP, gas drive efficiency                   |
| **Average reservoir pressure vs time**          | datum-corrected static pressures             | Pressure depletion monitoring                |
| Pressure–depth gradient                         | survey pressures vs depth                    | Fluid contacts (OWC, GOC) tracking           |
| Δp vs cumulative voidage                        | Pavg, Np                                     | Aquifer support classification               |

### From `PVT` / `FLUID`

| Use                                        | Example                                           |
|--------------------------------------------|---------------------------------------------------|
| Convert surface volumes to reservoir bbl   | Bo, Bg used in VRR and recovery calculations      |
| Bubble-point overlay on GOR plots          | flag wells producing below Pb                     |
| Compute formation-volume corrections       | for Hall plot, recovery factor                    |

### From `COMPLETIONS` + `WORKOVERS`

| Plot                                       | Use                                               |
|--------------------------------------------|---------------------------------------------------|
| Workover timeline (Gantt)                  | Correlate rate / WCT / GOR jumps with events     |
| Completion-zone mix per well               | Allocation quality, zonal contributions          |
| Time-since-last-intervention histogram     | Identify intervention candidates                 |

### From `TOPS` / `FORMATIONS` + production

| Plot                                                | Use                                            |
|-----------------------------------------------------|------------------------------------------------|
| Recovery factor per zone (Np / OOIP)                | Zonal performance ranking                      |
| Net pay × porosity × So map (heat map)              | Sweet spot identification                      |
| Wells × zones bubble map                            | Spatial sweep distribution                     |

---

## What we have implemented so far (synthetic + real-ready)

The dashboard's metric registry already supports — at field / reservoir / well
level, with UAE field units (BOPD, BWPD, MMscf/d, psi):

| Tab            | Charts                                                                                |
|----------------|---------------------------------------------------------------------------------------|
| Overview       | KPI cards · stacked production mix                                                    |
| Production     | Oil rate (BOPD) · Water rate (BWPD) · Gas rate (MMscf/d) · cumulative oil/water/gas   |
| Injection      | Water injection rate (BWIPD) · Gas injection rate (MMscf/d) · cumulative injection    |
| Ratios         | GOR · Water cut (WCT)                                                                 |
| Diagnostics    | Decline curve (semilog oil rate) · GOR vs Np · WCT vs Np · WOR vs time · VRR          |
| Pressure       | BHP · THP (when mapped)                                                               |
| Wells table    | Per-well aggregates with CSV download                                                 |
| Data quality   | Hierarchy reconciliation · out-of-range counts                                        |

Adding any other plot from the catalogue above is a ~10-line registry entry
once the underlying column is mapped in the YAML config (see
`src/monitoring/charts/metrics.py`).

---

## Suggested follow-up once real `.mdb` is on disk

1. Run `scripts/inspect_mdb.py` and review the generated report.
2. Update `configs/<db>.yaml` to point at the real OFM table/column names.
3. If well tests / static pressures / PVT tables are present, add new YAML
   sections for them and register the corresponding charts (PI vs time, P/Z,
   IPR) — each is one new metric + one new chart.
