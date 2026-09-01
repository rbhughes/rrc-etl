"""Download the PDQ dump from the RRC's managed file transfer portal.

The datasets page links a GoAnywhere MFT "GoDrive" page, not a file.
The page is a JSF/PrimeFaces web client: downloading means replaying
its form postback — same session cookies, the page's ViewState token,
and the file row's command-link parameter (scraped, not hardcoded:
the j_id suffixes change between deployments). The response streams
the zip as application/force-download. Refreshed the last Saturday of
each month; ~3.7 GB compressed, >25 GB extracted.
"""
import re
import time

import requests

from . import config

PDQ_LINK = "https://mft.rrc.texas.gov/link/1f5ddb8d-329a-4459-b7f8-177b4f5ee60d"
_POST = "https://mft.rrc.texas.gov/webclient/godrive/PublicGoDrive.xhtml"


def fetch_pdq() -> None:
    """Fetch PDQ_DSV.zip. A monthly snapshot: re-running overwrites."""
    dest = config.pdq_zip()
    dest.parent.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (rrc-etl)"
    page = s.get(PDQ_LINK, timeout=120).text
    vs = re.search(
        r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', page)
    link = re.search(r"addSubmitParam\('fileList',\{'([^']+)':'([^']+)'\}",
                     page)
    if not vs or not link:
        raise SystemExit("MFT page did not match; RRC may have changed it")
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
