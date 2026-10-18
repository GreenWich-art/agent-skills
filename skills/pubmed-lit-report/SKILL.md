---
name: pubmed-lit-report
display_name: "PubMed 文献检索报告"
display_name_en: "PubMed Literature Report"
version: 1.0.1
author: 冯金岳 (Feng Jinyue)
license: MIT
description_zh: "PubMed / EuropePMC 文献检索 → 单文件 HTML 双语报告 → OA 全文 PDF 下载 → 质量门禁，一站式流水线。中文文献纯中文展示、外文文献双语对照；期刊指标可插拔（用户自供 CSV，不内置任何 IF 数据）；PDF 只下开放获取，含 PMC PoW 离线求解；交付前 7 项质量门禁。触发词：PubMed 检索、文献报告、文献调研、下载文献 PDF。"
description_en: "One-stop literature pipeline: PubMed/EuropePMC search → single-file HTML report (Chinese articles in Chinese, foreign articles bilingual with translations) → open-access PDF download (incl. offline PMC proof-of-work solver) → 7-rule quality gate. Journal metrics are pluggable via user-supplied CSV — no proprietary IF data bundled. Triggers: PubMed search, literature report, download paper PDFs."
description: |
  PubMed / EuropePMC 检索 → 双语 HTML 报告 → OA PDF 下载 → 质量门禁 的完整流水线。

  触发场景：
  - "帮我检索某个关键词/某位作者的 PubMed 文献并生成报告"
  - "把这些文献的 PDF 全文下载下来"（仅开放获取）
  - "检索结果整理成可搜索筛选的 HTML，英文文献要中文翻译对照"
  - 需要期刊指标标注（用户提供自己有权限使用的指标 CSV）

  与其他 skill 的边界：参考文献著录格式（GB/T 7714）用 `gbt7714-reference-check`；
  出凝血方向每日精读自动化流水线是更上层的专用流程。
tags:
  - pubmed
  - literature-search
  - biomedical
  - open-access
  - research
---

# PubMed 文献检索报告流水线

四步流水线，每步有独立脚本，全部**纯 Python 标准库**（零 pip 依赖）：

```
pubmed_search.py   →   results.json
（Agent 翻译环节）→   translations.json
build_report.py    →   report.html
fetch_pdfs.py      →   pdfs/（仅 OA）
validate_report.py →   交付前质量门禁（退出码 0 才可交付）
```

## 第 1 步：检索

```bash
python3 scripts/pubmed_search.py --query "sepsis coagulation" --days 365 --max 50 -o results.json
python3 scripts/pubmed_search.py --author "Levi M" --affiliation "Amsterdam" --days 1825 -o results.json
```

- **双通道**：英文走 NCBI E-utilities；中文关键词自动切 EuropePMC（PubMed 对中文支持极差）；
  PubMed 故障时自动降级 EuropePMC
- **限速合规**：无 key 3 req/s；建议用户申请免费 NCBI API key（`--api-key` 或 `NCBI_API_KEY` 环境变量）
- **绝不编造**：缺失字段显式 `null`，不猜测；每条记录留痕检索式与时间窗
- 时间窗用相对天数（`--days`），保证检索可复现

## 第 2 步：翻译（Agent / 人工环节）

脚本不内置 LLM。外文文献的中文翻译由 Agent 运行时生成，写入 `translations.json`：

```json
{ "PMID": { "title_zh": "...", "abstract_zh": "（可选）" } }
```

**语言硬规则**：中文文献（language=chi 或中文标题）→ 报告纯中文展示；
外文文献 → 双语对照（原文 + 中文翻译）。未翻译的会标「待翻译」并被质量门禁拦截。

## 第 3 步：生成报告

```bash
python3 scripts/build_report.py results.json --translations translations.json -o report.html
python3 scripts/build_report.py results.json --metrics metrics.csv -o report.html
```

- 单文件 HTML：搜索框、语种筛选、OA 筛选，无外部依赖，可直接转发
- **期刊指标可插拔**：`--metrics metrics.csv`（格式 `journal_match,metric_name,metric_value`）。
  本 skill **不内置任何影响因子数据**——JCR IF 是 Clarivate 商业数据，
  请使用你有权使用的来源（机构订阅导出、公开数据自行整理）

## 第 4 步：下载 OA 全文 PDF（可选）

```bash
python3 scripts/fetch_pdfs.py results.json -o pdfs/ --email you@example.org --only-oa
```

**只下开放获取文献**，四级降级链：

| 级 | 途径 | 说明 |
|---|---|---|
| 1 | EuropePMC fullTextXML | 证明 OA 并留档 XML |
| 2 | EuropePMC 官方 PDF 端点 | 最稳定 |
| 3 | PMC PoW 离线求解（`pmc_pdf.py`） | 对 PMC 反爬的 sha256 工作量证明求解 |
| 4 | Unpaywall OA 直链 | 需 `--email`（其使用条款要求） |

每个 PDF 做 `%PDF-` 头校验 + SHA256 登记到 `fetch_manifest.json`；
并发默认 2，勿调高（对 NCBI 友好）。**不绕过付费墙**——非 OA 文献跳过并记录原因。

## 第 5 步：质量门禁（交付前必跑）

```bash
python3 scripts/validate_report.py results.json report.html --pdfs pdfs/
```

7 项规则：R1 必有 PMID/PMCID；R2 PMID 形态合法；R3 外文必须有翻译（>30% 缺失即 error）；
R4 占位符占比告警；R5 检索式留痕尾注；R6 指标徽标检查；R7 manifest 中 PDF 头校验。
**退出码非 0 不得交付。**

报告中的链接可再用 `scripts/check_refs.py` 批量核验（区分真死链与反爬拦截）。

## 质量红线（不可违背）

1. **绝不编造**：任何字段缺失就显式标注，不用训练记忆补全文献信息
2. **只下 OA**：Unpaywall `is_oa` 或 EuropePMC `isOpenAccess` 至少其一确认为真才下载
3. **可复现**：检索式与时间窗必须留痕在报告尾注
4. **合规限速**：对 NCBI/EuropePMC 的请求间隔与并发限制不得放宽

## 系统要求

Python 3.9+，纯标准库，零 pip 依赖。联网（NCBI / EuropePMC / Unpaywall 可及）。
