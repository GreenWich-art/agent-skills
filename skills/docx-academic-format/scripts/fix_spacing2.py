#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中英文混排间距修正（原地修改，**不重建 run**）。

⚠️ 设计约束（踩坑教训）：
绝不能删除/重建 run 来"重排"格式。Word 的 rPr 内含 rFonts、sz、b、i 等
全部格式信息，重建 run 会丢失模板未覆盖的属性，导致字体/字号/三线表边框全部损坏。
正确做法：**只修改 run.text 的字符内容，不动 run 的 XML 结构与属性**。
"""
import re
import sys
from docx import Document
from docx.oxml.ns import qn

DOC = sys.argv[1]

CJK = r'一-鿿㐀-䶿　-〿＀-￯'
CN = rf'[{CJK}]'
CN_PUNCT = r'[，。；：、（）「」《》【】？！]'

ITALIC_CHARS = ('P', 'OR', 'RR', 'HR', 'SD', 'SE', 'AUC', 'CI')
TWO_LETTER = ('OR', 'RR', 'HR', 'SD', 'SE')


def fix_spacing_in_run(text):
    """修正单个 run 内的空格（不做跨 run 操作）。"""
    if not text:
        return text
    t = text

    # ① 数学表达式内部：字母/数字 与 运算符 之间加空格
    #P=0.04 -> P = 0.04 ;  >=10 -> >= 10
    t = re.sub(r'(?<![A-Za-z])(P|OR|RR|HR|SD|SE|AUC)(=|<|>|<=|>=|≤|≥)(?=[0-9])',
               lambda m: f'{m.group(1)} {m.group(2)} ', t)
    t = re.sub(r'(?<=[A-Za-z])[ ]*(?==|<|>|≤|≥)', ' ', t)
    t = re.sub(r'(?<==|<|>|≤|≥)[ ]*(?=[0-9])', ' ', t)

    # ② 数学表达式与中文之间要有空格：">= 10小时" -> ">= 10 小时"
    t = re.sub(r'(?<=[=<>≤≥])[ ]*([0-9.]+)[ ]*(?=[一-鿿])', r' \1 ', t)

    # ③ 中文/中文标点 与 字母数字 之间删空格
    t = re.sub(rf'({CN}|{CN_PUNCT})[ ]*(?=[0-9A-Za-z])', r'\1', t)
    t = re.sub(rf'(?<=[0-9A-Za-z])[ ]*(?={CN}|{CN_PUNCT})', '', t)

    # ④ 汉字之间删空格
    t = re.sub(rf'({CN})[ ]*(?={CN})', r'\1', t)

    # ⑤ 数字与百分号之间加空格：33% -> 33 %（GB/T 7714 与科技论文规范）
    t = re.sub(r'(?<=[0-9])[ ]*(?=%)', ' ', t)

    return t


def process_paragraph(p):
    """只改 run.text，不动 XML 结构。"""
    changed = False
    for r in p.runs:
        old = r.text
        new = fix_spacing_in_run(old)
        if new != old:
            r.text = new      # 只赋值 text，rPr 原样保留
            changed = True

    # 跨 run 边界：斜体符号 run 与紧随其后的运算符 run 之间要补空格
    # "P" + "< 0.05"  ->  "P " + "< 0.05"
    runs = list(p.runs)
    for i in range(len(runs) - 1):
        a, b = runs[i], runs[i + 1]
        if not (a.font.italic and b.text):
            continue
        ta, tb = a.text, b.text
        # a 以统计量字母结尾，b 以运算符开头 -> 在 a 末尾补空格
        if re.search(r'(P|OR|RR|HR|SD|SE|AUC|SD)$', ta) and \
                re.match(r'\s*[=<>≤≥]', tb) and not ta.endswith(' '):
            a.text = ta + ' '
            changed = True
    return changed


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
        if process_paragraph(p):
            n += 1
    doc.save(DOC)
    print(f'间距修正段落: {n} 个（未改动任何 run 结构与格式）')


if __name__ == '__main__':
    main()