---
name: pmc-oa-pdf-fetch
display_name: "PMC 开放获取文献下载"
display_name_en: "PMC OA PDF Fetch"
version: "1.0.0"
author: "冯金岳 (Feng Jinyue)"
license: "MIT"
description_zh: "下载开放获取（OA）生物医学文献的 PDF 全文与补充材料。按「EuropePMC fullTextXML → Unpaywall 定位 OA 位置 → PMC PoW 求解 → EuropePMC supplementaryFiles → 出版社直链」的固定优先级逐级降级。触发场景：需要下载 PubMed/PMC 文献 PDF 全文、EuropePMC 全文、或补充材料（图片/附表）；文献 PDF 直链返回 403/404；遇到 PMC「Preparing to download ...」中间页或 reCAPTCHA 挑战页；需要绕过出版社 Cloudflare 拦截获取 OA 全文。"
description_en: "Download open-access (OA) biomedical article PDFs and supplementary files. Fixed-priority degradation chain: EuropePMC fullTextXML → Unpaywall OA location → PMC Proof-of-Work solving → EuropePMC supplementaryFiles → publisher direct link. Triggers: download PubMed/PMC full-text PDFs; PDF links returning 403/404; PMC 'Preparing to download' interstitial or reCAPTCHA pages; bypassing publisher Cloudflare blocks for OA content."
description: "Download open-access biomedical article PDFs from PMC with offline Proof-of-Work solving. Triggers: 下载文献PDF, PMC PDF, 403/404 on PDF link, Preparing to download, reCAPTCHA page, OA full text, supplementary files, download paper PDF."
tags:
  - pubmed
  - pmc
  - pdf
  - literature
  - open-access
  - biomedical
---

# PMC / OA 文献 PDF 获取

## 适用前提

只用于**开放获取（OA）**文献（CC BY / CC BY-NC / CC BY-NC-ND 等）。不要用于绕过付费墙获取订阅制论文——
那属于规避版权保护。判断 OA 状态：Unpaywall 返回 `is_oa: true`，或 EuropePMC 的 `isOpenAccess: Y`。

## 机构订阅场景（重要补充）

用户所在学校/单位订阅了出版商数据库时，**人工单篇下载**在授权范围内完全合规，但需注意：

- **校园网 / 机构 IP 段内**：出版商认 IP 不认人，降级链第 5 级（出版社直链）通常直接返回 200，
  Cloudflare 也不会拦截——此时本 skill 的现有管线可以直接拿到订阅内容，无需任何登录逻辑。
- **校外访问**：优先使用学校提供的**系统级 VPN**（对脚本透明，配置一次即可）；
  WebVPN（URL 改写型代理）因各校改写规则不同、且需携带会话 Cookie，本 skill 不做支持。
- **不要写 Shibboleth / OpenAthens 自动登录**：需要本地存储统一身份认证凭证，属安全隐患；
  且各校 IdP 流程差异大，通用实现不可行。
- **批量下载红线**：几乎所有出版商的机构许可都区分「人工单篇下载」与 systematic/bulk downloading。
  **即使有订阅，脚本批量抓取也违反许可条款**，可导致全校 IP 段被封禁。确有大规模全文挖掘需求时，
  应申请出版商的 TDM（文本挖掘）API（如 Elsevier TDM API、Springer Nature Meta API），
  走官方配额通道，而不是用本 skill 批量循环。

## 降级链（严格按顺序）

| 优先级 | 途径 | 命令 / 端点 | 说明 |
|:--:|:--|:--|:--|
| 1 | EuropePMC 结构化全文 | `https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML` | **最稳定**。用于提取精确到二级标题的全文结构。返回 JATS XML |
| 2 | Unpaywall 定位 OA 位置 | `https://api.unpaywall.org/v2/{DOI}?email=you@example.org` | 读 `oa_locations[].url_for_pdf`，直接给出 PDF 直链 |
| 3 | **PMC PoW 求解下载** | `scripts/pmc_pdf.py <PMCID> <out.pdf>` | 见下文。**获取正文 PDF 的主力方案** |
| 4 | EuropePMC 补充材料 | `https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/supplementaryFiles` | 返回 ZIP：原始图片（`gr1`…=Figure 1…）+ 补充材料 PDF（`mmc1.pdf`） |
| 5 | 出版社直链 | 各出版社 `.../article-pdf/...` | 通常 403（Cloudflare）。**最后才试** |

## 已确认失效的端点（不要浪费时间）

- `…/rest/{PMCID}/fullTextPDF` → **404**（已废弃）
- `…/rest/{PMCID}/fulltextRepo` → **403**
- `https://europepmc.org/articles/{PMCID}?pdf=render` → **403**
- `https://europepmc.org/backend/ptpmcrender.fcgi?accid=…&blobtype=pdf` → **403**
- `https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=…` → **404**（OA service 已迁移）
- `ashpublications.org` 文章页在无头浏览器中停留于 Cloudflare「请稍候…」挑战页，不可用

## ★ 先决条件：PMC 的 PDF 文件名**不固定**，必须先解析

`https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/pdf/<文件名>.pdf` 中的**文件名随期刊与年份变化**，硬编码 `main.pdf` 在多数情况下会 404。

| 实测期刊 | 真实文件名 |
|:--|:--|
| Am J Hematol | `main.pdf` |
| Blood Advances | `main.pdf` |
| HemaSphere | `HEM3-10-e70338.pdf` |
| Am J Hematol | `AJH-101-1790.pdf` |
| Liver International | `LIV-46-0.pdf` |
| **Haematologica** | **`111300.pdf`**（卷 111 + 起始页 300，**省略期刊缩写**） |
| Blood（NIH 作者稿） | `nihms-2192199.pdf` |

**解析方法（按优先级；实测多例全部命中第 1 条）**

1. 文章页 `<meta name="citation_pdf_url" content="https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/pdf/XXX.pdf">` ← **最可靠**
2. `grep -oE 'href="[^"]*?/pdf/[^"]+?\.pdf"'` 取第一个命中
3. 兜底 `pdf/main.pdf`

命名规律参考（不可依赖，仅用于人工判断是否解析正确）：Wiley 系 OA 常见 `<期刊缩写>-<印刷卷>-0.pdf`（如 `LIV-46-0.pdf`）；带文章号时为 `<期刊缩写>-<卷>-<文章号>.pdf`（如 `HEM3-10-e70338.pdf`）；同刊常为 `<缩写>-<卷>-<起始页>.pdf`（如 `AJH-101-1790.pdf`）；**亦有「卷+起始页、无期刊缩写」变体（如 Haematologica 的 `111300.pdf` = 卷 111 + 起始页 300）**。

> **抓文章页时务必丢弃 Cookie**：用一个**独立的**、不保留 Cookie 的请求去读文章页，PDF 请求仍必须从**全新 Cookie 会话**发起。若把文章页产生的 `ncbi_sid` / `ncbi_pinger` 带到 PDF 请求上，会被直接升级为 reCAPTCHA（实测）。`scripts/pmc_pdf.py` 已按此实现。

## 核心方案：离线求解 PMC Proof-of-Work

### 原理

`https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/pdf/<文件名>.pdf` 会按风险策略在**两种挑战页**之间切换：

- **PoW 页**（1817 字节，标题 `Preparing to download ...`）→ **可离线求解**，这是我们要的通道；
- **reCAPTCHA 页**（约 20 KB，标题含 `reCAPTCHA`）→ 无法离线求解。

**触发 PoW 而非 reCAPTCHA 的关键：使用简约 UA，且不要在请求 PDF 之前访问文章页。**

```
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)
```

反例（会被升级为 reCAPTCHA，实测）：
- 完整 Chrome UA（`…AppleWebKit/537.36 … Chrome/1xx.0.0.0 Safari/537.36`）
- 先 `GET` 文章页（携带 `ncbi_sid` / `ncbi_pinger`）再请求 PDF

### PoW 算法（从 `pow-*.js` 反解，已确认）

PoW 页内嵌四个常量：`POW_CHALLENGE` / `POW_DIFFICULTY` / `POW_COOKIE_NAME` / `POW_COOKIE_PATH`。

1. 求**最小非负整数** `nonce`，使得
   `sha256(challenge + str(nonce)).hexdigest()` 的前缀等于 `'0' * difficulty`；
2. 设置 Cookie：`<POW_COOKIE_NAME> = challenge + "," + nonce`（路径为 `POW_COOKIE_PATH`）；
3. 携带该 Cookie 与 `Referer: https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/` 重新请求 PDF 直链
   → 应返回 `200` 与 `Content-Type: application/pdf`。

典型 `difficulty = 4`（期望约 65536 次哈希，本地亚秒级完成）。

### 一键脚本

```bash
# 推荐：自动解析真实 PDF 文件名（走 citation_pdf_url），再离线求解 PoW
python3 scripts/pmc_pdf.py PMC13575452 ./out.pdf

# 已自行解析出文件名时可直接指定，跳过文章页请求
python3 scripts/pmc_pdf.py PMC13575452 ./out.pdf --pdf-name LIV-46-0.pdf

# 静默模式（只输出结果行）
python3 scripts/pmc_pdf.py PMC13575452 ./out.pdf --quiet
```

脚本行为：先以简约 UA、**丢弃 Cookie** 地请求文章页解析真实 PDF 直链 → 再以**全新 Cookie 会话**冷请求该 PDF → 若直接得到 PDF 则保存；否则解析 PoW 常量、求解、回填 Cookie 重试。
如需强制重取 challenge，重跑即可（脚本不落盘 Cookie，每次都是全新会话）。

> **★★ 两条必须记住的硬规则（实测血泪教训）**
>
> **1. 第二个位置参数是输出文件全路径，不是目录。** 传目录会在**已经拿到 PDF 之后**抛
> `IsADirectoryError: [Errno 21] Is a directory`，前面那次 PoW 白解、那份 PDF 白拿。
> ❌ `pmc_pdf.py PMC13482240 --outdir /path/to/dir`　　✅ `pmc_pdf.py PMC13482240 /path/to/dir/xxx.pdf`
>
> **2. PMC 的 PDF 通道有「一次机会」特性。** 首次冷请求基本都能走通 PoW 并拿到真 PDF；
> **紧接着对同一 PDF 再请求一次，几乎必然升级为 reCAPTCHA**（不是「换 UA 就好」的普通限流）。
> 因此**第一次就要把输出路径写对，绝对不要「先试跑看看」**。
> 实测：首轮 `status=200 type=application/pdf bytes=23970819`，数秒后重跑同一 URL 即变为
> `type=text/html bytes=21329`（reCAPTCHA 挑战页）。
> **一旦浪费掉这次机会，直接跳到下一节的「出版社官网降级路线」，不要在 PMC 上反复重试。**

### 故障排查

| 现象 | 原因 | 处置 |
|:--|:--|:--|
| 返回 HTML 且含 `POW_CHALLENGE` | 进入了 PoW 通道（正常） | 交给脚本求解 |
| 返回 HTML 且含 `recaptcha` | 被升级为 reCAPTCHA | 换简约 UA、清会话 Cookie、稍等重试；仍失败则改用途径 4/5 |
| **404 / 「Article not found」** | **PDF 文件名猜错了** | **回到文章页解析 `citation_pdf_url`，不要硬编码 `main.pdf`** |
| `nonce` 长时间不收敛 | `difficulty` 被调高 | 打印 `difficulty` 判断；>5 时考虑异步或多进程求解 |
| 求解成功但 PDF 仍是 HTML | Cookie 域 / 路径不匹配 | 确认 Cookie 域为 `pmc.ncbi.nlm.nih.gov`、路径取 `POW_COOKIE_PATH` |
| **`IsADirectoryError: Is a directory`** | **把输出参数当成了目录** | **第二参数是输出文件全路径**。此时 PDF 其实已经拿到了，只是没落盘——**不要立刻重跑**（会触发 reCAPTCHA），先改对路径，若已升级则直接走出版社官网路线 |
| **首次成功、第二次立刻 reCAPTCHA** | PMC 对同一 PDF 路径的「一次机会」限流 | 见上文硬规则 2；**放弃 PMC，走出版社官网降级路线** |
| `citation_pdf_url` 返回 `-mmc1.pdf` | 该文 PDF 未入库，解析到的是**补充材料** | Blood 等刊常见「有 JATS 全文但正文 PDF 未入库」。立刻放弃 PMC 路线，不要拿补充材料冒充正文（实测） |

> **★ 存在 IP 级限流（实测）**
> 短时间内对 PMC 重复请求 PDF（例如连续下载多篇）后，**即使使用正确的简约 UA，也会被直接升级为 reCAPTCHA**，
> 且等待 45 s 仍不恢复。表现为「首次成功、随后全部失败」。
> **处置：** ① 批量下载时在两次请求之间留出足够间隔；② 一旦进入 reCAPTCHA 状态，不要反复重试（只会延长封禁），
> 改为先完成其他工作，或改用途径 4（`supplementaryFiles`）与出版社直链；③ 若确有多篇需求，优先按需下载而非批量预热。

### ★★ 降级路线：PMC 被 reCAPTCHA 卡死时改走出版社官网（实测有效）

当 PMC 直链**两次**均被升级为 reCAPTCHA（IP 级限流，等待后仍不恢复）时，若目标刊是**全 OA 刊**，走出版社官网比继续重试 PMC 更可靠：

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
# 1) DOI 解析 → 观察最终落到哪个出版社文章页
curl -s -o /dev/null -w "final: %{url_effective}\nHTTP: %{http_code}\n" -A "$UA" -L "https://doi.org/<DOI>"
# 2) 在文章页解析真实 PDF 直链
curl -s -A "$UA" "https://<publisher-article-page>" | grep -oiE '<meta name="citation_pdf_url"[^>]*>|href="[^"]*\.pdf[^"]*"' | sort -u | head
# 3) 带 Referer 直取（出版社几乎不校验 Referer，但带上更稳）
curl -sL --retry 3 -A "$UA" -e "$ARTICLE_PAGE" -o "$OUT" "$PDF_URL"
```

### ★★ 出版社页被 Cloudflare 完全拦死时：用浏览器「打印为 PDF」（实测有效）

`ashpublications.org`（ASH 系期刊）本轮出现 Cloudflare 完全拦截，
此前「等 10 s 再 open」的经验**未能复现**。有效替代路径：

1. 打开 PMC **全文页**（非 PDF），绕过出版社站点
2. 用浏览器工具打印该页为 PDF：`agent-browser pdf`
3. reCAPTCHA 首次弹出时再执行一次 open 即可通过

> 判定要点：目标刊属于 ASH / ScienceDirect 一类强 Cloudflare 防护时，
> 不要在 curl 上反复重试——成功率低且会加深封禁，直接切浏览器通道。

- **已验证可行**：Haematologica / Ferrata Storti —— `doi.org/10.3324/haematol.2025.287698` → `haematologica.org/article/view/12187` → `haematologica.org/article/download/12187/78653` → 2.91 MB / 14 页。
- **不可行**：仍受 Cloudflare 类挑战拦截的出版社（ASH `ashpublications.org`、Wiley `onlinelibrary.wiley.com/doi/pdfdirect/...`、De Gruyter、Thieme）——这些只能回 PMC 通道或浏览器会话。
- 前置判断：只有**全 OA / Gold OA** 刊才值得试这条路线（订阅刊会撞付费墙，禁止绕过）。

### ★ 完整性校验：大文件下载被中断会导致 xref 损坏

`curl` 取 PDF 时若被 SIGTERM / 超时中断，**文件头仍是正常的 `%PDF-1.6`、体积也看似合理，但 `pdfinfo` 会报 `Invalid XRef entry`**。因此下载后**不能只看文件头与文件大小**，必须同时满足：

```bash
head -c 8 "$OUT"                                  # %PDF-…
tail -c 32 "$OUT" | od -c | tail -3               # 应能看到 startxref … %%EOF
pdfinfo "$OUT" | grep -E "Pages|Page size"        # 页数应与「卷期页」推算一致
```

三者齐全才算完整；缺失则**重新完整下载**（加 `--retry 3`），不要拿损坏文件交差。

## 补充材料与图片

正文 PDF 受阻时，`supplementaryFiles` 端点仍通常可用，且内容往往正是随文图片与补充方法：

```bash
curl -sL -o sup.zip "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13049628/supplementaryFiles"
unzip -o sup.zip -d sup/
```

命名约定（Wiley / ASH 系）：`*-gr1`…`*-grN` 对应 Figure 1…N，`*-ga1` 为图形摘要，`*-mmc1.pdf` 为补充材料。

## 使用浏览器工具时

只有在需要点击、登录或渲染 JS 页面时才动用 `agent-browser`。纯下载场景**不要**启动浏览器——
PoW 可离线求解，启动 Chromium 只增加数百 MB 开销与失败面。若确需浏览器：

- 必须先把可用的 node 加入 PATH（否则 daemon 启动超时）；
- 任务结束务必 `agent-browser close`，避免僵尸 daemon。

## 复核清单

- [ ] 下载前确认目标文献为 OA（**或**确认当前处于机构订阅 IP 段内——此情形下出版社直链可直接用，
      但仍仅限人工量的单篇下载，禁止批量）
- [ ] **从文章页 `citation_pdf_url` 解析出真实 PDF 文件名**（不要硬编码 `main.pdf`）
- [ ] 保存后校验文件头为 `%PDF`
- [ ] **尾部校验 `startxref` / `%%EOF`**（大文件被中断会留下头正常、xref 损坏的半成品；`pdfinfo` 能识别）
- [ ] **核验页数**：用 `re.findall(rb'/Count\s+(\d+)', data)` 或 `/Type /Page` 计数，
      **不要相信 `file out.pdf` 的页数**（macOS 上常误报为 "1 pages"）；也可用 `mdls -name kMDItemNumberOfPages`
- [ ] 抽首末页核对内容（`pdftotext -f 1 -l 1` / `-f N -l N`），确认不是补充材料或其它文章
- [ ] 记录 `PMCID` / `DOI` / 落盘路径，便于后续复核
- [ ] 未成功时如实说明失败原因，不要以补充材料或图片冒充正文 PDF
