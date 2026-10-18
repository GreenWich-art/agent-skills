---
name: gbt7714-reference-check
display_name: "GB/T 7714 参考文献规范与核验"
display_name_en: "GB/T 7714 Reference Formatter & Link Checker"
version: 1.0.0
author: 冯金岳 (Feng Jinyue)
license: MIT
description_zh: "中文论文/学位论文参考文献的 GB/T 7714-2015 著录规范化，以及 URL / DOI / PMID / PMC 链接的批量可访问性核验与「假失效」（反爬）识别。附带可独立运行的 check_refs.py 并发核验脚本。交稿前核对文献表、批量验证链接死活时使用。"
description_en: "Format Chinese academic reference lists to GB/T 7714-2015 and batch-verify URL/DOI/PMID/PMC links, distinguishing genuinely dead links from anti-bot blocks (403/412/429). Ships a standalone concurrent checker script (check_refs.py). Use before submitting theses, papers, or any deliverable with a reference list."
description: |
  参考文献的 GB/T 7714-2015 著录规范化，以及 URL / DOI / PMID / PMC 链接的
  可访问性批量核验与"假失效"识别。

  触发场景：
  - 论文 / 综述 / 作业要交，需要核对参考文献格式
  - "帮我按国标改一下参考文献"
  - 要交付一份文献清单，需要确认链接没死
  - 已经有一堆 links，要批量验证哪些还能打开

  含一个可复用脚本 `scripts/check_refs.py`，能自动判别 URL / DOI / PMID / PMC
  并并发核验，且能区分「真死」与「被反爬」——后者不该判为失效。

  不适用：从零生成一份带引文的正文（那是写作任务）；
  Zotero 样式定制（见正文第六节，按需手工改 CSL）。
tags:
  - references
  - citation
  - gbt7714
  - academic-writing
---

# 参考文献 GB/T 7714-2015 规范化与链接核验

## 一、为什么值得单独做成一个 skill

这项工作有三个特征：**规则细节多**（文献类型标识、电子文献的引用日期、
三位作者以上的写法各不相同）、**容易出错且不报错**（几十个字符串里错一个很难被发现），
以及**一次写错就很难肉眼发现**。所以重点不是"记住规则"，而是
**程序化写入 + 回读校验 + 链接核验**这套流程。

## 二、GB/T 7714-2015 著录要点

### 基本结构

```
[序号] 主要责任者. 题名[文献类型标识/载体标识]. 出处, 年, 卷(期): 起止页码.
```

### 常见类型标识

| 类型 | 标识 | 电子化写法 |
|:--|:--|:--|
| 普通图书 | `[M]` | `[M/OL]` |
| 期刊文章 | `[J]` | `[J/OL]` |
| 报纸文章 | `[N]` | `[N/OL]` |
| 学位论文 | `[D]` | `[D/OL]` |
| 报告 | `[R]` | `[R/OL]` |
| 标准 | `[S]` | — |
| 电子公告 | `[EB/OL]` | — |
| 专利 | `[P]` | `[P/OL]` |

### 必须注意的三条

1. **电子文献必须著录引用日期和访问路径** —— GB/T 7714-2015 第 4.9 条的要求。
   带 URL / DOI 的文献，规范写法应当是
   `[J/OL]. 期刊名, 年, 卷(期): 页码[引用日期]. https://...`。
   **反过来，如果目标期刊/学校不要求，去掉引用日期是可以的，但要知道这是自己在做取舍**。
2. **责任者超过 3 个时**，中文文献写「主要责任者, 等」，西文写「主责任者, et al」。
   国标允许全部列出，但同一篇文献里要**前后统一**。
3. **西文作者姓在前、名缩写在后**：`Büller HR, Verhamme P, Weitz JI`。
   不要把 PubMed 的 `Buller HR` 直接搬过来丢了变音字母，也不要写成 `HR Büller`。

## 三、链接核验（核心工具）

```bash
# 每行一个：URL / DOI / PMID / PMC 编号，脚本自动判别类型
python3 scripts/check_refs.py refs.txt

# JSON 输入，支持显式指定类型
python3 scripts/check_refs.py refs.json --timeout 20 --workers 8
```

退出码：**0 = 无明确失效项；1 = 存在失效项**。

支持的输入形态：

| 输入 | 解析结果 |
|:--|:--|
| `10.1056/NEJMoa2513880` 或 `https://doi.org/...` | DOI 链接 |
| `25482425`（纯数字） | PubMed 链接 |
| `PMC2909362` | PMC 链接 |
| `https://...` 或裸域名 | 原样访问 |

### 判定逻辑（重要）

脚本把结果分三桶，**不要一看到非 200 就判失效**：

| 桶 | 条件 | 处理 |
|:--|:--|:--|
| 可直接访问 | 200 / **203** / 30x | 通过 |
| 疑似反爬 | 403 / 412 / 429 / 503 / 000（无非致命错误） | **改用浏览器复核**，不是链接错了 |
| 疑似失效 | curl 明确报 `could not resolve host` 等 DNS/证书错误 | 确认后替换或删除该链接 |

已实测的两个坑：

- **PubMed 返回 203**，不是失败。曾经把 203 当成失效，白白浪费一轮排查
- **`curl -s` 会把 DNS 错误静默掉**，导致"域名不存在"和"网络被墙"这两种完全不同的
  情况都显示 000。脚本已改用 `-sS`，靠 stderr 区分

### 常见站点的访问特性

| 站点 | 特征 |
|:--|:--|
| `nhc.gov.cn`（国家卫健委） | curl 常返回 412 反爬，**浏览器能正常打开** |
| 万方 med. 域 | 有反爬，可改用 `d.wanfangdata.com.cn/periodical/<xxx>` 形式访问 |
| 知网 | 一般不提供直链，文献能检索到即可，不必强求 URL |
| NEJM / Lancet | 付费墙，curl 常返回 403；有 DOI 就够了 |

## 四、写入工艺：防止字符错乱

这是本 skill 最容易被忽视、也最容易造成实际伤害的一点。

**不要用长 Heredoc 直接往 docx / json / py 里写长列表文献。**
实践中多次出现字符错乱：DOI 前缀写错（`10.7723` 误为 `10.19546` 之类）、
作者名错字、政策文号乱码，且**写入过程不报错**。

正确做法：

```python
# 1) 把文献列表构造成 Python 数据结构，程序化整块写入
refs = [
    {"id": 1, "text": "Büller HR, ...", "url": "https://...", "doi": "10.1056/..."},
    ...
]

# 2) 定义校验清单
must_have = ["25482425", "10.1056/NEJMoa2513880", "国卫医发", "Büller"]
bads      = ["10.7723", "理相指南", "ERUOIMMUON"]

# 3) 写完后立刻回读校验
content = read_back()
missing = [s for s in must_have if s not in content]
leaked  = [s for s in bads if s in content]
assert not missing and not leaked, (missing, leaked)
```

`must_have` 放关键标识（PMID、DOI、文号、难写的人名地名），
`bads` 放已知的错误写法。**两者都要有**：前者防丢内容，后者防产生错误内容。

## 五、常见错误清单（照着查一遍）

| 错误 | 例子 | 正确写法 |
|:--|:--|:--|
| 合并不同口径的数值 | 把"2-4%（RCT）"和"2-5%（真实世界）"合并成一个数 | 保留口径差异，分开写 |
| 卷期页写错 | Büller 写成 2009;361:1722 | 实际为 NEJM 2015;372:232-240 |
| 转引当成原引 | 引了一篇二手综述里的数字，却标注原始 RCT | 追到原文，或明确写"转引自" |
| 政策文件无出处 | 正文引了 5 份文件，参考文献表里一条没有 | 正文引用的每份政策/报告都要入表 |
| 著录标题与实际不符 | 文献[1]标题和实际发表的文章不是一篇 | 逐条核对标题 |
| 专有名词拼写错误 | EUROIMMUN 写成 ERUOIMMUON | 逐条目视核对专有名词 |

## 六、Zotero / CSL 相关

需要调整 Zotero 引用样式时，直接改 `.csl` 文件比用插件配置更可控。
例如 GB/T 7714-2015 numeric 样式每条文献末尾都带 `[引用日期]`，
找出 `accessed-date` 宏把宏体清空为 `<group/>` 即可全站失效（一处改动）。
同时改 `id` / `title` / `updated` 避免与官方样式冲突。

**但要提醒自己**：GB/T 7714-2015 对电子文献要求著录引用日期（第 4.9 条），
去掉之后对正式投稿的期刊 / 学位论文可能不符合规范。这是用户自己的权衡，
应当**把这个取舍明确告知**，而不是默默去掉。

`issued-year` 宏里保留的一处 accessed 兜底是合理的（issued 缺失时用访问年份占位），
不要一起删掉。

## 七、检查清单

- [ ] 每条文献的类型标识与是否 `/OL` 一致
- [ ] 超过 3 位作者的处理方式前后统一
- [ ] 西文人名姓在前、名缩写；变音字母没有丢
- [ ] 电子文献有引用日期（除非明确决定不要）与访问路径
- [ ] DOI 前缀正确、无半角/全角混用
- [ ] 链接已跑 `check_refs.py`，"疑似反爬"项用浏览器复核过
- [ ] 写入后 `must_have` / `bads` 回读校验通过
- [ ] 正文引用的每条都在文献表中出现，反之亦然
