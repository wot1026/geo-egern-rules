#!/usr/bin/env python3
"""
把各种上游格式解析成统一的规则行：
  "example.com"          -> DOMAIN-SUFFIX 语义（裸域名）
  "full:example.com"     -> DOMAIN 精确匹配
  "keyword:foo"          -> DOMAIN-KEYWORD
  "regexp:^[a-z]+$"      -> 正则（Egern/Loon 不支持时会被丢弃或转告警）
"""
from __future__ import annotations
import re


def parse_clash_yaml(text: str) -> list[str]:
    """
    blackmatrix7 风格 Clash yaml，两种 payload 行格式都存在于其仓库中:

    A) 显式类型前缀 (大多数分类规则文件):
        - 'DOMAIN-SUFFIX,netflix.com'
        - 'DOMAIN,netflix.net'
        - 'DOMAIN-KEYWORD,netflix'
        - 'IP-CIDR,1.2.3.0/24,no-resolve'   <- 忽略 IP 规则

    B) 裸域名 (如 ChinaMax_Domain.yaml，头部注释说明 DOMAIN-SUFFIX 数量，
       payload 直接是不带前缀的域名，隐含全部按 DOMAIN-SUFFIX 处理):
        - 'cpro.baidustatic.com'
        - 'download.jetbrains.com'

    对每一行：先尝试匹配显式类型前缀；不匹配则视为裸域名 -> DOMAIN-SUFFIX。
    IP-CIDR / IP-CIDR6 / IP-ASN / PROCESS-NAME 等非域名规则一律跳过。
    """
    out = []
    non_domain_prefixes = ("IP-CIDR", "IP-CIDR6", "IP-ASN", "PROCESS-NAME", "USER-AGENT")

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.lstrip("-").strip()
        line = line.strip("'\"")
        if not line or line.startswith("payload:"):
            continue

        m = re.match(r"^(DOMAIN-SUFFIX|DOMAIN|DOMAIN-KEYWORD),\s*([^\s,]+)", line, re.I)
        if m:
            kind, value = m.group(1).upper(), m.group(2).strip()
            if kind == "DOMAIN-SUFFIX":
                out.append(value.lower())
            elif kind == "DOMAIN":
                out.append(f"full:{value.lower()}")
            elif kind == "DOMAIN-KEYWORD":
                out.append(f"keyword:{value.lower()}")
            continue

        if line.upper().startswith(non_domain_prefixes):
            continue

        # 裸域名格式：视为 DOMAIN-SUFFIX。简单校验一下形如域名（含至少一个点，无空格）。
        if " " not in line and "," not in line and "." in line:
            out.append(line.lower())

    return out


def parse_dnsmasq_conf(text: str) -> list[str]:
    """felixonmars dnsmasq-china-list: server=/example.com/114.114.114.114"""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^server=/([^/]+)/", line)
        if m:
            out.append(f"full:{m.group(1).strip().lower()}")
    return out


def parse_domain_list_custom(text: str, exclude_keywords=None, exclude_suffix_cn=False) -> list[str]:
    """
    Loyalsoldier domain-list-custom 风格:
      domain:example.com
      full:example.com
      regexp:^example
      keyword:example
      full:example.com:@cn      <- 冒号+@ 标记的属性，例如 @cn @ads @!cn 等，需要剥离
      domain:example.com @cn    <- 部分文件里是空格分隔，也一并兼容

    实测该仓库的属性标注实际写法是紧跟在域名后面用 ":@attr" 分隔（无空格），
    例如 "full:cdn.apple-mapkit.com:@cn"。之前的实现只处理了空格分隔的写法，
    导致 ":@cn" 被当成域名的一部分保留了下来，产出脏数据。这里同时兼容两种写法。
    """
    exclude_keywords = exclude_keywords or []
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if any(kw in line for kw in exclude_keywords):
            continue
        # 去掉 @attr 后缀：兼容 ":@attr"（无空格，实际最常见）和 " @attr"（空格分隔）两种写法
        line = re.split(r":?\s*@", line)[0].strip()
        m = re.match(r"^(domain|full|regexp|keyword):(.+)$", line)
        if not m:
            continue
        kind, value = m.group(1), m.group(2).strip().lower()
        if exclude_suffix_cn and value.endswith(".cn"):
            continue
        if kind == "domain":
            out.append(value)
        elif kind == "full":
            out.append(f"full:{value}")
        elif kind == "keyword":
            out.append(f"keyword:{value}")
        elif kind == "regexp":
            out.append(f"regexp:{value}")
    return out


def parse_plain_hosts(text: str) -> list[str]:
    """WindowsSpyBlocker 风格: '0.0.0.0 telemetry.microsoft.com'"""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            out.append(f"full:{parts[1].strip().lower()}")
    return out


PARSERS = {
    "clash_yaml": parse_clash_yaml,
    "dnsmasq_conf": parse_dnsmasq_conf,
    "domain_list_custom": parse_domain_list_custom,
    "plain_hosts": parse_plain_hosts,
}
