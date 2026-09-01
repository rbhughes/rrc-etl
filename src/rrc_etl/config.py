"""Path resolution. Raw RRC files are large and re-fetchable: kept out
of git, shared between projects via RRC_RAW rather than duplicated."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = Path(os.environ.get("RRC_RAW", ROOT / "data" / "raw"))
OUT = Path(os.environ.get("RRC_OUT", ROOT / "data"))


def pdq_zip() -> Path:
    return RAW / "PDQ_DSV.zip"


def pdq_dir() -> Path:
    return OUT / "pdq"
