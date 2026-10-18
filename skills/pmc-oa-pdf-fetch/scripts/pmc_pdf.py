#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download an open-access article PDF from PMC, solving the JavaScript
Proof-of-Work challenge offline when the server serves it.

Usage:
    python3 pmc_pdf.py <PMCID> <out.pdf> [--pdf-name <filename.pdf>] [--quiet]

Mechanism:
  PMC serves one of two challenges on the PDF path, chosen by risk score:
    * PoW page (title "Preparing to download ...", ~1.8 KB) -> solvable offline
    * reCAPTCHA page (title contains "reCAPTCHA", ~20 KB)  -> NOT solvable
  Using the plain UA below AND not carrying session cookies onto the PDF
  request reliably routes to the PoW page. A full Chrome UA, or carrying
  ncbi_sid / ncbi_pinger cookies obtained from an interactive article-page
  visit, reliably escalates to reCAPTCHA.

  PoW: find the smallest nonce >= 0 such that
       sha256(f"{challenge}{nonce}").hexdigest().startswith("0" * difficulty)
  Then set   cookie[POW_COOKIE_NAME] = f"{challenge},{nonce}"

IMPORTANT - the PDF filename on PMC is NOT stable across journals or years.
Observed so far: main.pdf, HEM3-10-e70338.pdf, AJH-101-1790.pdf, LIV-46-0.pdf,
nihms-2192199.pdf. NEVER hardcode it. This script resolves the real URL from
the article page's <meta name="citation_pdf_url"> tag (falling back to any
href=".../pdf/*.pdf" link, then to main.pdf). The article page is fetched with
a bare UA and its cookies are DISCARDED, so the PDF request still starts cold.

Only use this for open-access (CC BY / CC BY-NC / CC BY-NC-ND) articles.
"""
import hashlib
import http.cookiejar
import re
import sys
import urllib.request

# Deliberately minimal UA: routes PMC to the offline-solvable PoW channel.
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"


def solve_pow(challenge: str, difficulty: int) -> int:
    target = "0" * difficulty
    nonce = 0
    while True:
        if hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest().startswith(target):
            return nonce
        nonce += 1


def discover_pdf_url(pmcid: str, quiet: bool = False) -> tuple:
    """Resolve the real PDF URL from the article page. Cookies are NOT kept."""
    art_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
    req = urllib.request.Request(art_url, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")

    m = re.search(
        r'<meta[^>]+name="citation_pdf_url"[^>]+content="([^"]+\.pdf)"', html, re.I)
    if not m:
        m = re.search(
            r'<meta[^>]+content="([^"]+\.pdf)"[^>]+name="citation_pdf_url"', html, re.I)
    if m:
        url = m.group(1)
        if url.startswith("/"):
            url = "https://pmc.ncbi.nlm.nih.gov" + url
        if not quiet:
            print(f"PDF url (citation_pdf_url): {url}")
        return url, html

    cands = [h for h in re.findall(r'href="([^"]+?/pdf/[^"]+?\.pdf)"', html)]
    if cands:
        url = cands[0]
        if url.startswith("/"):
            url = "https://pmc.ncbi.nlm.nih.gov" + url
        if not quiet:
            print(f"PDF url (href fallback): {url}")
        return url, html

    url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/main.pdf"
    if not quiet:
        print("WARNING: no PDF link found on article page; falling back to main.pdf")
    return url, html


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    quiet = "--quiet" in flags
    pdf_name = None
    if "--pdf-name" in sys.argv:
        i = sys.argv.index("--pdf-name")
        if i + 1 < len(sys.argv):
            pdf_name = sys.argv[i + 1]
            args = [a for a in args if a != pdf_name]

    if len(args) < 2:
        print(__doc__)
        return 2
    pmcid, out = args[0], args[1]

    if pdf_name:
        pdf_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/{pdf_name}"
        if not quiet:
            print(f"PDF url (explicit --pdf-name): {pdf_url}")
    else:
        try:
            pdf_url, _ = discover_pdf_url(pmcid, quiet=quiet)
        except Exception as exc:  # article page unreachable -> fall back
            print(f"WARNING: article page fetch failed ({exc}); using main.pdf")
            pdf_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/main.pdf"

    art_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"

    # Cold request: fresh cookie jar, no session cookies carried over.
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", UA)]

    body = opener.open(pdf_url, timeout=60).read()

    if body[:4] == b"%PDF":
        open(out, "wb").write(body)
        print(f"direct PDF -> {out} ({len(body)} bytes)")
        return 0

    html = body.decode("utf-8", "replace")
    if "recaptcha" in html.lower():
        print("BLOCKED: server escalated to a reCAPTCHA challenge (not solvable offline).")
        print("Try again shortly, or fall back to supplementaryFiles / publisher route.")
        return 1

    m = re.search(r'POW_CHALLENGE\s*=\s*"([^"]+)"', html)
    d = re.search(r'POW_DIFFICULTY\s*=\s*"(\d+)"', html)
    nm = re.search(r'POW_COOKIE_NAME\s*=\s*"([^"]+)"', html)
    pt = re.search(r'POW_COOKIE_PATH\s*=\s*"([^"]+)"', html)
    if not (m and d and nm and pt):
        print("No PoW challenge found. Response head follows:")
        print(html[:500])
        return 1

    challenge, difficulty = m.group(1), int(d.group(1))
    cookie_name, cookie_path = nm.group(1), pt.group(1)
    print(f"PoW: difficulty={difficulty} challenge={challenge[:24]}...")

    nonce = solve_pow(challenge, difficulty)
    digest = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
    print(f"PoW solved: nonce={nonce} hash={digest}")

    jar.set_cookie(http.cookiejar.Cookie(
        version=0, name=cookie_name, value=f"{challenge},{nonce}",
        port=None, port_specified=False, domain="pmc.ncbi.nlm.nih.gov",
        domain_specified=True, domain_initial_dot=False, path=cookie_path,
        path_specified=True, secure=True, expires=None, discard=False,
        comment=None, comment_url=None, rest={}, rfc2109=False,
    ))

    req = urllib.request.Request(
        pdf_url, headers={"User-Agent": UA, "Referer": art_url, "Accept": "application/pdf,*/*"})
    resp = opener.open(req, timeout=120)
    data = resp.read()
    print(f"status={resp.status} type={resp.headers.get('Content-Type')} bytes={len(data)}")

    if data[:4] != b"%PDF":
        print("Still not a PDF. Response head follows:")
        print(data[:500])
        return 1

    open(out, "wb").write(data)
    print(f"SAVED -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
