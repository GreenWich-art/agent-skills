---
name: docx-academic-format
display_name: "学术论文 docx 排版"
display_name_en: "Academic docx Formatter"
version: 1.0.0
author: 冯金岳 (Feng Jinyue)
license: MIT
description_zh: "把 Markdown 或已有 docx 批量重整为中文学术论文规范排版：三线表（精确到 1/8 磅）、统计量斜体（P/α/β/F/χ² 等）、中西文混排字体四槽位、1.5 倍行距、两端对齐、百分号与运算符间距。基于 python-docx 直接操作 XML，附 4 个可复用脚本与生成后自检清单。触发词：按学术格式排版、三线表、P值斜体、Times New Roman、论文排版。"
description_en: "Batch-reformat Markdown or existing .docx into Chinese academic-paper style: three-line tables (exact 1/8-pt borders), italicized statistics (P/α/β/F/χ²...), CJK+Latin font slots (SimSun + Times New Roman), 1.5 line spacing, justified body text, and GB-style spacing around % and operators. Built on python-docx with 4 reusable scripts and a post-generation self-check suite."
description: |
  按学术论文规范（小三黑体一级标题/四号黑体二级/小四正文宋体1.5倍行距/三线表/中西文混排Times New Roman/统计量斜体）
  批量重整 Markdown 或已有 docx 的格式。用户说"按学术格式排版""三线表""小三号黑体标题""1.5倍行距"
  "数字英文用Times New Roman""P值斜体"时使用。基于 python-docx 直接生成 docx，不走逐段插入。

  不适用：高校课程论文/作业的字体字号约定（标准不同）；党政机关公文国标 GB/T 9704
  （又是另一套标准）。三套标准不可混用。
tags:
  - docx
  - academic-writing
  - python-docx
  - formatting
---

# 学术论文 docx 格式重整

## 何时用
- 需要把 Markdown 分析报告/表格转成符合投稿规范的 docx
- 需要批量设置中西文混排、三线表、多级标题字号间距
- 逐段插入类 API 无法控制三线表边框、run 级 rFonts、斜体拆分时，用本 skill

## 中文字号 → 磅值

| 字号 | 磅 |
| --- | --- |
| 三号 | 16 |
| 小三 | 15 |
| 四号 | 14 |
| 小四 | 12 |
| 五号 | 10.5 |

默认规范（可按目标期刊/学校要求覆盖）：一级标题小三黑体、二级四号黑体、
正文小四宋体 1.5 倍行距、西文一律 Times New Roman、表格五号宋体。

## 关键实现要点（踩过的坑）

### 1. 三线表边框
`w:tblBorders` 的 `w:sz` 单位是 **1/8 磅**：
- 顶/底 1.5 磅 → `sz=12`
- 中间线（表头下方）1.0 磅 → `sz=8`
- 竖线必须显式 `val="none"`，否则 Word 会画默认竖线

**表头下方那条线**要靠 `row.cells[i]` 逐格设 `w:tcBorders/w:bottom`，只设
tblBorders 的 insideH 在某些渲染器下不可靠。

### 2. `cell.text = ''` 会留下无格式空 run
清空单元格要用：
```python
p = cell.paragraphs[0]
for r in list(p.runs):
    r._element.getparent().remove(r._element)
```
否则 `runs[0]` 是一个无 rPr 的空 run，后续校验字体时会误判。

### 3. 中西文混排必须同时设 4 个字体槽位
```python
rFonts.set(qn('w:ascii'), 'Times New Roman')
rFonts.set(qn('w:hAnsi'), 'Times New Roman')
rFonts.set(qn('w:eastAsia'), '宋体')   # 中文字体
rFonts.set(qn('w:cs'), 'Times New Roman')
```
漏设 eastAsia → 中文回落到默认字体。

### 4. 斜体要拆 run
统计量（P<0.001、OR=2.17、CI、β、P 值）必须拆成独立 run 才能单独设 italic。
正则顺序有讲究：`P值` 要用 `\bP(\s*值)\b` 整体匹配；
先匹配 `P\s*[<>=]\s*[\d.]+` 再匹配孤立的 P，否则 `P=0.06` 会被拆成 `P` + `=0.06`。

### 5. 「空一行」= 段落间距，不是空段落

**绝对不要用回车（空段落）实现"空一行"。** 空段落会在 Word 里造成：
- 后续编辑时多出空行、无法干净删除
- 打印/转 PDF 时出现不确定的空白
- 与段前段后间距叠加后间距失控

正确做法——用 `space_before` / `space_after`（单位磅）：

| 场景 | 实现 |
| --- | --- |
| 一级标题「上下各空一行」 | `space_before = Pt(小四字号×1.5)`、`space_after = 同值` |
| 二级标题「上面空一行」 | `space_before = Pt(小四字号×1.5)`、`space_after = Pt(0)` |
| 三级及以下标题 | 不设间距 |
| 正文 | `space_before = Pt(0)`、`space_after = Pt(0)` |
| 图/表与正文之间空一行 | 在**图/表所在段落**上设 `space_before/after`，不另插空段 |

参考值：小四(12pt) 空一行 ≈ 18 磅；五号(10.5pt) 空一行 ≈ 15.75 磅。

校验方式：`sum(1 for p in doc.paragraphs if not p.text.strip()) == 0`
——正常文档不应存在任何空段落。

### 6. 禁止自动加粗

**任何时候都不要给文字加粗，除非用户明确要求。**

这条极易踩坑：Markdown 里的 `**文字**` 是**源文件的强调标记**，不是排版指令。
把它渲染成 Word 加粗，等于擅自给原文加重点。

正确做法：
- `**文字**` → 只取文字内容，**不加粗**
- 需要分小标题时，用独立段落 + 目标字体/字号，不要靠加粗实现层级
- 层级感只能来自：字体（黑体/楷体）、字号、段前段后间距、编号

同样禁止的还有：**斜体**除指定的统计量/符号外不要用；**下划线**、**着重号**、
**彩色字**、**字符缩放/字间距**——用户没要求的一律不动。

转换完成后应自检：
```python
# 不应出现任何非用户要求的 bold
bold = [r.text for p in doc.paragraphs for r in p.runs if r.font.bold]
```
表头是否加粗看用户要求；本 skill 默认表头**不加粗**（靠字号+三线表区分）。

### 7. 三级及以下标题不空行
只有 1、2 级标题设段前段后间距；3 级及以下不加间距、不加粗。

## 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/tri_line_table.py` | 三线表边框（含 `verify_table_borders()` 自检） |
| `scripts/fmt_lib.py` | 字体/间距/加粗段解析/单元格样式 工具函数库 |
| `scripts/fix_italic.py` | 统计量斜体拆分（原地改，不重建 run） |
| `scripts/fix_spacing2.py` | 中英文混排与符号间距修正（原地改，不重建 run） |

依赖：`pip install python-docx`

`fmt_lib.parse_bold_segments(text, allow_bold=False)` 默认**丢弃但不渲染** `**` 标记；
只有用户明确要求加粗时才传 `allow_bold=True`。

对已有 docx 做格式修正时的执行顺序（**不可反序**）：
```bash
python3 scripts/fix_italic.py  目标.docx   # 先拆斜体
python3 scripts/fix_spacing2.py 目标.docx  # 后修间距
```
**反序会被间距规则把已拆开的符号重新拼错。**

## 校验清单（生成后必查）
1. **空段落数 == 0** —— 最高优先级，`sum(1 for p in doc.paragraphs if not p.text.strip())`
2. **加粗 run == 0**（除非用户要求）——`[r.text for p in doc.paragraphs for r in p.runs if r.font.bold]` 必须为空；表格内同样检查
3. 一级标题 sz==15 且 eastAsia==黑体，**space_before==space_after==18pt**
4. 二级标题 sz==14，**space_before==18pt**
5. 正文 sz==12、eastAsia==宋体、line_spacing==1.5
6. 所有 run 的 ascii/hAnsi==Times New Roman
7. 斜体 run 数量 >0 且内容是统计量（这是唯一允许的特殊格式）
8. 三线表：用 `verify_table_borders(table)` 逐表校验，应全部返回 `(True, [])`
9. 表题：五号黑体居中、句末无标点
10. 表格内所有 run: 宋体 + 10.5pt
11. **正文段落 alignment == JUSTIFY**，标题与表题保持原样
12. **百分号前有空格**：`33 %` 而非 `33%`
13. **符号与汉字间无空格**：`30余次`；**符号与数字间有空格**：`≥ 10 小时`、`P < 0.05`

**一次性自检脚本**：
```python
import sys; sys.path.insert(0, '<skill>/scripts')
from tri_line_table import verify_table_borders
from docx import Document
d = Document('out.docx'); ps = d.paragraphs
assert sum(1 for x in ps if not x.text.strip()) == 0, '存在空段落'
assert not [r for x in ps for r in x.runs if r.font.bold], '存在加粗'
assert not [r for t in d.tables for row in t.rows for c in row.cells
            for r in c.paragraphs[0].runs if r.font.bold], '表格存在加粗'
for i, t in enumerate(d.tables, 1):
    good, prob = verify_table_borders(t)
    assert good, f'表{i} 三线表不合规: {prob}'
print('全部通过')
```

## 无可视化验证环境时

没有 LibreOffice / Word 可转 PDF 目视验证三线表时，
改用 XML 层校验（清单第 1–9 项），能可靠覆盖字号、字体、边框、间距。

## 补充：三线表的精确规范

**只有 3 条线**：

| 位置 | 磅值 | `w:sz` |
| --- | --- | --- |
| 表头行（上框线） | 1.5 | 12 |
| 表头行（下框线） | 1.0 | 8 |
| 末行（下框线） | 1.5 | 12 |
| 其余所有框线（含所有中间行、竖线） | 空 | `val="none"` |

**关键**：不能只在 `tblBorders` 设 `insideH`。表级边框会被单元格级 `tcBorders` 覆盖，
一旦某单元格写了 `bottom`，就以单元格级为准。**必须逐单元格显式设置**：
1. 表级 `tblBorders` 六项全设 `none`
2. 所有行 `tcBorders` 四边先全设 `none`
3. 表头行单元格：`top=('single',12)` + `bottom=('single',8)`
4. 末行单元格：`bottom=('single',12)`

`clear_row_borders()` 要对**每一行**调用，不能只清表头和末行——否则中间行残留线条。

## 补充：中文引号替换

Markdown 里的 `"` 是直引号，转 docx 后必须成对替换为 `“` / `”`：
```python
dq_index = 0   # 必须跨 run 连续计数，不能每个 run 从 0 开始
for r in p.runs:
    for ch in r.text:
        if ch == '"':
            out.append('“' if dq_index % 2 == 0 else '”')
            dq_index += 1
```
只改 `r.text`，不动 `rPr` → 字体/字号/斜体全部保留。
替换后必须验证：`全文 " 计数 == 0`、`“` 计数 == `”` 计数、**逐段**左右配对
（整篇平衡不代表逐段平衡）。

## 补充：Word 编辑会产生碎片 run

用户在 Word 里手工编辑后，段落会被拆成多个 run，其中部分（被拆出的 `-`、单字）
**不带 `rFonts`**，会回落到默认字体。修完引号/边框后应扫一遍：
```python
rf = r._element.rPr.rFonts if r._element.rPr is not None else None
if rf is None or rf.get(qn('w:eastAsia')) is None:  # → 需补齐
```
补齐方式：取段内第一个已设定字体的 run 作参照，继承其 rFonts/sz/b。

## 重要工作流提醒

用户在 Word 中手工修改过文档后，**绝不能重新生成整份文档**——会覆盖用户改动。
正确做法：读取现有 docx → 原地定点修 XML → 保存。
修前先备份：`cp xxx.docx /tmp/backup.docx`。

## 斜体规范

### 唯一判定标准：**该字符在数学/统计学中是否是变量或符号**

| 类别 | 是否斜体 | 示例 |
| --- | --- | --- |
| 统计学显著性 P | **斜体** | `P = 0.04`、`P < 0.001` |
| 检验水准 α | **斜体** | `α = 0.05` |
| 检验统计量 F、Z、H、χ²、t、r | **斜体** | `F = 4.52`、`χ² = 8.31` |
| 特殊字母（基因符号、甲基化 β 值等） | **斜体** | `β` |
| **OR、CI、RR、HR、SD、SE、AUC** | **不斜体** | `OR = 3.14`、`95% CI` |
| 多字母缩写（BMI、OGTT、FPG…） | **不斜体** | `BMI`、`OGTT` |
| 中文文字 | **不斜体** | `值`、`为` |

### ⚠️ 最易错：「P值」只有 P 斜体

```
✗ 斜体 'P值'         ← "值" 跟着斜了
✓ 斜体 'P' + 正体 '值'
✓ 斜体 'P' + 正体 '值为' + ...
```

`P 值`、`P值`、`P 值为 0.07` ——一律只有 **P** 斜体，紧跟的汉字全部正体。

### 斜体拆分的三条铁律（踩过血）

1. **绝不重建 run**。用"字符流重组 run"修格式会导致 rFonts/sz/b 全丢、
   三线表边框被清空、斜体标记错位成碎片。**只能改 `run.text`，绝不删/建 run 元素。**
2. **拆分必须用 `copy.deepcopy(run._element)`** 保留全部格式属性；
   插入位置 `parent.insert(index+1, el)`（紧邻原 run）。用 `append` 会跑到段末、
   顺序错乱出现 `PP`。
   副本文本 = `lead + rest + trail`（**不含 stat**），原 run 文本 = `lead + stat`。
3. **`run.text = x` 不会清空已有 `<w:t>` 节点**，在 deepcopy 副本上会**追加**。
   必须先 `el.remove(child)` 删掉所有 `w:t/w:br/w:tab/w:cr`；
   且要先移除 `w:i/w:iCs` 再设文本，顺序反了也会错。

参考实现见 `scripts/fix_italic.py`。

## 中英文混排与符号间距

### 基本规则

| 场景 | 规则 | 示例 |
| --- | --- | --- |
| 中文 ↔ 数字/字母/标点 | **不加空格** | `在30余次未校正检验的背景下`、`但Table 1显示` |
| 汉字 ↔ 汉字 | **不加空格** | `研究目的` |
| 英文单词之间 | 加空格 | `Table 1` |
| 数学表达式内部 | 字母/数字 与 运算符 之间加空格 | `P = 0.04`、`BMI < 18.5` |
| 数学表达式 ↔ 中文 | 加空格 | `P < 0.05 为阈值` |

### 符号与数字/字母/汉字的间距（易错）

| 组合 | 规则 | 示例 |
| --- | --- | --- |
| **符号 ↔ 数字** | **加空格** | `33 %`、`87.3 %`、`P = 0.04` |
| **符号 ↔ 英文单词/字母** | **加空格** | `Table 1`；`α = 0.05` |
| **符号 ↔ 汉字** | **不加空格** | `30余次`、`≥10小时`（符号紧贴汉字） |

**易错点**：`30 余次`（错，符号与汉字间多空格） vs `30余次`（对）。
**运算符类符号（≥ ≤ = < >）与数字之间要空格，但符号与紧随的汉字之间不补空格。**

### 百分号

`33 %` 数字与 `%` 之间**加空格**。这是科技论文规范的要求，不要写成 `33%`。

参考实现见 `scripts/fix_spacing2.py`（含 `fix_spacing_in_run`）。

## 正文段落对齐

**正文段落用两端对齐**——即 Word 的 `JUSTIFY`（Cmd+J / Ctrl+J），
注意不是 `DISTRIBUTE`。

```python
from docx.enum.text import WD_ALIGN_PARAGRAPH
p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
```

**只应用到正文段落**，以下保持各自原有对齐，**不要改动**：
- 各级标题——通常左对齐
- 表题——居中
- 表格内单元格——按需（左对齐或居中）

## ⚠️ 三条铁律（执行顺序与校验）

### 执行顺序
```bash
python3 scripts/fix_italic.py  目标.docx   # 先拆斜体
python3 scripts/fix_spacing2.py 目标.docx  # 后修间距
```

### 校验（必做，缺一不可）
```python
import re
norm = lambda s: re.sub(r'\s', '', s)
# ① 文字零丢失——防吞字/重复字
assert all(norm(a.text) == norm(b.text)
           for a, b in zip(原文档.paragraphs, 新文档.paragraphs))
# ② 斜体 run 只能是统计符号本身（P/α/β/F/Z/H/χ/t/r），不得含：
#    - 运算符或数字：[=<>≤≥0-9]
#    - 汉字（'P值' 的 '值' 必须是正体）
#    - OR/CI/RR 等缩写
for p in 新文档.paragraphs:
    for r in p.runs:
        if r.font.italic and r.text.strip():
            t = r.text.strip()
            assert not re.search(r'[=<>≤≥0-9\u4e00-\u9fff]', t), f'斜体含运算符/数字/汉字: {t!r}'
            assert t.split(' ')[0] not in ('OR','CI','RR','HR','SD','SE','AUC'), f'缩写不应斜体: {t!r}'
# ③ 正文段落必须两端对齐
from docx.enum.text import WD_ALIGN_PARAGRAPH
assert any(p.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY for p in 新文档.paragraphs)
# ④ 中文引号成对
assert sum(p.text.count('“') for p in 新文档.paragraphs) == \
       sum(p.text.count('”') for p in 新文档.paragraphs)
```

## ⚠️ 最高优先级铁律（违反即返工）

1. **「空一行」只能用段落间距**（`space_before`/`space_after`），**绝不能用回车/空段落**。
2. **任何时候都不要给文字加粗**，除非用户在需求里明确说了要加粗。
   Markdown 的 `**文字**` 是源文件的强调记号，不是排版指令——只去标记、不加粗。
3. 用户没要求的格式（下划线、着重号、彩色字、字间距、字符缩放）一律不动。
4. 用户手工改过文档后，**禁止重新生成整份文档**，只能读现有文件原地改 XML。

**层级感只能来自字体（黑体/楷体）、字号、段前段后间距、编号——不是加粗。**

## 精简正文/表格文字时的注意事项

在用户已修改的 docx 上精简文字内容时：

### 铁律：合并写入第一个 run，其余置空
```python
def set_paragraph_text(p, text):
    runs = p.runs
    if not runs: return False
    runs[0].text = text          # 格式保留在第一个 run
    for r in runs[1:]:
        r.text = ''              # ⚠️ 必须置空，否则残留旧文字造成重复
    return True
```
同样遵守「不重建 run」原则——只改 `run.text`，绝不删/建 `<w:r>`。

### 定位表格：按文档流顺序，不能用 `doc.paragraphs` 索引
段落里嵌着表格时，`doc.paragraphs[i]` 的序号与表格不对应。必须走 body 流：
```python
from docx.table import Table
from docx.text.paragraph import Paragraph
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
seq = []
for c in doc.element.body.iterchildren():
    if c.tag == W+'p':   seq.append(('p', Paragraph(c, doc)))
    elif c.tag == W+'tbl': seq.append(('t', Table(c, doc)))
```

### 增删行的两个坑
1. **`table.rows` 每次访问都重新解析 XML** —— 删行后再用 `rows[ri]` 会越界。
   先 `rows = list(table.rows)` 快照，从后往前删。
2. **克隆出来的行会丢末行下框线** —— 克隆末行补齐后，三线表的底线会变成 `nil`。
   收尾必须重新补末行 `bottom` 边框（sz=12）。

### ⚠️ 检测边框时不要只认 `none`
Word 自己的三线表，中间行写的是 **`w:val="nil"`** 而非 `"none"`。
判定"无线"要同时接受两者：
```python
assert tv in ('nil','none') and bv in ('nil','none')
```
只认 `none` 会误报"边框损坏"，实际是检测逻辑错。
