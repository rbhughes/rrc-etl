"""Fetch well surface locations from the RRC public GIS service.

The PDQ dump has no coordinates anywhere. The RRC public map viewer's
"Well Locations" layer does: ~1.4M points with NAD83 lat/lon, an API
number, a symbol (well type) and a location-reliability code. ~1.03M
rows carry a real 8-digit API (3-digit county + 5-digit unique — the
same pair og_well_completion carries); the rest are old hardcopy-era
permitted locations with no API and are skipped.

Pulled via paginated REST queries (1,000 rows/page, ordered by
OBJECTID), ~1,050 requests. Snapshot semantics: re-running overwrites.
"""
import time

import duckdb
import requests

from . import config

LAYER = ("https://gis.rrc.texas.gov/server/rest/services/rrc_public/"
         "RRC_Public_Viewer_Srvs/MapServer/1/query")
PAGE = 1000


def fetch_wells() -> None:
    out = config.OUT / "wells"
    out.mkdir(parents=True, exist_ok=True)
    out_path = out / "well_locations.parquet"
    s = requests.Session()
    s.headers["User-Agent"] = "rrc-etl"
    rows = []
    offset = 0
    t0 = time.time()
    while True:
        for attempt in range(3):
            try:
                r = s.get(LAYER, params={
                    "where": "GIS_API5 <> ' '",
                    "outFields": "API,SYMNUM,GIS_SYMBOL_DESCRIPTION,"
                                 "RELIAB,GIS_LAT83,GIS_LONG83",
                    "orderByFields": "OBJECTID",
                    "resultOffset": offset,
                    "resultRecordCount": PAGE,
                    "returnGeometry": "false",
                    "f": "json",
                }, timeout=120)
                j = r.json()
                if "error" in j:
                    raise RuntimeError(j["error"])
                break
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
        feats = j.get("features", [])
        for f in feats:
            a = f["attributes"]
            api = (a.get("API") or "").strip()
            lat, lon = a.get("GIS_LAT83"), a.get("GIS_LONG83")
            if len(api) == 8 and lat and lon:
                rows.append((api[:3], api[3:], a.get("SYMNUM"),
                             a.get("GIS_SYMBOL_DESCRIPTION"),
                             a.get("RELIAB"), lat, lon))
        offset += len(feats)
        if offset % 100_000 < PAGE:
            print(f"  {offset:,} fetched "
                  f"({offset/(time.time()-t0):.0f} rows/s)", flush=True)
        if len(feats) < PAGE:
            break
    con = duckdb.connect()
    con.execute("""create table w (api_county varchar, api_unique varchar,
        symnum int, symbol varchar, reliab varchar,
        lat double, lon double)""")
    con.executemany("insert into w values (?,?,?,?,?,?,?)", rows)
    con.execute(f"""copy w to '{out_path}'
                    (format parquet, compression zstd)""")
    print(f"  {len(rows):,} wells with API + coords -> {out_path} "
          f"({out_path.stat().st_size/1e6:.0f} MB) "
          f"in {(time.time()-t0)/60:.1f} min")
