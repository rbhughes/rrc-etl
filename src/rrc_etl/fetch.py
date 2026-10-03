"""Download the PDQ dump from the RRC's managed file transfer portal.

The datasets page links a GoAnywhere MFT "GoDrive" page, not a file.
The page is a JSF/PrimeFaces web client: downloading means replaying
its form postback — same session cookies, the page's ViewState token,
and the file row's command-link parameter (scraped, not hardcoded:
the j_id suffixes change between deployments). The response streams
the zip as application/force-download. Refreshed the last Saturday of
each month; ~3.7 GB compressed, >25 GB extracted.

The host also sits behind a WAF that refuses callers before any of
that matters: a request carrying a non-browser User-Agent gets an
empty 403, and a source IP it has decided against stops getting an
answer to the TLS handshake at all. Shared CI egress addresses trip
it regularly, so a failure here is far more often a block than a
change to the page -- the two are reported separately below.
"""
import re
import time

import requests

from . import config

PDQ_LINK = "https://mft.rrc.texas.gov/link/1f5ddb8d-329a-4459-b7f8-177b4f5ee60d"
_POST = "https://mft.rrc.texas.gov/webclient/godrive/PublicGoDrive.xhtml"
# Must read as a browser: the WAF 403s a bare client UA.
_UA = "Mozilla/5.0 (rrc-etl)"
_TRIES = 4
_BACKOFF = 60  # seconds before the 2nd try, doubled for each one after


def _get_page(s: requests.Session) -> str:
    """GET the GoDrive page, retrying while the host refuses us.

    A refusal is not the same failure as a page we cannot parse, and
    saying which one happened is most of the diagnosis. Retries are
    spaced in minutes: when the block is the sticky kind, hammering
    only confirms it.
    """
    why = ""
    for attempt in range(_TRIES):
        if attempt:
            delay = _BACKOFF * 2 ** (attempt - 1)
            print(f"    {why}; retrying in {delay}s "
                  f"(attempt {attempt + 1} of {_TRIES})", flush=True)
            time.sleep(delay)
        try:
            r = s.get(PDQ_LINK, timeout=120)
        except requests.exceptions.SSLError as e:
            # Handshake dropped mid-negotiation. Not a certificate
            # problem: the WAF is blackholing this source address.
            why = f"TLS handshake refused ({type(e).__name__})"
            continue
        except requests.exceptions.RequestException as e:
            why = f"connection failed ({type(e).__name__})"
            continue
        if r.status_code == 200 and r.text.strip():
            return r.text
        why = f"HTTP {r.status_code}, {len(r.content)}-byte body"
    raise SystemExit(
        f"RRC MFT refused all {_TRIES} attempts: {why}.\n"
        f"This host blocks by source-IP reputation and shared CI "
        f"egress addresses trip it, so the page is probably fine. "
        f"Retry from another network, or fetch the dump elsewhere, "
        f"stage it at {config.pdq_zip()} and skip this step.")


def fetch_pdq() -> None:
    """Fetch PDQ_DSV.zip. A monthly snapshot: re-running overwrites."""
    dest = config.pdq_zip()
    dest.parent.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    page = _get_page(s)
    vs = re.search(
        r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', page)
    link = re.search(r"addSubmitParam\('fileList',\{'([^']+)':'([^']+)'\}",
                     page)
    if not vs or not link:
        raise SystemExit(
            "MFT served a page we cannot parse; RRC may have changed it "
            f"({len(page)} bytes, ViewState found: {bool(vs)}, "
            f"file row found: {bool(link)})")
    data = {
        "fileList_SUBMIT": "1",
        "javax.faces.ViewState": vs.group(1),
        link.group(1): link.group(2),
        "fileTable_selection": "",
    }
    t0 = time.time()
    with s.post(_POST, data=data, stream=True, timeout=600) as r:
        r.raise_for_status()
        if "html" in r.headers.get("content-type", ""):
            raise SystemExit("MFT returned HTML, not the file; "
                             "postback replay failed")
        total = int(r.headers.get("content-length", 0))
        print(f"  {PDQ_LINK}\n    -> {dest} ({total/1e9:.2f} GB)")
        n = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
                n += len(chunk)
                if n % (1 << 29) < (1 << 22):
                    print(f"    {n/1e9:.1f} GB "
                          f"({n/1e6/(time.time()-t0):.0f} MB/s)", flush=True)
    print(f"  done: {n/1e9:.2f} GB in {(time.time()-t0)/60:.1f} min")
