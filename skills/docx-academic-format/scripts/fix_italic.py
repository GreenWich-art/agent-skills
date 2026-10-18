#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正斜体范围（原地修改，**不重建 run**）。

斜体规范（最终版）：
  判定标准 = 该字符在数学/统计学中是否为变量或符号

  斜体：P（显著性）、α（检验水准）、β、F/Z/H/χ²/t/r（检验统计量）、
        以及基因名、甲基化值等特殊字母
  不斜体：OR / CI / RR / HR / SD / SE / AUC（统计量缩写）、
          BMI / OGTT / FPG（单字母缩写）、以及所有汉字

  「P值」只有 P 斜体，"值" 必须是正体。

⚠️ 三条铁律（都是踩过血的）：
1. 绝不重建 run。只能改 run.text，绝不删/建 <w:r> 元素——
   否则 rFonts/sz/b 全丢、三线表边框被清空。
2. 拆分必须用 copy.deepcopy(run._element) 保留全部格式属性，
   插入位置 parent.insert(index+1, el)（紧邻原 run）。
   append 会跑到段末、顺序错乱出现 'PP'。
   副本文本 = lead + rest（**不含 stat**）；原 run = lead + stat。
3. run.text = x 不会清空已有 <w:t> 节点，在 deepcopy 副本上会**追加**。
   必须先 el.remove(child) 删掉 w:t/w:br/w:tab/w:cr；
   且要先移除 w:i/w:iCs 再设文本，顺序反了同样会错。
"""
import re
import sys
import copy
from docx import Document
from docx.oxml.ns import qn
from docx.text.run import Run

DOC = sys.argv[1]

# 明确**不**斜体的统计量缩写
NOT_ITALIC_ABBR = ('OR', 'CI', 'RR', 'HR', 'SD', 'SE', 'AUC', 'MD', 'ME')

# 需要斜体的单字符统计符号
ONE_CHAR = ('P', 'α', 'β', 'F', 'Z', 'H', 'χ', 't', 'r', 'X', 'Y')


def _set_run_text(run, text):
    """安全设置 run 文本：先删所有 <w:t>/<w:br>/<w:tab>/<w:cr>，再写入。

    ⚠️ python-docx 的 `run.text = x` 不会清空原有 <w:t>，
       在 deepcopy 副本上会追加而非替换，导致 'P<0.05' + ' = 0.05' 重复。
    """
    el = run._element
    for child in list(el):
        if child.tag in (qn('w:t'), qn('w:br'), qn('w:tab'), qn('w:cr')):
            el.remove(child)
    run.text = text


def _do_split(run, lead, stat, rest):
    """拆成：原 run = lead+stat（保持斜体），副本 = rest（正体）。
    副本必须 insert 到原 run 紧后面。
    """
    el = run._element
    parent = el.getparent()

    new_el = copy.deepcopy(el)          # 继承 rFonts/sz/b 等全部属性
    idx = list(parent).index(el)
    parent.insert(idx + 1, new_el)

    # ⚠️ 顺序：先移除斜体标记，再设文本（反了会出错）
    rPr = new_el.find(qn('w:rPr'))
    if rPr is not None:
        for tag in ('w:i', 'w:iCs'):
            e = rPr.find(qn(tag))
            if e is not None:
                rPr.remove(e)

    new_run = Run(new_el, run._parent)
    _set_run_text(new_run, lead + rest)   # 副本**不含 stat**

    _set_run_text(run, lead + stat)       # 原 run 只留符号（保持斜体）
    return True


def split_stat_run(run):
    """拆分形如 'P<0.05' / 'P=1.00' / 'P值' / 'α = 0.05' 的斜体 run。"""
    txt = run.text
    if not txt:
        return False

    # 情况 A：符号 + 运算符 + 数值
    m = re.match(r'^(\s*)([A-Za-zα-ωχ])(\s*[=<>≤≥]\s*[0-9.]+)(\s*)$', txt)
    if m and m.group(2) in ONE_CHAR:
        lead, stat, rest, trail = m.groups()
        return _do_split(run, lead, stat, rest + trail)

    # 情况 B：符号 + 汉字，如 'P值'
    m = re.match(r'^(\s*)([A-Za-zα-ωχ])([\u4e00-\u9fff].*)$', txt)
    if m and m.group(2) in ONE_CHAR:
        lead, stat, rest = m.groups()
        return _do_split(run, lead, stat, rest)

    return False


def unitalicize_abbrev(p):
    """把 OR / CI 等缩写从斜体改为正体。返回处理数量。"""
    n = 0
    for r in list(p.runs):
        if not r.font.italic:
            continue
        txt = (r.text or '').strip()
        if not txt:
            continue
        head = txt.split(' ')[0].split('=')[0].split('<')[0].strip()
        if head in NOT_ITALIC_ABBR:
            rPr = r._element.find(qn('w:rPr'))
            if rPr is not None:
                for tag in ('w:i', 'w:iCs'):
                    e = rPr.find(qn(tag))
                    if e is not None:
                        rPr.remove(e)
            n += 1
    return n


def process(p):
    cnt = 0
    # 先拆分（符号与后继内容分离）
    for r in list(p.runs):
        if r.font.italic:
            cnt += split_stat_run(r)
    # 再把 OR/CI 等缩写取消斜体（放在拆分之后，避免误处理刚拆出的副本）
    cnt += unitalicize_abbrev(p)
    return cnt


def iter_paragraphs(doc):
    for p in doc.paragraphs:
        yield p
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p
                for nt in cell.tables:
                    for nrow in nt.rows:
                        for ncell in nrow.cells:
                            for p in ncell.paragraphs:
                                yield p


def main():
    doc = Document(DOC)
    n = 0
    for p in iter_paragraphs(doc):
        n += process(p)
    doc.save(DOC)
    print(f'斜体修正: {n} 处（拆分为「符号斜体+其余正体」；OR/CI 等取消斜体）')


if __name__ == '__main__':
    main()