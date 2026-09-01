"""Normalize the PDQ dump's tables to parquet.

Format facts (see docs and the PDQ Dump User Manual):

- The zip holds one `<TABLE>_DATA_TABLE.dsv` per Oracle table,
  delimited by `}` with NO enclosures at all. That means quoting must
  be DISABLED when reading: a stray double-quote inside a lease or
  operator name is data, not a quote character — the exact inverse of
  the Petrinex trap. `}` was chosen because it never appears in the
  data.
- Everything is read as varchar and numeric columns are TRY_CASTed by
  name pattern; RRC pads with spaces, so values are trimmed first.
- Only the lease-grain and identity tables are extracted. County /
  district / field cycle tables are lossy rollups of OG_LEASE_CYCLE
  (the county ones are documented as allowable-based estimates), and
  the SUMMARY_* tables exist for the query UI.
"""
import zipfile

import duckdb

from . import config

TABLES = (
    "GP_COUNTY",
    "GP_DATE_RANGE_CYCLE",
    "GP_DISTRICT",
    "OG_FIELD_DW",
    "OG_LEASE_CYCLE",
    "OG_LEASE_CYCLE_DISP",
    "OG_OPERATOR_DW",
    "OG_REGULATORY_LEASE_DW",
    "OG_WELL_COMPLETION",
)

# Column-name suffixes that are numeric volumes/counts in the dump.
_NUM_SUFFIXES = ("_VOL", "_ALLOW", "_BAL", "_LIMIT", "_LIFT", "_DISP",
                 "_AMT", "_COUNT")

READ_OPTS = "delim='}', quote='', header=true, all_varchar=true"


def _member_for(z: zipfile.ZipFile, table: str) -> str | None:
    for name in z.namelist():
        stem = name.rsplit("/", 1)[-1].upper()
        if stem.startswith(table + "_DATA_TABLE"):
            return name
    return None


def _select_list(con, csv_path) -> str:
    cols = [d[0] for d in con.execute(
        f"select * from read_csv('{csv_path}', {READ_OPTS}) limit 0"
    ).description]
    parts = []
    for c in cols:
        if c.upper().endswith(_NUM_SUFFIXES):
            parts.append(f'try_cast(trim("{c}") as bigint) as "{c}"')
        else:
            parts.append(f'nullif(trim("{c}"), \'\') as "{c}"')
    return ", ".join(parts)


def build() -> None:
    zp = config.pdq_zip()
    if not zp.exists():
        raise SystemExit(f"missing {zp}; run fetch-pdq first")
    out = config.pdq_dir()
    work = config.OUT / "work"
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    with zipfile.ZipFile(zp) as z:
        for table in TABLES:
            member = _member_for(z, table)
            if member is None:
                print(f"  {table}: NOT FOUND in zip -- skipped")
                continue
            out_path = out / f"{table.lower()}.parquet"
            csv_path = work / f"{table}.dsv"
            with z.open(member) as src, open(csv_path, "wb") as dst:
                while chunk := src.read(1 << 22):
                    dst.write(chunk)
            try:
                con.execute(f"""
                    copy (select {_select_list(con, csv_path)}
                          from read_csv('{csv_path}', {READ_OPTS}))
                    to '{out_path}' (format parquet, compression zstd)
                """)
            finally:
                csv_path.unlink()
            n = con.execute(
                f"select count(*) from '{out_path}'").fetchone()[0]
            mb = out_path.stat().st_size / 1e6
            print(f"  {table}: {n:,} rows -> "
                  f"{out_path.name} ({mb:,.0f} MB)", flush=True)
