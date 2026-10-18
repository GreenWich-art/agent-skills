#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三线表边框：只有 3 条线（表头上/表头下/末行下），其余全空。

正确规范：
  - 表头行上框线1.5 磅（w:sz=12）
  - 表头行下框线 1.0 磅（w:sz=8）
  - 末行  下框线 1.5 磅（w:sz=12）
  - 其余所有框线（含所有中间行、全部竖线）= none

关键：单元格级 tcBorders 会覆盖表级 tblBorders，
所以必须逐单元格显式设置，不能只设 tblBorders。
"""
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# w:sz 单位为 1/8 磅
SZ_1_5 = '12'   # 1.5 磅
SZ_1_0 = '8'    # 1.0 磅


def _set_tc_border(tcPr, edge, val, sz='0'):
    """在 tcPr 内设置某条边。val='none' 时 sz 忽略。"""
    tag = 'w:' + edge
    tcBorders = tcPr.find(qn('w:tcBorders'))
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)
    e = tcBorders.find(qn(tag))
    if e is None:
        e = OxmlElement(tag)
        tcBorders.append(e)
    e.set(qn('w:val'), val)
    if val == 'none':
        e.set(qn('w:sz'), '0')
        e.set(qn('w:space'), '0')
        e.set(qn('w:color'), 'auto')
    else:
        e.set(qn('w:sz'), sz)
        e.set(qn('w:space'), '0')
        e.set(qn('w:color'), '000000')


def _clear_row(row):
    """把一整行所有单元格的四条边全部设为 none。"""
    for cell in row.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        for edge in ('top', 'bottom', 'left', 'right'):
            _set_tc_border(tcPr, edge, 'none')


def _clear_table_level(table):
    """表级 tblBorders 六项全部设为 none，避免与单元格级冲突。"""
    tblPr = table._tbl.tblPr
    for old in tblPr.findall(qn('w:tblBorders')):
        tblPr.remove(old)
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement('w:' + edge)
        e.set(qn('w:val'), 'none')
        e.set(qn('w:sz'), '0')
        e.set(qn('w:space'), '0')
        e.set(qn('w:color'), 'auto')
        borders.append(e)
    tblPr.append(borders)


def set_table_borders(table):
    """应用三线表边框。必须在所有单元格写入内容后再调用。"""
    rows = table.rows
    if not len(rows):
        return

    # 1) 表级全清空
    _clear_table_level(table)

    # 2) 每一行先全部清空（含中间数据行，避免残留线条）
    for row in rows:
        _clear_row(row)

    # 3) 表头行：上 1.5 磅 + 下 1.0 磅
    for cell in rows[0].cells:
        tcPr = cell._tc.get_or_add_tcPr()
        _set_tc_border(tcPr, 'top', 'single', SZ_1_5)
        _set_tc_border(tcPr, 'bottom', 'single', SZ_1_0)
        _set_tc_border(tcPr, 'left', 'none')
        _set_tc_border(tcPr, 'right', 'none')

    # 4) 末行：下 1.5 磅
    if len(rows) > 1:
        for cell in rows[-1].cells:
            tcPr = cell._tc.get_or_add_tcPr()
            _set_tc_border(tcPr, 'bottom', 'single', SZ_1_5)
            _set_tc_border(tcPr, 'top', 'none')
            _set_tc_border(tcPr, 'left', 'none')
            _set_tc_border(tcPr, 'right', 'none')


def verify_table_borders(table):
    """返回 (是否合规, 诊断信息)。用于自检。"""
    problems = []
    tblPr = table._tbl.tblPr
    tb = tblPr.find(qn('w:tblBorders'))
    if tb is None:
        problems.append('缺 tblBorders')
    else:
        for e in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            v = tb.find(qn('w:' + e))
            if v is None or v.get(qn('w:val')) != 'none':
                problems.append(f'表级 {e} 应为 none')

    rows = table.rows
    # 表头行
    tc = rows[0].cells[0]._tc.get_or_add_tcPr().find(qn('w:tcBorders'))
    if tc is None:
        problems.append('表头行缺 tcBorders')
    else:
        t = tc.find(qn('w:top')); b = tc.find(qn('w:bottom'))
        if t is None or t.get(qn('w:sz')) != SZ_1_5:
            problems.append('表头上框线应=12 (1.5磅)')
        if b is None or b.get(qn('w:sz')) != SZ_1_0:
            problems.append('表头下框线应=8 (1.0磅)')

    # 末行
    if len(rows) > 1:
        lc = rows[-1].cells[0]._tc.get_or_add_tcPr().find(qn('w:tcBorders'))
        if lc is None or lc.find(qn('w:bottom')) is None or \
           lc.find(qn('w:bottom')).get(qn('w:sz')) != SZ_1_5:
            problems.append('末行下框线应=12 (1.5磅)')

    # 中间行必须全空
    for ri, row in enumerate(rows[1:-1], 1):
        tcb = row.cells[0]._tc.get_or_add_tcPr().find(qn('w:tcBorders'))
        if tcb is None:
            problems.append(f'第{ri}行缺 tcBorders')
            continue
        for e in ('top', 'bottom'):
            el = tcb.find(qn('w:' + e))
            if el is None or el.get(qn('w:val')) != 'none':
                problems.append(f'第{ri}行 {e} 应为 none')

    return (len(problems) == 0, problems)