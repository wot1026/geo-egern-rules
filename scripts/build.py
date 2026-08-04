#!/usr/bin/env python3
"""
主构建入口。

用法:
  python3 scripts/build.py [--only category1,category2] [--sources sources.yaml]

流程:
  1. 读取 sources.yaml
  2. 对每个 category，拉取其所有上游源，用对应 parser 解析成统一规则行
  3. 加上 extra_domains（如果有）
  4. dedup_rules 去冗余
  5. 渲染 egern/<category>.yaml + loon/<category>.list
  6. 生成 SUMMARY.md 汇总各分类规则数量、action、更新时间

失败处理: 单个上游源拉取失败不应中断整体构建，记录警告并跳过该源。
"""
from __future__ import annotations
import argparse
import datetime
import os
import sys
import time
import urllib.request
import urllib.error

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from parsers import PARSERS
from dedup import dedup_rules
from convert_output import render_egern, render_loon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "geo-egern-rules-builder/1.0 (+https://github.com/)"


def fetch(url: str, retries: int = 3, timeout: int = 20) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"  [warn] fetch failed ({attempt}/{retries}): {url} -> {e}", file=sys.stderr)
            time.sleep(1.5 * attempt)
    print(f"  [error] giving up on: {url}", file=sys.stderr)
    return None


def build_category(name: str, cfg: dict) -> dict:
    print(f"==> building category: {name}")
    all_lines: list[str] = []

    for src in cfg.get("sources", []):
        stype = src["type"]
        url = src["url"]
        parser = PARSERS.get(stype)
        if parser is None:
            print(f"  [warn] unknown source type '{stype}' for {url}, skipping", file=sys.stderr)
            continue

        text = fetch(url)
        if text is None:
            continue

        kwargs = {}
        if stype == "domain_list_custom":
            if "exclude_keywords" in src:
                kwargs["exclude_keywords"] = src["exclude_keywords"]
            if "exclude_suffix_cn" in src:
                kwargs["exclude_suffix_cn"] = src["exclude_suffix_cn"]

        parsed = parser(text, **kwargs)
        print(f"  - {stype}: {url} -> {len(parsed)} rules")
        all_lines.extend(parsed)

    for extra in cfg.get("extra_domains", []):
        all_lines.append(extra)

    suffix, full, keyword, regexp = dedup_rules(all_lines)

    if regexp:
        print(f"  [info] dropped {len(regexp)} regexp rules (unsupported by Egern/Loon)", file=sys.stderr)

    total = len(suffix) + len(full) + len(keyword)
    print(f"  => total {total} rules (suffix={len(suffix)} full={len(full)} keyword={len(keyword)})")

    egern_dir = os.path.join(ROOT, "egern")
    loon_dir = os.path.join(ROOT, "loon")
    os.makedirs(egern_dir, exist_ok=True)
    os.makedirs(loon_dir, exist_ok=True)

    with open(os.path.join(egern_dir, f"{name}.yaml"), "w", encoding="utf-8") as f:
        f.write(render_egern(suffix, full, keyword, name))

    with open(os.path.join(loon_dir, f"{name}.list"), "w", encoding="utf-8") as f:
        f.write(render_loon(suffix, full, keyword, name))

    return {
        "name": name,
        "action": cfg.get("action", "PROXY"),
        "total": total,
        "suffix": len(suffix),
        "full": len(full),
        "keyword": len(keyword),
        "regexp_dropped": len(regexp),
    }


def write_summary(results: list[dict]):
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M %Z")
    lines = [
        "# Build Summary",
        "",
        f"Last built: {now} (UTC+8)",
        "",
        "| Category | Action | Total | Suffix | Full | Keyword | Regexp Dropped |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['action']} | {r['total']} | {r['suffix']} | "
            f"{r['full']} | {r['keyword']} | {r['regexp_dropped']} |"
        )
    with open(os.path.join(ROOT, "SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="逗号分隔的分类名，仅构建这些分类")
    ap.add_argument("--sources", default=os.path.join(ROOT, "sources.yaml"))
    args = ap.parse_args()

    with open(args.sources, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    categories = config["categories"]
    if args.only:
        wanted = set(args.only.split(","))
        categories = {k: v for k, v in categories.items() if k in wanted}
        missing = wanted - categories.keys()
        if missing:
            print(f"[warn] unknown categories requested: {missing}", file=sys.stderr)

    results = []
    for name, cfg in categories.items():
        try:
            results.append(build_category(name, cfg))
        except Exception as e:
            print(f"[error] category '{name}' failed entirely: {e}", file=sys.stderr)

    write_summary(results)
    print(f"\nDone. Built {len(results)} categories.")


if __name__ == "__main__":
    main()
