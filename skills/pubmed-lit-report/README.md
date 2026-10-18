# pubmed-lit-report

PubMed / EuropePMC 文献检索 → **单文件 HTML 双语报告** → 开放获取 PDF 批量下载 →
交付前质量门禁，一条流水线全包。纯 Python 标准库，零 pip 依赖。

这是一个 **Agent Skill**（放进 skills 目录后 Agent 自动按流水线执行），
每个脚本也可独立命令行使用。

## 这个工具适合你吗？

**适合谁**：医学、生命科学方向的研究生与科研人员；需要快速摸清一个关键词/
一位作者的文献产出的临床医生；写综述前要做文献初筛的人。

**典型场景**：

| 场景 | 它能做什么 |
|---|---|
| "帮我查最近一年 X 方向的文献，整理成能搜索筛选的报告" | 检索 → 单文件 HTML（搜索框/语种/OA 筛选），直接转发给导师 |
| 英文文献读起来慢，想要中文对照 | 外文文献双语对照（标题+摘要翻译槽），中文文献自动纯中文展示 |
| "把这些文献的 PDF 下下来" | 只下开放获取：四级降级链（EuropePMC → 官方 PDF → PMC PoW 求解 → Unpaywall），每篇 SHA256 登记 |
| 报告要标注期刊水平 | 可插拔指标 CSV——**不内置 IF 数据**（JCR 是 Clarivate 商业数据），用你有权使用的来源 |
| 怕 AI 编的文献信息 | 7 项质量门禁：PMID 形态、翻译覆盖率、检索式留痕、PDF 头校验，退出码非 0 不得交付 |

**不适合谁**：需要 GB/T 7714 参考文献**著录格式**（那是 citation 格式化，用
`gbt7714-reference-check`）；想绕过付费墙下订阅文献（本工具**只下 OA**，且这是设计原则
不是缺陷）；非生物医学领域（PubMed 库覆盖范围外）。

## 快速开始

```bash
# 1. 检索（英文走 PubMed，中文关键词自动切 EuropePMC）
python3 scripts/pubmed_search.py --query "sepsis coagulation" --days 365 --max 50 -o results.json

# 2. 翻译（Agent 或人工写 translations.json，可选但推荐）
#    { "PMID": {"title_zh": "...", "abstract_zh": "..."} }

# 3. 生成双语报告
python3 scripts/build_report.py results.json --translations translations.json -o report.html

# 4. 下载 OA 全文（可选）
python3 scripts/fetch_pdfs.py results.json -o pdfs/ --email you@example.org --only-oa

# 5. 交付前质量门禁（必跑）
python3 scripts/validate_report.py results.json report.html --pdfs pdfs/
```

## 设计原则

1. **绝不编造**：缺失字段显式 `null`，不用模型记忆补全文献信息
2. **只下开放获取**：EuropePMC 或 Unpaywall 至少其一确认为 OA 才下载，不绕付费墙
3. **可复现**：检索式与时间窗留痕在报告尾注
4. **合规**：NCBI 限速 3 req/s（建议申请免费 API key 升至 10 req/s）、并发默认 2
5. **零依赖**：纯标准库，任何 Python 3.9+ 环境直接跑

## 文件说明

| 文件 | 说明 |
|---|---|
| `SKILL.md` | Agent Skill 定义与完整流水线文档 |
| `scripts/pubmed_search.py` | 双通道检索（E-utilities + EuropePMC）→ JSON |
| `scripts/build_report.py` | JSON → 单文件 HTML（双语/筛选/OA 标记） |
| `scripts/fetch_pdfs.py` | OA PDF 四级降级下载 + SHA256 清单 |
| `scripts/pmc_pdf.py` | PMC Proof-of-Work 离线求解下载器 |
| `scripts/validate_report.py` | 7 项质量门禁 |
| `scripts/check_refs.py` | 报告链接批量核验（区分真死链与反爬） |
| `references/journal_metrics_example.csv` | 可插拔期刊指标 CSV 的格式示例 |

## License

MIT © 2026 冯金岳 (Feng Jinyue)
