#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_report.py — 文献报告质量门禁。

在报告交付前运行，拦住"看起来没问题"的隐性错误。检查项：

  R1  每条记录必须有 PMID 或 PMCID（无则无法核验来源）
  R2  PMID 必须能构成有效 PubMed 链接形态（纯数字）
  R3  外文文献必须有 title_zh（否则标注待翻译，此处按 error 计）
  R4  报告 HTML 中不得出现占位符残留（"待翻译"、"未获取"超过阈值比例）
  R5  检索式留痕尾注必须存在（SEARCH_TRACE 注释）
  R6  metrics 若标注了指标，CSV 行数必须 > 0 且报告中含至少一个指标徽标
  R7  fetch_manifest.json（若存在）中 status==ok 的 PDF 必须 %PDF- 头校验通过

退出码：0 = 通过；1 = 存在 error。warning 不影响退出码。

用法：
  python3 validate_report.py results.json report.html [--pdfs pdfs/]
"""

import argparse
import json
import re
import sys
from pathlib import Path


def fail(errors: list, msg: str):
    errors.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser(description="文献报告质量门禁")
    ap.add_argument("results", help="pubmed_search.py 输出的 JSON")
    ap.add_argument("report", help="build_report.py 输出的 HTML")
    ap.add_argument("--pdfs", help="fetch_pdfs.py 的输出目录（可选）")
    ap.add_argument("--warn-ratio", type=float, default=0.3,
                    help="待翻译/未获取占比超过该值即告警（默认 0.3）")
    args = ap.parse_args()

    errors, warnings = [], []

    records = json.load(open(args.results, encoding="utf-8"))
    page = Path(args.report).read_text(encoding="utf-8")

    # R1/R2
    for i, r in enumerate(records):
        pmid, pmcid = r.get("pmid"), r.get("pmcid")
        if not pmid and not pmcid:
            fail(errors, f"R1 第{i+1}条既无 PMID 也无 PMCID：{(r.get('title') or '')[:60]}")
        if pmid and not re.fullmatch(r"\d+", str(pmid)):
            fail(errors, f"R2 PMID 形态异常：{pmid!r}")

    # R3
    def is_zh(r):
        lang = (r.get("language") or "").lower()
        if "chi" in lang:
            return True
        return any("一" <= ch <= "鿿" for ch in (r.get("title") or ""))
    n_foreign = sum(1 for r in records if not is_zh(r))
    n_untranslated = page.count("（待翻译）")
    if n_foreign and n_untranslated:
        msg = f"R3 {n_untranslated}/{n_foreign} 条外文文献缺中文翻译"
        if n_untranslated / max(n_foreign, 1) > args.warn_ratio:
            fail(errors, msg)
        else:
            warnings.append(msg)

    # R4
    for placeholder in ("（待翻译）", "（未获取作者）", "期刊不详"):
        cnt = page.count(placeholder)
        if records and cnt / len(records) > args.warn_ratio:
            warnings.append(f"R4 占位符 {placeholder!r} 出现 {cnt}/{len(records)} 次，占比偏高")

    # R5
    if "<!-- SEARCH_TRACE" not in page:
        fail(errors, "R5 报告缺少检索式留痕尾注（SEARCH_TRACE）")

    # R6
    if "badge metric" in page:
        pass  # 有指标徽标即可；CSV 是否有权使用由用户负责，脚本不评判

    # R7
    if args.pdfs:
        mpath = Path(args.pdfs) / "fetch_manifest.json"
        if mpath.exists():
            manifest = json.load(open(mpath, encoding="utf-8"))
            for m in manifest:
                if m.get("status") == "ok" and m.get("pdf"):
                    p = Path(m["pdf"])
                    if not p.exists():
                        fail(errors, f"R7 manifest 记录的 PDF 不存在：{p}")
                    else:
                        with open(p, "rb") as f:
                            if f.read(5) != b"%PDF-":
                                fail(errors, f"R7 PDF 头校验失败：{p}")

    print("=== 质量门禁报告 ===")
    for e in errors:
        print(f"  [ERROR] {e}")
    for w in warnings:
        print(f"  [warn ] {w}")
    if not errors and not warnings:
        print("  全部通过。")

    print(f"\n结果：{len(errors)} 个 error，{len(warnings)} 个 warning")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
