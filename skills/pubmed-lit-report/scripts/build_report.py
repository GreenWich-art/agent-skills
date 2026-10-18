#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_report.py — 把 pubmed_search.py 的 JSON 结果渲染成单文件 HTML 文献报告。

语言规则（本 skill 的硬性约定）：
  * 中文文献（language 含 'chi' 或标题为中文）：报告中只显示中文信息；
  * 英文及其他语种文献：双语对照——原文标题 + 中文翻译。
  * 翻译不由本脚本生成（脚本不联网、不含 LLM）。翻译由 Agent 或人工写入
    translations.json 后传入：
        { "PMID": { "title_zh": "...", "abstract_zh": "..." }, ... }
    未提供翻译的英文文献会标注「待翻译」，且 validate_report.py 会发出警告。

期刊指标（可选，可插拔）：
  --metrics metrics.csv，格式： journal_match,metric_name,metric_value
  例： Blood,JCR IF 2024,21.0
  匹配方式：期刊名归一化（小写、去标点）后做子串匹配。
  本 skill **不内置任何 IF 数据**——JCR 影响因子是 Clarivate 商业数据，
  请使用你有权使用的指标来源（机构订阅导出、Scimago 公开页面整理等）。

用法：
  python3 build_report.py results.json -o report.html
  python3 build_report.py results.json --translations trans.json --metrics m.csv -o report.html
"""

import argparse
import csv
import html
import json
import re
import sys
from datetime import datetime, timezone


def norm_journal(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (name or "").lower()).strip()


def is_chinese_article(rec: dict) -> bool:
    lang = (rec.get("language") or "").lower()
    if "chi" in lang:
        return True
    title = rec.get("title") or ""
    return any("一" <= ch <= "鿿" for ch in title)


def load_metrics(path: str) -> dict:
    table = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = norm_journal(row.get("journal_match", ""))
            if key:
                table[key] = (row.get("metric_name", ""), row.get("metric_value", ""))
    return table


def metric_for(journal: str, table: dict):
    j = norm_journal(journal)
    if not j:
        return None
    for key, val in table.items():
        if key in j or j in key:
            return val
    return None


CARD_TMPL = """
<article class="card" data-search="{search}">
  <div class="card-head">
    <span class="badge {langcls}">{langbadge}</span>
    {metric_badge}
    {oa_badge}
    <span class="date">{pubdate}</span>
  </div>
  <h2 class="title">{title}</h2>
  {title_zh_block}
  <p class="meta"><strong>{journal}</strong> ｜ {authors}</p>
  {abstract_block}
  <p class="links">
    <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/" target="_blank" rel="noopener">PMID {pmid}</a>
    {doi_link}{pmc_link}
  </p>
</article>"""

PAGE_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --fg:#1a1a2e; --muted:#667; --line:#e3e3ee; --accent:#2456a6; --bg:#f7f7fb; --card:#fff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
       background:var(--bg); color:var(--fg); line-height:1.65; }}
header {{ background:var(--card); border-bottom:1px solid var(--line); padding:18px 24px;
         position:sticky; top:0; z-index:5; }}
header h1 {{ font-size:18px; margin:0 0 10px; }}
.controls {{ display:flex; gap:10px; flex-wrap:wrap; }}
.controls input, .controls select {{ padding:8px 10px; border:1px solid var(--line);
  border-radius:6px; font-size:14px; }}
.controls input[type=search] {{ flex:1; min-width:220px; }}
main {{ max-width:920px; margin:0 auto; padding:20px 16px 60px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
        padding:16px 20px; margin-bottom:16px; }}
.card-head {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap;
             font-size:12px; color:var(--muted); }}
.badge {{ padding:2px 8px; border-radius:10px; font-size:12px; }}
.badge.zh {{ background:#fdecec; color:#a33; }}
.badge.en {{ background:#e8f0fd; color:#2456a6; }}
.badge.oa {{ background:#e7f6ec; color:#1e7a3c; }}
.badge.metric {{ background:#fff4e0; color:#9a6a00; }}
.date {{ margin-left:auto; }}
.title {{ font-size:16.5px; margin:8px 0 2px; }}
.title-zh {{ font-size:15px; color:var(--accent); margin:0 0 6px; }}
.meta {{ font-size:13.5px; color:var(--muted); margin:6px 0; }}
.abstract {{ font-size:13.5px; margin:8px 0 0; }}
.abstract.zh {{ border-left:3px solid var(--accent); padding-left:10px; color:#333; }}
.links {{ font-size:13px; margin:10px 0 0; }}
.links a {{ color:var(--accent); margin-right:14px; text-decoration:none; }}
.links a:hover {{ text-decoration:underline; }}
.summary {{ font-size:13px; color:var(--muted); margin:0 0 14px; }}
footer {{ text-align:center; font-size:12px; color:var(--muted); padding:20px; }}
.hidden {{ display:none; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="controls">
    <input type="search" id="q" placeholder="搜索标题 / 作者 / 期刊 / 摘要…">
    <select id="langf">
      <option value="">全部语种</option><option value="zh">中文文献</option>
      <option value="en">双语（外文）文献</option>
    </select>
    <select id="oaf">
      <option value="">全部</option><option value="oa">仅开放获取</option>
    </select>
  </div>
</header>
<main>
<p class="summary">{summary}</p>
{cards}
</main>
<footer>由 pubmed-lit-report 生成 ｜ 生成时间 {gentime} ｜ 检索窗口 {window} ｜ 检索式留痕见报告尾注</footer>
<script>
const q = document.getElementById('q'), lf = document.getElementById('langf'),
      of = document.getElementById('oaf'), cards = [...document.querySelectorAll('.card')];
function apply() {{
  const kw = q.value.trim().toLowerCase();
  for (const c of cards) {{
    let ok = true;
    if (kw) ok = c.dataset.search.toLowerCase().includes(kw);
    if (ok && lf.value) ok = c.dataset.lang === lf.value;
    if (ok && of.value) ok = c.dataset.oa === 'oa';
    c.classList.toggle('hidden', !ok);
  }}
}}
q.addEventListener('input', apply); lf.addEventListener('change', apply); of.addEventListener('change', apply);
</script>
</body>
</html>"""


def esc(s) -> str:
    return html.escape(str(s)) if s else ""


def build(records: list, translations: dict, metrics: dict) -> str:
    cards = []
    n_zh = n_en = n_oa = 0
    for r in records:
        zh = is_chinese_article(r)
        pmid = r.get("pmid") or ""
        tr = translations.get(pmid, {})
        is_oa = bool(r.get("is_open_access"))

        if zh:
            n_zh += 1
            langbadge, langcls = "中文文献", "zh"
            title = esc(r.get("title")) or "（无题录标题）"
            title_zh_block = ""
            abstract_block = (f'<p class="abstract">{esc(r["abstract"])}</p>'
                              if r.get("abstract") else "")
        else:
            n_en += 1
            langbadge, langcls = "双语对照", "en"
            title = esc(r.get("title")) or "（无题录标题）"
            tzh = tr.get("title_zh")
            title_zh_block = (f'<p class="title-zh">{esc(tzh)}</p>' if tzh
                              else '<p class="title-zh">（待翻译）</p>')
            parts = []
            if r.get("abstract"):
                parts.append(f'<p class="abstract">{esc(r["abstract"])}</p>')
            if tr.get("abstract_zh"):
                parts.append(f'<p class="abstract zh">{esc(tr["abstract_zh"])}</p>')
            abstract_block = "\n".join(parts)

        if is_oa:
            n_oa += 1
        metric = metric_for(r.get("journal") or "", metrics)
        metric_badge = (f'<span class="badge metric">{esc(metric[0])} {esc(metric[1])}</span>'
                        if metric else "")
        oa_badge = '<span class="badge oa">OA</span>' if is_oa else ""

        authors = ", ".join(r.get("authors") or []) or "（未获取作者）"
        doi = r.get("doi")
        doi_link = (f'<a href="https://doi.org/{esc(doi)}" target="_blank" rel="noopener">DOI</a>'
                    if doi else "")
        pmcid = r.get("pmcid")
        pmc_link = (f'<a href="https://pmc.ncbi.nlm.nih.gov/articles/{esc(pmcid)}/" '
                    f'target="_blank" rel="noopener">PMC</a>' if pmcid else "")

        search_blob = " ".join([title, authors, r.get("journal") or "",
                                r.get("abstract") or "", tr.get("title_zh", ""),
                                tr.get("abstract_zh", "")])
        card = (CARD_TMPL
                .replace("{search}", esc(search_blob))
                .replace("{langbadge}", langbadge).replace("{langcls}", langcls)
                .replace("{metric_badge}", metric_badge)
                .replace("{oa_badge}", oa_badge)
                .replace("{pubdate}", esc(r.get("pubdate") or "日期不详"))
                .replace("{title}", title)
                .replace("{title_zh_block}", title_zh_block)
                .replace("{journal}", esc(r.get("journal") or "期刊不详"))
                .replace("{authors}", esc(authors))
                .replace("{abstract_block}", abstract_block)
                .replace("{pmid}", esc(pmid) if pmid else "（无 PMID）")
                .replace("{doi_link}", doi_link)
                .replace("{pmc_link}", pmc_link))
        # dataset 属性
        card = card.replace('<article class="card"',
                            f'<article class="card" data-lang="{langcls}" data-oa="{"oa" if is_oa else ""}"', 1)
        cards.append(card)

    first = records[0] if records else {}
    term = first.get("_search_term", "（未知检索式）")
    window = first.get("_search_window", "（未知窗口）")
    summary = (f"共 {len(records)} 条：中文文献 {n_zh} 条（纯中文展示），"
               f"外文文献 {n_en} 条（双语对照），开放获取 {n_oa} 条。"
               f"检索式：{esc(term)}")
    page = (PAGE_TMPL
            .replace("{title}", f"文献检索报告：{esc(term)}")
            .replace("{summary}", summary)
            .replace("{cards}", "\n".join(cards))
            .replace("{gentime}", datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z"))
            .replace("{window}", esc(window)))
    # 尾注：检索式留痕（质量门禁要求）
    page += f"\n<!-- SEARCH_TRACE term={term!r} window={window!r} n={len(records)} -->\n"
    return page


def main() -> int:
    ap = argparse.ArgumentParser(description="检索结果 JSON → 单文件 HTML 文献报告")
    ap.add_argument("input", help="pubmed_search.py 输出的 JSON")
    ap.add_argument("--translations", help="翻译 JSON（PMID → title_zh/abstract_zh）")
    ap.add_argument("--metrics", help="期刊指标 CSV（journal_match,metric_name,metric_value）")
    ap.add_argument("-o", "--output", required=True, help="输出 HTML 路径")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        records = json.load(f)
    translations = {}
    if args.translations:
        with open(args.translations, encoding="utf-8") as f:
            translations = json.load(f)
    metrics = load_metrics(args.metrics) if args.metrics else {}

    page = build(records, translations, metrics)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"[done] {len(records)} 条 → {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
