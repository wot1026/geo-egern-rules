#!/usr/bin/env python3
"""
去冗余逻辑，思路移植自 xishang0128/rules 的 findRedundantDomain.py + removeFrom.py：

1. suffix 域名（裸域名，视为 DOMAIN-SUFFIX）之间做父子覆盖去重：
   如果 a.com 和 www.a.com 同时存在，www.a.com 被 a.com 覆盖，删除 www.a.com。
2. full: / keyword: / regexp: 类型的规则不参与覆盖判断，原样保留（但去重复行）。

输入: list[str]，每行是 "full:xxx" / "keyword:xxx" / "regexp:xxx" / 裸域名(=suffix)
输出: (suffix_domains: list[str], full_domains: list[str],
       keyword_domains: list[str], regexp_domains: list[str])
      均已去冗余 + 排序
"""
from __future__ import annotations


def _is_covered(domain: str, suffix_set: set[str]) -> bool:
    """domain 是否被 suffix_set 中的某个更短的父域名覆盖（不含自身）"""
    parts = domain.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[i:])
        if parent in suffix_set and parent != domain:
            return True
    return False


def dedup_rules(lines: list[str]):
    suffix_raw: set[str] = set()
    full_raw: set[str] = set()
    keyword_raw: set[str] = set()
    regexp_raw: set[str] = set()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("full:"):
            full_raw.add(line[len("full:"):].strip().lower())
        elif line.startswith("keyword:"):
            keyword_raw.add(line[len("keyword:"):].strip().lower())
        elif line.startswith("regexp:"):
            regexp_raw.add(line[len("regexp:"):].strip())
        else:
            suffix_raw.add(line.lstrip(".").strip().lower())

    # 父子覆盖去重，仅在 suffix 集合内部做
    suffix_clean = {d for d in suffix_raw if not _is_covered(d, suffix_raw)}

    # full: 类型如果已经被某个 suffix 覆盖，也可以去掉（xxx.com full 被 xxx.com suffix 覆盖）
    full_clean = {d for d in full_raw if not _is_covered(d, suffix_clean) and d not in suffix_clean}

    return (
        sorted(suffix_clean),
        sorted(full_clean),
        sorted(keyword_raw),
        sorted(regexp_raw),
    )


if __name__ == "__main__":
    import sys
    data = sys.stdin.read().splitlines()
    s, f, k, r = dedup_rules(data)
    print(f"# suffix={len(s)} full={len(f)} keyword={len(k)} regexp={len(r)}", file=sys.stderr)
    for d in s:
        print(d)
