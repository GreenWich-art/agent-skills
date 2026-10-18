#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学术论文 docx 格式工具库：中文字号对照、中西文混排字体槽位、段落间距、
加粗段解析与单元格样式。供排版脚本 import 使用。

字号对照（中文字号 -> 磅值）：
  初号 42 / 小初 36 / 一号 26 / 小一 24 / 二号 22 / 小二 18
  三号 16 / 小三 15 / 四号 14 / 小四 12 / 五号 10.5 / 小五 9
"""
import re
import copy
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsmap
from docx.oxml import OxmlElement

# ============ 字号常量 ============
from tri_line_table import set_table_borders, verify_table_borders  # noqa: E402

# ============字号常量 ============
SZ_XIAOSAN = Pt(15)   # 小三
SZ_SIHAO   = Pt(14)   # 四号
SZ_XIAOSI  = Pt(12)   # 小四
SZ_WUHAO   = Pt(10.5) # 五号

FONT_SONG = '宋体'
FONT_HEI  = '黑体'
FONT_KAI  = '楷体'
FONT_EN   = 'Times New Roman'


def set_run_font(run, cn_font, size_pt, bold=False, italic=False):
    """设置单个 run 的中英文字体、字号、粗体、斜体。

    ⚠️ 铁律：除非用户明确要求，bold 一律传 False。
       Markdown 里的 **文字** 是源文件强调标记，不是排版指令，不得渲染为加粗。
    """
    run.font.size = size_pt
    run.font.bold = bool(bold)
    run.font.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:ascii'), FONT_EN)
    rFonts.set(qn('w:hAnsi'), FONT_EN)
    rFonts.set(qn('w:eastAsia'), cn_font)
    rFonts.set(qn('w:cs'), FONT_EN)


# 「空一行」的磅值：小四(12pt)×1.5 倍行距 ≈ 18 磅；五号(10.5pt) ≈ 15.75 磅
GAP_L1_BEFORE = Pt(18)
GAP_L1_AFTER= Pt(18)
GAP_L2_BEFORE = Pt(18)
GAP_L2_AFTER  = Pt(0)
GAP_NONE      = Pt(0)


def add_spacing(p, before=0, after=0, line=1.5):
    """设置段落间距与行距（行距以倍数计）。"""
    pf = p.paragraph_format
    pf.space_before = before
    pf.space_after = after
    if line is not None:
        pf.line_spacing = line
        pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE


def blank_paragraph(doc, size=SZ_XIAOSI):
    """【已废弃】不要用空段落实现"空一行"。

    用户规范：「空行」必须在 Word 的段落设置（space_before/space_after）中实现，
    不能靠回车。空段落会导致后续编辑残留空行、打印出不确定空白。
    保留本函数仅为识别旧代码，请改用 add_spacing()。
    """
    raise RuntimeError(
        'blank_paragraph 已废弃：「空一行」请用段落间距实现，'
        '即 add_spacing(p, before=Pt(18), after=Pt(18))'
    )


# ============ 斜体处理：特殊符号与统计量 ============
# 需斜体的：P 值、OR、CI、β 等统计符号
ITALIC_PATTERNS = [
    re.compile(r'(P\s*[<>=≤≥]\s*[\d.]+)'),      # P<0.001 / P=0.06
    re.compile(r'(OR\s*[=＝]?\s*[\d.]+)'),        # OR=2.17
    re.compile(r'(OR\s+[\d.]+)'),                # OR 0.90
    re.compile(r'(CI\s*)'),                      # CI
    re.compile(r'(β)'),                          # β
    re.compile(r'\bP(\s*值)\b'),                 # P值 / P 值（值一并斜体）
]
# 英文缩写（这些用 Times New Roman 即可，不需要斜体，但统计量需斜体）
ITALIC_ABBR = ['P', 'OR', 'CI', 'β', 'RR', 'HR', 'SD', 'SE', 'AUC', 'R²']


def split_italic_segments(text):
    """把文本切分成 [(片段, 是否斜体), ...]"""
    marks = [False] * len(text)
    for pat in ITALIC_PATTERNS:
        for m in pat.finditer(text):
            for i in range(m.start(), m.end()):
                marks[i] = True
    segments = []
    cur = ''
    cur_flag = None
    for ch, f in zip(text, marks):
        if cur_flag is None or f == cur_flag:
            cur += ch
            cur_flag = f
        else:
            segments.append((cur, cur_flag))
            cur, cur_flag = ch, f
    if cur:
        segments.append((cur, cur_flag))
    return segments


def add_text_with_italics(p, text, cn_font, size_pt, bold=False):
    """向段落写入文本，自动处理统计量斜体与中英文字体分离。"""
    for seg, is_italic in split_italic_segments(text):
        if seg == '':
            continue
        r = p.add_run(seg)
        set_run_font(r, cn_font, size_pt, bold=bold, italic=is_italic)


def parse_bold_segments(text, allow_bold=False):
    """把 **强调** 标记拆分为 [(片段, 是否加粗), ...]。

    ⚠️ 铁律：任何时候都不要给文字加粗，除非明确要求。
    Markdown 的 **文字** 只是源文件的强调记号，必须**丢弃标记但不加粗**。
    allow_bold 默认 False；仅当用户明确要求加粗时才传 True。
    """
    if not allow_bold:
        # 去掉 ** 标记，保留文字，全部不加粗
        return [(re.sub(r'\*\*(.+?)\*\*', r'\1', text), False)]
    segments = []
    for i, part in enumerate(re.split(r'\*\*(.+?)\*\*', text)):
        if part == '':
            continue
        segments.append((part, i % 2 == 1))
    return segments or [(text, False)]


# ============ 三线表边框 ============



def style_cell_paragraph(cell, text, bold=False, align='left'):
    """设置表格单元格段落：五号宋体、单倍行距、无段间距、垂直居中。"""
    # 清除已有 run（保留段落本身），避免 cell.text='' 产生空 run
    p = cell.paragraphs[0]
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    pf = p.paragraph_format
    pf.space_before = Pt(2)
    pf.space_after = Pt(2)
    pf.line_spacing = 1.0
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    if align == 'center':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == 'right':
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # 解析 **加粗** 标记：拆成 (文本, 是否加粗) 片段
    for seg_text, seg_bold in parse_bold_segments(text):
        add_text_with_italics(p, seg_text, FONT_SONG, SZ_WUHAO, bold=seg_bold)
    if not p.runs:
        r = p.add_run('')
        set_run_font(r, FONT_SONG, SZ_WUHAO)

    # 垂直居中
    tcPr = cell._tc.get_or_add_tcPr()
    vAlign = OxmlElement('w:vAlign')
    vAlign.set(qn('w:val'), 'center')
    tcPr.append(vAlign)


def set_table_layout_fixed(table):
    """固定表格布局并设置总宽度与单元格边距。"""
    tbl = table._tbl
    tblPr = tbl.tblPr
    tblLayout = OxmlElement('w:tblLayout')
    tblLayout.set(qn('w:type'), 'fixed')
    tblPr.append(tblLayout)

    # 单元格边距
    mar = OxmlElement('w:tblCellMar')
    for tag, w in (('w:top', 40), ('w:left', 80),
                   ('w:bottom', 40), ('w:right', 80)):
        e = OxmlElement(tag)
        e.set(qn('w:w'), str(w))
        e.set(qn('w:type'), 'dxa')
        mar.append(e)
    tblPr.append(mar)


def repeat_header_row(row):
    """让表头跨页重复。"""
    trPr = row._tr.get_or_add_trPr()
    tblHeader = OxmlElement('w:tblHeader')
    tblHeader.set(qn('w:val'), 'true')
    trPr.append(tblHeader)