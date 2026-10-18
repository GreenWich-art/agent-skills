#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pubmed_search.py — PubMed / EuropePMC 文献检索（纯标准库，零依赖）

输出 JSON：每篇文献含 pmid / doi / pmcid / title / authors / journal / pubdate /
abstract / language / is_open_access / oa_pdf_url。

用法：
  python3 pubmed_search.py --query "sepsis coagulation" --days 365 --max 50 -o results.json
  python3 pubmed_search.py --author "Levi M" --affiliation "Amsterdam" --days 1825 -o out.json
  python3 pubmed_search.py --query "凝血功能障碍" --days 730 -o out.json   # 中文关键词走 EuropePMC

设计说明：
  * PubMed E-utilities（esearch/esummary/efetch XML）为主通道，EuropePMC REST 为备通道
    与中文/非拉丁关键词通道（PubMed 对中文检索支持很差）。
  * 遵守 NCBI 使用条款：无 API key 时限速 3 req/s（脚本内置 0.4s 间隔），
    强烈建议通过 --api-key 或环境变量 NCBI_API_KEY 提供个人 key（免费申请，
    https://www.ncbi.nlm.nih.gov/account/ ），限速升至 10 req/s。
  * 不提供 PMID 之外无法核验的字段；缺失字段显式置 null 而非猜测。
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UA = "pubmed-lit-report/1.0 (literature search; mailto:set-NCBI-tool-email)"
REQ_INTERVAL = 0.4          # 无 key 时遵守 3 req/s
REQ_INTERVAL_KEY = 0.12     # 有 key 时 10 req/s 留余量

_last_call = [0.0]


def _throttle(has_key: bool):
    gap = REQ_INTERVAL_KEY if has_key else REQ_INTERVAL
    dt = time.time() - _last_call[0]
    if dt < gap:
        time.sleep(gap - dt)
    _last_call[0] = time.time()


def _get_json(url: str, has_key: bool) -> dict:
    _throttle(has_key)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_text(url: str, has_key: bool) -> str:
    _throttle(has_key)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


# ---------------------------------------------------------------- PubMed

def pubmed_search(term: str, mindate: str, maxdate: str, maxn: int,
                  api_key: str = "") -> list:
    """返回 PMID 列表。mindate/maxdate 格式 YYYY/MM/DD。"""
    q = {
        "db": "pubmed", "term": term, "retmax": str(maxn), "retmode": "json",
        "datetype": "pdat", "mindate": mindate, "maxdate": maxdate,
        "sort": "relevance",
    }
    if api_key:
        q["api_key"] = api_key
    url = f"{EUTILS}/esearch.fcgi?{urllib.parse.urlencode(q)}"
    data = _get_json(url, bool(api_key))
    return data.get("esearchresult", {}).get("idlist", [])


def pubmed_fetch(pmids: list, api_key: str = "") -> list:
    """efetch XML → 结构化记录列表。"""
    if not pmids:
        return []
    q = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    if api_key:
        q["api_key"] = api_key
    url = f"{EUTILS}/efetch.fcgi?{urllib.parse.urlencode(q)}"
    xml_text = _get_text(url, bool(api_key))
    root = ET.fromstring(xml_text)

    out = []
    for art in root.iter("PubmedArticle"):
        rec = {"pmid": None, "doi": None, "pmcid": None, "title": None,
               "authors": [], "journal": None, "pubdate": None,
               "abstract": None, "language": None}
        med = art.find("MedlineCitation")
        if med is None:
            continue
        pmid_el = med.find("PMID")
        rec["pmid"] = pmid_el.text.strip() if pmid_el is not None else None

        article = med.find("Article")
        if article is not None:
            t = article.find("ArticleTitle")
            rec["title"] = "".join(t.itertext()).strip() if t is not None else None

            lang = article.find("Language")
            rec["language"] = lang.text.strip() if lang is not None else None

            ab = article.find("Abstract")
            if ab is not None:
                parts = []
                for at in ab.iter("AbstractText"):
                    label = at.get("Label")
                    txt = "".join(at.itertext()).strip()
                    parts.append(f"{label}: {txt}" if label else txt)
                rec["abstract"] = "\n".join(parts) or None

            j = article.find("Journal")
            if j is not None:
                jt = j.find("Title")
                rec["journal"] = jt.text.strip() if jt is not None else None
                pd_el = j.find("JournalIssue/PubDate")
                if pd_el is not None:
                    y = pd_el.findtext("Year") or ""
                    mth = pd_el.findtext("Month") or ""
                    med_d = pd_el.findtext("MedlineDate") or ""
                    rec["pubdate"] = (f"{y}-{mth}" if y else med_d).strip("-") or None

            al = article.find("AuthorList")
            if al is not None:
                for a in al.iter("Author"):
                    last = a.findtext("LastName") or ""
                    fore = a.findtext("ForeName") or ""
                    coll = a.findtext("CollectiveName")
                    if coll:
                        rec["authors"].append(coll.strip())
                    elif last:
                        rec["authors"].append(f"{last} {fore}".strip())

        for aid in art.iter("ArticleId"):
            t, v = aid.get("IdType"), (aid.text or "").strip()
            if t == "doi" and v:
                rec["doi"] = v
            elif t == "pmc" and v:
                rec["pmcid"] = v
        out.append(rec)
    return out


# ---------------------------------------------------------------- EuropePMC

def epmc_search(query: str, maxn: int) -> list:
    """EuropePMC 检索，输出与 PubMed 通道同构的记录（用于中文关键词或 PubMed 失败降级）。"""
    q = {"query": query, "format": "json", "pageSize": str(maxn),
         "resultType": "core", "sort": "RELEVANCE"}
    url = f"{EPMC}/search?{urllib.parse.urlencode(q)}"
    data = _get_json(url, False)
    out = []
    for it in data.get("resultList", {}).get("result", []):
        out.append({
            "pmid": it.get("pmid") or None,
            "doi": it.get("doi") or None,
            "pmcid": it.get("pmcid") or None,
            "title": it.get("title") or None,
            "authors": [a.strip() for a in (it.get("authorString") or "").split(",") if a.strip()],
            "journal": it.get("journalTitle") or None,
            "pubdate": it.get("firstPublicationDate") or it.get("pubYear") or None,
            "abstract": it.get("abstractText") or None,
            "language": None,   # EuropePMC core 结果不直接给语言，由报告层兜底判断
            "is_open_access": it.get("isOpenAccess") == "Y",
            "oa_pdf_url": None,  # 由 PDF 模块另行解析
        })
    return out


def epmc_enrich_oa(records: list) -> list:
    """为每条有 PMCID 的记录标注 OA 状态（EuropePMC 单条查询，限速）。"""
    for r in records:
        if r.get("pmcid") and r.get("is_open_access") is None:
            try:
                q = {"query": f"EXT_ID:{r['pmid']} AND SRC:MED" if r.get("pmid")
                     else f"PMCID:{r['pmcid']}",
                     "format": "json", "resultType": "lite"}
                url = f"{EPMC}/search?{urllib.parse.urlencode(q)}"
                data = _get_json(url, False)
                hits = data.get("resultList", {}).get("result", [])
                if hits:
                    r["is_open_access"] = hits[0].get("isOpenAccess") == "Y"
            except Exception:
                r["is_open_access"] = None
    return records


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="PubMed / EuropePMC 文献检索 → JSON")
    ap.add_argument("--query", help="PubMed 检索式（支持 AND/OR/NOT、[MeSH] 等语法）")
    ap.add_argument("--author", help="作者姓名（如 'Levi M'），与 --query 二选一")
    ap.add_argument("--affiliation", help="配合 --author 收窄单位（可选）")
    ap.add_argument("--days", type=int, default=365, help="向前回溯天数（默认 365）")
    ap.add_argument("--max", type=int, default=50, dest="maxn", help="最大返回条数（默认 50）")
    ap.add_argument("--api-key", default="", help="NCBI API key（或设环境变量 NCBI_API_KEY）")
    ap.add_argument("-o", "--output", required=True, help="输出 JSON 路径")
    args = ap.parse_args()

    import os
    api_key = args.api_key or os.environ.get("NCBI_API_KEY", "")

    if args.author:
        term = f'{args.author}[Author]'
        if args.affiliation:
            term += f' AND {args.affiliation}[Affiliation]'
    elif args.query:
        term = args.query
    else:
        ap.error("必须提供 --query 或 --author 之一")

    maxdate = date.today().strftime("%Y/%m/%d")
    mindate = (date.today() - timedelta(days=args.days)).strftime("%Y/%m/%d")

    # 中文/非 ASCII 关键词：PubMed 几乎搜不到，直接走 EuropePMC
    has_cjk = any("一" <= ch <= "鿿" for ch in term)

    records = []
    channel = "pubmed"
    if has_cjk:
        channel = "europepmc"
        print(f"[info] 检测到中文关键词，使用 EuropePMC 通道", file=sys.stderr)
        records = epmc_search(f"{term} AND FIRST_PDATE:[{mindate.replace('/', '-')} TO {maxdate.replace('/', '-')}]",
                              args.maxn)
    else:
        try:
            pmids = pubmed_search(term, mindate, maxdate, args.maxn, api_key)
            print(f"[info] PubMed 命中 {len(pmids)} 条，正在抓取元数据…", file=sys.stderr)
            records = pubmed_fetch(pmids, api_key)
        except Exception as e:
            print(f"[warn] PubMed 通道失败（{e}），降级 EuropePMC", file=sys.stderr)
            channel = "europepmc"
            records = epmc_search(term, args.maxn)

    if channel == "pubmed":
        epmc_enrich_oa(records)

    for r in records:
        r.setdefault("is_open_access", None)
        r.setdefault("oa_pdf_url", None)
        r["_search_channel"] = channel
        r["_search_term"] = term
        r["_search_window"] = f"{mindate}..{maxdate}"

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"[done] {len(records)} 条 → {args.output}（通道: {channel}）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
