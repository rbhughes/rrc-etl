"""Command line interface: rrc <command>."""
import argparse

from . import fetch, pdq


def main() -> None:
    p = argparse.ArgumentParser(prog="rrc", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch-pdq",
                   help="download the monthly PDQ production dump (~3.7 GB)")
    sub.add_parser("build-pdq",
                   help="normalize the dump's lease/identity tables to parquet")
    a = p.parse_args()
    if a.cmd == "fetch-pdq":
        fetch.fetch_pdq()
    elif a.cmd == "build-pdq":
        pdq.build()


if __name__ == "__main__":
    main()
