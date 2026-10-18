#!/usr/bin/env python3
# check_refs.py —— 链接 / DOI / PMID 可访问性批量核验（复用自 gbt7714-reference-check skill）
#
# 版本：1.0.0  许可：MIT  作者：冯金岳 (Feng Jinyue)
# 依赖：Python 3 标准库 + 系统 curl，无需安装任何第三方包
#
# 用法：
#   python3 check_refs.py refs.json              # JSON 数组，每项 {"id":1,"type":"url|doi|pmid","value":"..."}
#   python3 check_refs.py refs.txt               # 每行一个 URL / DOI / PMID，自动判别类型
#   python3 check_refs.py refs.txt --timeout 20 --workers 8
#
# 退出码：0 = 全部可访问；1 = 存在失效项
#
# 重要：返回码 403/412/000 不等于链接失效，见 SKILL.md「反爬识别」一节。

import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import urllib.parse

CURL = "/usr/bin/curl"

# 常见反爬 / 误判状态码：不直接判为失效
SOFT_CODES = {
    "000": "连接失败或超时（可能是网络出口限制，不一定是链接失效）",
    "403": "被拒绝（反爬常见，浏览器可能能正常打开）",
    "412": "前置条件失败（反爬，浏览器可能能正常打开）",
    "429": "请求过于频繁，稍后重试",
    "503": "服务暂时不可用",
}

# 200/203 均为请求成功；203 = PubMed 等站点常见的 Non-Authoritative Information，
# 曾被误判为失效。
OK_CODES = {"200", "203", "301", "302", "303", "307", "308"}

# curl stderr 出现这些串 = 明确的失败信号，即使返回码是 000 也应判为失效
HARD_FAIL_MARKERS = (
    "could not resolve host",
    "couldn't resolve host",
    "no address associated",
    "ssl certificate problem",
)


def classify(raw: str):
    """判别输入类型并构造候选 URL。"""
    s = raw.strip().strip("<>").rstrip(".,;])")
    if not s:
        return None, None
    if re.match(r"^\d{7,8}$", s):
        return "pmid", "https://pubmed.ncbi.nlm.nih.gov/%s/" % s
    if re.match(r"^\d{1,8}$", s):
        return "pmid", "https://pubmed.ncbi.nlm.nih.gov/%s/" % s
    m = re.match(r"^(?:https?://)?(?:dx\.)?doi\.org/(.+)$", s, re.I)
    if m:
        return "doi", "https://doi.org/" + m.group(1)
    if re.match(r"^10\.\d{4,9}/", s):
        return "doi", "https://doi.org/" + s
    if re.match(r"^PMC\d+$", s, re.I):
        return "pmc", "https://www.ncbi.nlm.nih.gov/pmc/articles/%s/" % s.upper()
    if s.lower().startswith(("http://", "https://")):
        return "url", s
    return "url", "https://" + s


def probe(item, timeout):
    idx, kind, url = item
    try:
        out = subprocess.run(
            # 用 -sS 而非 -s：-s 会把 DNS/连接错误一起静默掉，导致无法区分 000 的成因
            [CURL, "-sS", "-o", "/dev/null", "-L", "-w", "%{http_code}",
             "--max-time", str(timeout),
             "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
             url],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        code = (out.stdout or "").strip()[-3:]
        err = out.stderr.strip()
    except subprocess.TimeoutExpired:
        return idx, "000", "curl 超时", url
    except Exception as e:
        return idx, "000", str(e), url

    if not code:
        return idx, "000", err or "无响应", url
    if code in OK_CODES:
        return idx, code, "", url
    if code == "000":
        low = err.lower() if err else ""
        hit = next((m for m in HARD_FAIL_MARKERS if m in low), None)
        if hit:
            # 明确的失败信号：不放进「疑似反爬」桶
            return idx, code, "hard:" + hit, url
    return idx, code, SOFT_CODES.get(code, ""), url


def load_items(path):
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        out = []
        for n, it in enumerate(data, 1):
            if isinstance(it, str):
                k, u = classify(it)
            else:
                k = it.get("type")
                v = it.get("value", "")
                if k == "doi":
                    u = "https://doi.org/" + re.sub(r"^https?://(dx\.)?doi\.org/", "", v, flags=re.I)
                elif k == "pmid":
                    u = "https://pubmed.ncbi.nlm.nih.gov/%s/" % str(v).strip()
                else:
                    k, u = classify(v)
            if u:
                out.append((n, k, u))
        return out

    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            k, u = classify(s)
            if u:
                out.append((len(out) + 1, k, u))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    items = load_items(args.input)
    if not items:
        print("没有可用于核验的条目。")
        return 2

    print(f"共 {len(items)} 条待核验，超时 {args.timeout}s，并发 {args.workers}\n")

    results = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(probe, it, args.timeout) for it in items]
        for fu in cf.as_completed(futs):
            results.append(fu.result())
    results.sort()

    bad, soft = [], []
    print(f"{'#':>3}  {'状态码':<7} 判定 / 说明")
    print("-" * 96)
    for idx, code, note, url in results:
        flag = "OK " if code in OK_CODES else "!! "
        msg = note[5:] if note.startswith("hard:") else (note or ("访问正常" if code in OK_CODES else ""))
        print(f"{idx:>3}  {code:<7} {flag} {msg}".strip())
        if code not in OK_CODES:
            entry = (idx, code, note, url)
            (soft if not note.startswith("hard:") else bad).append(entry)

    print("\n=== 汇总 ===")
    print(f"可直接访问：{len(results) - len(bad) - len(soft)}")
    print(f"疑似反爬 / 需浏览器复核：{len(soft)}")
    print(f"疑似失效：{len(bad)}")

    if soft:
        print("\n[需人工复核 — 不一定是链接失效]")
        for idx, code, note, url in soft:
            print(f"  [{idx}] {code} {url}")
    if bad:
        print("\n[疑似失效]")
        for idx, code, note, url in bad:
            print(f"  [{idx}] {code} {url}")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
