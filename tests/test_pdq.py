"""Build a tiny synthetic PDQ_DSV.zip end to end.

The fixture bakes in the format facts that matter: `}` delimiters, NO
quoting (a stray double-quote is data), space-padded values, and the
`<TABLE>_DATA_TABLE.dsv` member naming.
"""
import zipfile

import duckdb
import pytest

from rrc_etl import config, pdq


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW", tmp_path / "raw")
    monkeypatch.setattr(config, "OUT", tmp_path)
    (tmp_path / "raw").mkdir()
    lease = (
        "OIL_GAS_CODE}DISTRICT_NO}LEASE_NO}CYCLE_YEAR_MONTH}"
        "OPERATOR_NO}OPERATOR_NAME}LEASE_GAS_PROD_VOL\n"
        'G}01}123456}202501}999999}BOB\'S "BEST" GAS CO}  1500  \n'
        "G}01}123457}202501}999999}PLAIN CO}\n"
    )
    county = "COUNTY_NO}COUNTY_NAME\n001}ANDERSON\n"
    with zipfile.ZipFile(tmp_path / "raw" / "PDQ_DSV.zip", "w") as z:
        z.writestr("OG_LEASE_CYCLE_DATA_TABLE.dsv", lease)
        z.writestr("GP_COUNTY_DATA_TABLE.dsv", county)
    return tmp_path


def test_build_types_and_quoting(data, capsys):
    pdq.build()
    con = duckdb.connect()
    rows = con.execute(f"""
      select OPERATOR_NAME, LEASE_GAS_PROD_VOL
      from '{data / "pdq" / "og_lease_cycle.parquet"}'
      order by LEASE_NO""").fetchall()
    # embedded double-quote survives; padded numeric trimmed and cast;
    # empty numeric becomes NULL
    assert rows[0] == ('BOB\'S "BEST" GAS CO', 1500)
    assert rows[1] == ("PLAIN CO", None)
    vol_type = con.execute(f"""
      select column_type from (describe select * from
      '{data / "pdq" / "og_lease_cycle.parquet"}')
      where column_name = 'LEASE_GAS_PROD_VOL'""").fetchone()[0]
    assert vol_type == "BIGINT"
    out = capsys.readouterr().out
    assert "NOT FOUND" in out  # tables absent from the fixture are reported


def test_missing_zip_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW", tmp_path)
    monkeypatch.setattr(config, "OUT", tmp_path)
    with pytest.raises(SystemExit, match="fetch-pdq"):
        pdq.build()
