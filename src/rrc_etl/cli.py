"""Command line interface: rrc <command>."""
import argparse

from . import fetch, pdq, wells


def main() -> None:
    p = argparse.ArgumentParser(prog="rrc", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch-pdq",
                   help="download the monthly PDQ production dump (~3.7 GB)")
    sub.add_parser("build-pdq",
                   help="normalize the dump's lease/identity tables to parquet")
    sub.add_parser("fetch-wells",
                   help="pull well surface locations from the RRC GIS service")
    a = p.parse_args()
    if a.cmd == "fetch-pdq":
        fetch.fetch_pdq()
    elif a.cmd == "build-pdq":
        pdq.build()
    elif a.cmd == "fetch-wells":
        wells.fetch_wells()


if __name__ == "__main__":
    main()
