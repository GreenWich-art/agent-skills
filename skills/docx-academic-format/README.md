# docx-academic-format

把 Markdown 或已有 Word 文档批量重整为**中文学术论文规范排版**：三线表、统计量斜体、
中西文混排字体、1.5 倍行距、两端对齐、符号间距——并附生成后自检清单。

这是一个 **Agent Skill**（放进 skills 目录后 Agent 自动遵循其中的规范与脚本），
其中的 4 个 Python 脚本也可独立使用。

## 这个工具适合你吗？

**适合谁**：要向中文期刊投稿、写学位论文正文的研究生与科研人员；
用 AI 生成论文初稿后，被"格式不规范"打回来返工的人；
用 python-docx 自动排版、被 run 级格式丢失坑过的人。

**典型场景**：

| 场景 | 它能做什么 |
|---|---|
| 期刊要求"三线表"，Word 里怎么画都不对 | 精确到 1/8 磅的三线表实现 + `verify_table_borders()` 自检，逐单元格设置不留残余竖线 |
| "P 值要斜体"——结果 OR、CI、"值"字全跟着斜了 | 唯一判定标准（数学/统计学变量才斜体）+ 拆 run 铁律，`fix_italic.py` 原地修不毁格式 |
| 中文宋体、英文 Times New Roman 混排总有一处不生效 | 四个字体槽位（ascii/hAnsi/eastAsia/cs）一个不能少的完整写法 |
| Markdown 转 docx 后，`**强调**` 全变成加粗、空段落满篇 | 两条最高优先级铁律：`**` 只去标记不加粗、"空一行"只用段落间距 |
| 导师/用户在 Word 里改过的文档，不敢重新生成 | 原地改 XML 的工作流：只改 `run.text`、绝不重建 run、改前备份 |

**不适合谁**：排**党政机关公文**（那是 GB/T 9704 国标，另一套）；
排**高校课程作业**（各校字体字号约定不同，本工具是投稿级规范）；
只要"大概能看"的排版（本工具的价值在精确与可自检，简单场景用 Word 模板更省事）。

## 覆盖的规范点

- **三线表**：只有三条线（表头上 1.5 磅 / 表头下 1.0 磅 / 末行下 1.5 磅），
  逐单元格显式设置，附 `verify_table_borders()` 自检
- **统计量斜体**：P、α、β、F、Z、H、χ²、t、r 斜体；OR/CI/RR/HR/SD/SE/AUC 不斜体；
  「P值」只有 P 斜体——全部按「数学/统计学中是否为变量」这一唯一标准判定
- **中西文混排**：中文宋体（eastAsia 槽位）+ 西文 Times New Roman，四个字体槽位一个不能少
- **「空一行」= 段落间距**，绝不用空段落；**禁止自动加粗**——Markdown 的 `**` 是
  强调记号不是排版指令
- **符号间距**：`33 %`、`P < 0.05`、`30余次`——百分号前有空格，运算符与数字间有空格、
  与汉字间无空格
- **正文两端对齐**（JUSTIFY，不是 DISTRIBUTE）

## 快速开始

```bash
pip install python-docx

# 对已有 docx 做格式修正（顺序不可反：先斜体，后间距）
python3 scripts/fix_italic.py  目标.docx
python3 scripts/fix_spacing2.py 目标.docx
```

从零生成 docx 时，`scripts/fmt_lib.py`（字号对照、字体槽位、间距、加粗段解析）
和 `scripts/tri_line_table.py`（三线表 + 自检）作为库 import 使用。

## 作为 Agent Skill 使用

把本目录放进你的 skills 目录（如 `~/.workbuddy/skills/`、`.claude/skills/`）。
`SKILL.md` 内含完整方法论：字号磅值对照、8 个关键实现坑（含 python-docx 的
run 级 XML 操作陷阱）、13 项生成后校验清单、三条最高优先级铁律。

**与其他排版 skill 的边界**：本 skill 管学术投稿级排版；高校课程论文/作业、
党政机关公文（GB/T 9704）是另外两套标准，不可混用。

## 文件说明

| 文件 | 说明 |
|---|---|
| `SKILL.md` | Agent Skill 定义与完整方法论 |
| `scripts/tri_line_table.py` | 三线表边框实现 + `verify_table_borders()` 自检 |
| `scripts/fmt_lib.py` | 字体/间距/加粗段解析/单元格样式工具库 |
| `scripts/fix_italic.py` | 统计量斜体拆分（原地改，不重建 run） |
| `scripts/fix_spacing2.py` | 中英文混排与符号间距修正（原地改） |
| `requirements.txt` | 依赖清单（仅 python-docx） |

## 设计哲学（为什么这么强调"不重建 run"）

python-docx 里 run 的 `rPr` 承载全部格式信息（字体、字号、斜体、边框继承）。
任何"删了重建"的操作都会丢失模板未覆盖的属性——这是无数格式损坏的根源。
本 skill 的所有修改都遵循**只改 `run.text`，绝不删/建 `<w:r>`** 原则。

## License

MIT © 2026 冯金岳 (Feng Jinyue)
