#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_pdfs.py — 批量下载检索结果中开放获取（OA）文献的 PDF。

只下载开放获取文献（is_open_access == true 或能通过 EuropePMC 确认的条目），
不绕过任何付费墙。每条记录按固定降级链尝试：

  1. EuropePMC fullTextXML（证明全文可及，同时留档）
  2. EuropePMC 官方 PDF 端点
  3. PMC PoW 求解下载（调用 pmc_pdf.py —— 含离线 Proof-of-Work 求解）
  4. Unpaywall 定位的 OA 直链（需提供联系邮箱，遵守其使用条款）

产物：
  <outdir>/<PMID>.pdf            下载成功的全文
  <outdir>/<PMID>.xml           EuropePMC 全文 XML（降级链第 1 步留档）
  <outdir>/fetch_manifest.json  每条的下载状态、来源、SHA256、失败原因

用法：
  python3 fetch_pdfs.py results.json -o pdfs/ --email you@example.org
  python3 fetch_pdfs.py results.json -o pdfs/ --only-oa --workers 2

注意：并发保持低位（默认 2），对 PMC / EuropePMC 友好；脚本内置限速。
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UNPAYWALL = "https://api.unpaywall.org/v2"
UA = "pubmed-lit-report/1.0 (OA pdf fetch)"
SCRIPT_DIR = Path(__file__).resolve().parent


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_pdf(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def _get(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def try_epmc_fulltext(rec: dict, outdir: Path) -> dict:
    """第 1 级：EuropePMC 全文 XML。能拿到说明是 OA，同时留档。"""
    pmcid = rec.get("pmcid")
    if not pmcid:
        return {"ok": False, "reason": "无 PMCID"}
    url = f"{EPMC}/{pmcid}/fullTextXML"
    try:
        data = _get(url)
    except Exception as e:
        return {"ok": False, "reason": f"fullTextXML 不可获取: {e}"}
    if b"<article" not in data[:2000]:
        return {"ok": False, "reason": "fullTextXML 返回非文章内容"}
    xml_path = outdir / f"{rec.get('pmid') or pmcid}.xml"
    xml_path.write_bytes(data)
    return {"ok": True, "via": "europepmc-fulltextxml", "xml": str(xml_path)}


def try_epmc_pdf(rec: dict, outdir: Path) -> dict:
    """第 2 级：EuropePMC 官方 PDF 端点。"""
    pmcid = rec.get("pmcid")
    if not pmcid:
        return {"ok": False, "reason": "无 PMCID"}
    pmid = rec.get("pmid") or pmcid
    pdf_path = outdir / f"{pmid}.pdf"
    url = f"{EPMC}/{pmcid}/fullTextPdf"
    try:
        data = _get(url)
        pdf_path.write_bytes(data)
    except Exception as e:
        return {"ok": False, "reason": f"EuropePMC PDF 端点失败: {e}"}
    if not _is_pdf(pdf_path):
        pdf_path.unlink(missing_ok=True)
        return {"ok": False, "reason": "EuropePMC 返回非 PDF"}
    return {"ok": True, "via": "europepmc-pdf", "pdf": str(pdf_path),
            "sha256": _sha256(pdf_path)}


def try_pmc_pow(rec: dict, outdir: Path) -> dict:
    """第 3 级：PMC PoW 求解下载（pmc_pdf.py）。"""
    pmcid = rec.get("pmcid")
    if not pmcid:
        return {"ok": False, "reason": "无 PMCID"}
    pmid = rec.get("pmid") or pmcid
    pdf_path = outdir / f"{pmid}.pdf"
    tool = SCRIPT_DIR / "pmc_pdf.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(tool), pmcid, str(pdf_path), "--quiet"],
            capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "pmc_pdf.py 超时"}
    if proc.returncode != 0 or not pdf_path.exists():
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return {"ok": False, "reason": f"pmc_pdf.py 失败: {tail[-1] if tail else 'unknown'}"}
    if not _is_pdf(pdf_path):
        pdf_path.unlink(missing_ok=True)
        return {"ok": False, "reason": "PMC 返回非 PDF（可能遭遇 reCAPTCHA）"}
    return {"ok": True, "via": "pmc-pow", "pdf": str(pdf_path),
            "sha256": _sha256(pdf_path)}


def try_unpaywall(rec: dict, outdir: Path, email: str) -> dict:
    """第 4 级：Unpaywall 定位 OA 直链。"""
    doi = rec.get("doi")
    if not doi or not email:
        return {"ok": False, "reason": "无 DOI 或未提供 --email"}
    try:
        info = json.loads(_get(f"{UNPAYWALL}/{urllib.parse.quote(doi)}?email={urllib.parse.quote(email)}"))
    except Exception as e:
        return {"ok": False, "reason": f"Unpaywall 查询失败: {e}"}
    if not info.get("is_oa"):
        return {"ok": False, "reason": "Unpaywall 判定非 OA，不下载"}
    url = None
    for loc in info.get("oa_locations", []):
        url = loc.get("url_for_pdf") or url
    if not url:
        return {"ok": False, "reason": "Unpaywall 无可用 PDF 直链"}
    pmid = rec.get("pmid") or hashlib.sha1(doi.encode()).hexdigest()[:12]
    pdf_path = outdir / f"{pmid}.pdf"
    try:
        pdf_path.write_bytes(_get(url))
    except Exception as e:
        return {"ok": False, "reason": f"OA 直链下载失败（常被出版社拦截）: {e}"}
    if not _is_pdf(pdf_path):
        pdf_path.unlink(missing_ok=True)
        return {"ok": False, "reason": "OA 直链返回非 PDF"}
    return {"ok": True, "via": "unpaywall", "pdf": str(pdf_path),
            "sha256": _sha256(pdf_path), "url": url}


def fetch_one(rec: dict, outdir: Path, email: str, only_oa: bool) -> dict:
    pmid = rec.get("pmid") or rec.get("pmcid") or "unknown"
    entry = {"pmid": pmid, "title": rec.get("title"), "steps": []}

    if only_oa and rec.get("is_open_access") is False:
        entry["status"] = "skipped"
        entry["reason"] = "非 OA（--only-oa 生效）"
        return entry

    for step in (lambda: try_epmc_fulltext(rec, outdir),
                 lambda: try_epmc_pdf(rec, outdir),
                 lambda: try_pmc_pow(rec, outdir),
                 lambda: try_unpaywall(rec, outdir, email)):
        result = step()
        entry["steps"].append(result)
        time.sleep(0.5)   # 对服务器友好
        if result.get("ok") and result.get("pdf"):
            entry["status"] = "ok"
            entry.update({k: result[k] for k in ("via", "pdf", "sha256") if k in result})
            return entry
        if result.get("ok"):
            # 第 1 级只证明 OA 并留档 XML，继续向下尝试拿 PDF
            continue

    entry["status"] = "failed"
    entry["reason"] = "四级降级链均失败"
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(description="批量下载 OA 文献 PDF（四级降级链）")
    ap.add_argument("input", help="pubmed_search.py 输出的 JSON")
    ap.add_argument("-o", "--outdir", required=True, help="PDF 输出目录")
    ap.add_argument("--email", default="", help="联系邮箱（Unpaywall 条款要求）")
    ap.add_argument("--only-oa", action="store_true", help="只尝试明确标注为 OA 的条目")
    ap.add_argument("--workers", type=int, default=2, help="并发数（默认 2，勿调高）")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        records = json.load(f)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_one, r, outdir, args.email, args.only_oa): r
                for r in records}
        for fut in as_completed(futs):
            entry = fut.result()
            manifest.append(entry)
            mark = {"ok": "✓", "skipped": "–", "failed": "✗"}.get(entry["status"], "?")
            print(f"  [{mark}] {entry['pmid']}: {entry.get('via') or entry.get('reason', '')}",
                  file=sys.stderr)

    mpath = outdir / "fetch_manifest.json"
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    ok = sum(1 for m in manifest if m["status"] == "ok")
    print(f"[done] {ok}/{len(manifest)} 篇 PDF 下载成功，清单 → {mpath}", file=sys.stderr)
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
