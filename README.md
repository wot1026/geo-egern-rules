# geo-egern-rules

自动构建的 Egern / Loon 分类规则集，思路参考自 [xishang0128/rules](https://github.com/xishang0128/rules) 的上游数据源与去冗余方法，但输出格式改为 Egern YAML 和 Loon `.list` 纯文本规则（而非 geosite/geoip 二进制库），便于直接在 Egern / Loon 配置里按 URL 引用。

## 目录结构

```
sources.yaml          # 所有分类的上游数据源定义
scripts/
  parsers.py           # 各上游格式解析器 (clash_yaml / dnsmasq_conf / domain_list_custom / plain_hosts)
  dedup.py              # 去冗余逻辑：移除被父域名 suffix 覆盖的子域名
  convert_output.py     # 渲染 Egern YAML / Loon list
  build.py              # 主构建入口
egern/<category>.yaml   # 构建产物：Egern 规则集
loon/<category>.list    # 构建产物：Loon 规则集
SUMMARY.md               # 每次构建后的分类规则数量汇总
.github/workflows/build.yml   # 每日自动构建 + 提交 + 清 CDN 缓存
```

## 分类清单

| 分类 | 语义 | 主要上游 |
|---|---|---|
| china_direct | 中国大陆域名直连 | blackmatrix7 ChinaMax + Loyalsoldier cn.txt |
| google_cn / apple_cn | 中国区 CDN 加速节点直连 | felixonmars dnsmasq-china-list |
| global_proxy | 全球域名白名单代理 | Loyalsoldier geolocation-!cn |
| google / github / netflix / openai / telegram / twitter / tiktok / youtube / spotify / microsoft / apple_global / applemusic / cloudflare / abema / bahamut / global_media | 分类服务代理规则 | blackmatrix7/ios_rule_script 各分类 |
| onedrive / bilibili | 直连（国内可达服务） | blackmatrix7/ios_rule_script |
| private_tracker | PT 站点代理 | blackmatrix7/ios_rule_script |
| block_httpdns / windows_spy | 拒绝（隐私/遥测拦截） | blackmatrix7 BlockHttpDNS + WindowsSpyBlocker |

完整分类定义、上游 URL、额外补充域名见 `sources.yaml`。

## 本地构建

```bash
pip install pyyaml
python3 scripts/build.py                    # 构建全部分类
python3 scripts/build.py --only openai,github  # 只构建指定分类，便于调试
```

## 去冗余逻辑

思路移植自 xishang0128/rules 的 `findRedundantDomain.py`：

- 如果 `a.com` 和 `www.a.com` 同时出现在 suffix 列表中，`www.a.com` 被 `a.com` 覆盖，自动剔除。
- `full:` 精确匹配规则如果已被某条 suffix 规则覆盖，同样剔除。
- `regexp:` 规则因 Egern/Loon 均不支持而被丢弃，构建日志会报告丢弃数量（详见 `SUMMARY.md`）。

## 在 Egern / Loon 中引用

**Egern** (YAML 规则集，jsDelivr CDN 加速)：

```yaml
rule_providers:
  openai:
    url: https://cdn.jsdelivr.net/gh/<your-username>/geo-egern-rules@main/egern/openai.yaml
    interval: 86400
    behavior: classical
```

**Loon** (.list 规则集)：

```
[Rule]
RULE-SET,https://cdn.jsdelivr.net/gh/<your-username>/geo-egern-rules@main/loon/openai.list,PROXY
```

将 `<your-username>` 替换为实际仓库路径。建议直连类分类（`china_direct` / `*_cn` / `onedrive` / `bilibili`）指向 DIRECT 策略，`block_httpdns` / `windows_spy` 指向 REJECT，其余指向 PROXY，具体对照见 `sources.yaml` 中每个分类的 `action` 字段。

## 更新频率

GitHub Actions 每日 UTC+8 06:30 自动拉取上游、重新构建并提交（与 xishang0128/rules 的调度时间错开半小时，避免同时段给上游造成压力）。也可以在 Actions 页面手动触发 `workflow_dispatch`。

## 新增分类

在 `sources.yaml` 的 `categories` 下新增一个 key，指定 `action`（DIRECT/PROXY/REJECT，仅用于文档标注，不影响实际输出格式）和 `sources` 列表即可，构建脚本会自动识别并生成对应的 Egern/Loon 文件。
