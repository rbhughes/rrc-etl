# rrc-etl

Fetch and normalize Texas Railroad Commission public oil and gas data
— starting with the PDQ production dump — into clean parquet you can
query with DuckDB, pandas, or anything else. The Texas sibling of
[petrinex-etl](https://github.com/rbhughes/petrinex-etl), built for
the [methane-outliers](https://github.com/rbhughes/methane-outliers)
comparison project.

## Quickstart

```sh
pip install -e .
rrc fetch-pdq     # ~3.7 GB zip from the RRC's MFT portal
rrc build-pdq     # -> data/pdq/*.parquet (~1.4 GB)
```

Paths: `RRC_RAW` (default `data/raw`) for downloads, `RRC_OUT`
(default `data`) for parquet.

## What you get (measured, 2026-08 dump)

One parquet per source table under `data/pdq/`:

| table | rows | what it is |
|---|---|---|
| `og_lease_cycle` | 78.9M | lease-month production, 1993-01..now |
| `og_lease_cycle_disp` | 48.6M | lease-month disposition volumes |
| `og_regulatory_lease_dw` | 549k | lease identity |
| `og_well_completion` | 821k | well (API) -> lease mapping |
| `og_operator_dw` | 78k | operator registry |
| `og_field_dw` | 66k | field identity (discovery date, flags) |
| `gp_county` / `gp_district` | 277 / 14 | geography codes |

Scale: ~132,000 leases report in a current month. Operator joins via
`OPERATOR_NO` cover 100% of a month's disposition rows.

## Format facts that cost debugging time

- **The download is not a link.** The datasets page points at a
  GoAnywhere MFT page (a JSF/PrimeFaces web client). `fetch-pdq`
  replays its form postback — session cookie, `ViewState` token, and
  the file row's command-link parameter, all scraped at run time
  because the component ids change between deployments.
- **`}` is the delimiter and there is NO quoting.** A stray `"` in an
  operator name is data. Disable quoting when reading (`quote=''`) —
  the exact inverse of the Petrinex quoting trap.
- **Values are space-padded**; trim before casting, and empty strings
  are NULL.
- **Casinghead disposition columns are spelled `DISPCDE##`** (with an
  E), unlike gas well gas's `DISPCD##`. Not a typo in the manual; it
  is the schema.
- **Flared and vented gas are NOT split in this dump.** Form PR gained
  disposition codes 10 (flared) and 11 (vented) in March 2021, but
  the PDQ dump folds both back into the legacy combined column
  `*_DISPCD04_VOL` ("vented or flared") — measured: the code-04
  series is continuous across the 2021 change (205.6 Bcf in 2019,
  ~110-125 Bcf/yr 2023-2025). Lease/field fuel is code 01. The split
  detail exists only in the separate PR (P1/P2) Gas Disposition
  dataset (future work).
- **Production is by LEASE, not well.** Wells map to leases via
  `og_well_completion` (821k completions over 403k lease keys).
- The dump is a monthly full snapshot (last Saturday), not
  incremental: re-fetch replaces everything, and history back to
  1993-01 comes with it.

## Data licence

RRC public data. This repo ships code; pull the data from the source.
`data/` is gitignored — do not re-host the dump.

## Code licence

MIT — see `LICENSE`. Code only, not the data.
