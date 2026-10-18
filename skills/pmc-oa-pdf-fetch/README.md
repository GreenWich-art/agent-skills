# pmc-oa-pdf-fetch

让 AI Agent 可靠地下载**开放获取（OA）**生物医学文献的 PDF 全文与补充材料：
从 PubMed Central 的反爬挑战（Proof-of-Work）离线求解，到出版社直链、
EuropePMC 补充材料，按固定优先级逐级降级，直到拿到文件为止。

## 这个工具适合你吗？

**适合谁**：需要频繁从 PubMed/PMC 获取文献全文的医学/生命科学研究生、科研人员、
文献调研重度用户，以及驱动这类工作的 AI Agent。

**典型场景**：

| 你遇到的情况 | 本工具的处理 |
|---|---|
| 「帮我下载这篇 PMC 文献的 PDF」 | 一条命令自动解析真实文件名 + 解 PoW 拿到全文 |
| PDF 直链返回 403 / 404 | PMC 的 PDF 文件名随期刊变化，硬编码必 404；本工具从文章页 `citation_pdf_url` 解析真实文件名 |
| 碰到 "Preparing to download..." 中间页 | 这是可离线求解的 PoW 挑战，`scripts/pmc_pdf.py` 亚秒级本地求解 |
| 碰到 reCAPTCHA 挑战页 | 自动诊断原因（UA 太完整/带了文章页 Cookie/IP 被限流），并给出出版社直链等降级路线 |
| 正文 PDF 没入库，只有网页全文 | EuropePMC `fullTextXML` 取结构化全文；`supplementaryFiles` 取图片和附表 |
| 下载下来的 PDF 打不开 | 内置完整性校验意识：文件头 + `%%EOF` 尾部 + 页数核验三重检查 |

**不适合谁**：

- 想绕过付费墙下载订阅制论文的人——本工具**明确拒绝**这一用途（仅 OA 或机构 IP 段内的人工量单篇下载）
- 需要批量抓取全库文献的人——即使有机构订阅，批量下载也违反出版商许可条款；大规模文本挖掘请走出版商官方 TDM API（如 Elsevier TDM API、Springer Nature Meta API）
- 非生物医学领域的文献获取（arXiv、IEEE 等不在这条链路的覆盖范围内）

## 快速开始

零依赖，只需要 Python 3 标准库：

```bash
python3 scripts/pmc_pdf.py PMC13575452 ./out.pdf
```

脚本会：从文章页解析真实 PDF 文件名（Cookie 即用即弃）→ 以全新会话冷请求 PDF →
若遇到 PoW 挑战则本地求解 sha256 nonce、回填 Cookie 重试 → 校验 `%PDF-` 文件头后落盘。

**注意**：第二个参数是输出文件的完整路径（含文件名），不是目录；
同一 PDF 短时间内重复请求会触发 reCAPTCHA，请第一次就把路径写对。

## 作为 Agent Skill 使用

把本目录放进你的 skills 目录（如 `~/.workbuddy/skills/`、`.claude/skills/`），
Agent 会在「下载文献 PDF」「PDF 链接 403」「Preparing to download」等场景自动加载本 Skill，
按其中的降级链和硬规则执行——包括什么时候**不该**重试、什么时候该换路线。

**与相近 skill 的边界**：

- 本 skill 是「**单篇**下载通道」，解决「这一篇怎么拿到」
- 若需要「检索一批文献 → 出报告 → 批量收 PDF」的流水线，
  属于文献报告类 skill 的职责（其内部可复用本 skill 的 `pmc_pdf.py` 作为一级降级）

## 文件说明

| 文件 | 说明 |
|---|---|
| `SKILL.md` | Agent Skill 定义与完整使用文档：五级降级链、PoW 原理与算法、已失效端点黑名单、故障排查表、完整性校验清单 |
| `scripts/pmc_pdf.py` | 核心下载脚本（约 170 行，纯标准库，可审计） |

## 合规边界

- 仅用于开放获取文献（CC BY 等）或机构订阅 IP 段内的人工量单篇下载
- 不绕过付费墙；不做批量抓取；不做机构认证（Shibboleth/OpenAthens）自动化
- Unpaywall 接口需按礼貌池惯例提供联系邮箱（`?email=` 参数）

## 系统要求

Python 3.8+（仅标准库），联网环境。macOS / Linux / Windows 均可运行。

## License

MIT © 2026 冯金岳 (Feng Jinyue)
