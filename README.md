# work-collect-v2

> 左霖的信息收集与热点追踪助理，为 OpenClaw 设计。
> 支持：定向订阅采集 · 多平台热点聚合 · X/YouTube 订阅 · 飞书推送 · 自动留档

---

## 功能概览

| 功能 | 说明 | 数据来源 |
|------|------|------|
| 定向信息收集 | 抓取订阅媒体最新内容 | RSS / 网页 |
| 微信/小红书热榜 | 国内35+平台热点聚合 | DailyHot API（自部署） |
| X/Twitter 监控 | 固定账号时间线 + 关键词追踪 | Nitter RSS（免费） |
| YouTube 订阅 | 频道最新视频推送 | YouTube 官方 RSS（免费） |
| 热点追踪 | 多平台热榜聚合 + 关键词过滤 + AI摘要 | DailyHot + Nitter + YouTube |
| 每日简报 | 定时汇总推送到飞书 | 以上所有来源 |
| 自动留档 | 每次执行 Markdown + JSON 双格式存档 | 本地 output/ 目录 |

---

## 快速开始

### 第一步：部署 DailyHot（国内平台热榜聚合）

DailyHot 是获取微信、小红书、微博等国内平台热榜的核心服务，需要自行部署。

**前提：** 已安装 [Docker](https://docs.docker.com/get-docker/)

```bash
# 启动 DailyHot
cd docker
docker compose up -d

# 验证是否正常运行
curl http://localhost:6688/weixin        # 微信热文
curl http://localhost:6688/xiaohongshu  # 小红书热榜
curl http://localhost:6688/weibo        # 微博热搜
```

启动成功后，访问 http://localhost:6688 可查看所有支持的平台列表（35+个）。

**常用命令：**
```bash
docker logs -f dailyhot          # 查看日志
docker compose down              # 停止
docker compose pull && docker compose up -d  # 更新到最新版
```

### 第二步：安装 Python 依赖

```bash
pip install pyyaml
```

> 注：项目尽量使用 Python 标准库，只需安装 pyyaml 一个依赖。

### 第三步：配置订阅源

编辑 `config/sources.yaml`，填入你的订阅信息：

```yaml
# X/Twitter 账号（填用户名，不含@）
x_twitter:
  accounts:
    - elonmusk
    - OpenAI

# YouTube 频道（填频道ID）
youtube:
  channels:
    - UCxxxxxxxxxxxxxxxxxxxxxx
```

### 第四步：配置关键词

编辑 `config/keywords.txt`，一行一个关键词（已预置医疗器械相关关键词）：

```
医疗器械
脑机接口
AI医疗
# 可随时追加
```

### 第五步：在 OpenClaw 中使用

将本仓库配置为 OpenClaw Skill 后，直接对话触发：

| 说什么 | 效果 |
|--------|------|
| `今天有什么热点` | 当前各平台热榜（关键词过滤后） |
| `新增热点` | 仅上次执行后新增的热点 |
| `生成简报` | 每日汇总简报（含订阅源+热点） |
| `帮我收藏 [链接]` | 收藏单条内容到 inbox/ |
| `查看订阅源` | 列出所有已配置的订阅源 |
| `添加订阅源 xxx` | 添加新订阅源 |

---

## 配置文件说明

### config/sources.yaml（核心配置）

```yaml
dailyhot:
  base_url: "http://localhost:6688"  # DailyHot 实例地址
  platforms:                          # 开启的热榜平台
    - weixin      # 微信
    - xiaohongshu # 小红书
    - weibo       # 微博
    # 更多平台见 DailyHot 文档

x_twitter:
  nitter_instances:    # Nitter 实例（多个自动容灾）
    - "https://nitter.net"
  accounts:            # 监控的账号
    - username1
  keywords:            # 追踪的关键词
    - "AI medical"

youtube:
  channels:            # 订阅的频道 ID
    - UCxxxxxx

trend:
  mode: incremental    # current/incremental/digest
  top_n: 20            # 每平台取前N条
```

**如何获取 YouTube 频道 ID：**
1. 打开频道主页
2. 查看 URL，如果是 `/channel/UCxxxxxx` 格式，`UCxxxxxx` 即为 ID
3. 如果是 `/@username` 格式，右键查看源代码搜索 `channel_id`

### config/keywords.txt（关键词过滤）

```
# 一行一个，# 开头为注释
医疗器械
脑机接口
AI医疗
```

### config/notify.yaml（推送渠道）

默认走 OpenClaw 绑定的飞书渠道，无需额外配置。

如需多渠道推送，填入对应 Webhook：
```yaml
feishu:
  enabled: true
  webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"  # 填入后直接推送

telegram:
  enabled: false
  bot_token: ""
  chat_id: ""
```

---

## 文件结构

```
work-collect-v2/
├── SKILL.md                # OpenClaw 技能主文件
├── AGENTS.md               # 助理身份与协作规范
├── SOUL.md                 # 助理角色与职责
├── MEMORY.md               # 长期记忆与任务记录
├── README.md               # 本文档
├── scripts/
│   ├── collect.py          # 定向信息收集
│   ├── trend.py            # 热点追踪
│   └── sources/
│       ├── dailyhot.py     # DailyHot API 抓取
│       ├── nitter.py       # X/Twitter Nitter RSS
│       ├── youtube.py      # YouTube RSS 订阅
│       └── utils.py        # 工具函数（去重/过滤/留档/推送）
├── config/
│   ├── sources.yaml        # 订阅源配置（主配置文件）
│   ├── keywords.txt        # 关键词过滤列表
│   └── notify.yaml         # 推送渠道配置
├── output/
│   ├── collect/            # 定向采集留档
│   └── trend/              # 热点追踪留档
├── collection/             # 已分类收藏
│   └── 工作参考/
│       ├── 医疗器械技术与行业/
│       ├── 法规标准/
│       └── 投资分析/
├── favorites/              # 精选收藏
├── archive/                # 归档原文备份
├── inbox/                  # 新收录待分类
├── subscriptions.json      # 订阅源列表（兼容旧版）
├── content_index.json      # 内容索引
├── logs/                   # 执行日志
└── docker/
    └── docker-compose.yml  # DailyHot 一键部署
```

---

## 命令行直接使用

```bash
# 热点追踪
python scripts/trend.py --mode current       # 当前热榜快照
python scripts/trend.py --mode incremental   # 新增热点（默认）
python scripts/trend.py --mode digest        # 每日汇总简报

# 定向采集
python scripts/collect.py --daily            # 采集所有订阅源
python scripts/collect.py --save <URL>       # 收藏单条内容
python scripts/collect.py --list             # 查看所有订阅源
```

---

## 如何添加/修改订阅源

所有配置改完后，下次执行自动生效，无需重启任何服务。

| 操作 | 方法 |
|------|------|
| 添加 YouTube 频道 | `config/sources.yaml` → `youtube.channels` 追加频道ID |
| 添加 X 账号 | `config/sources.yaml` → `x_twitter.accounts` 追加用户名 |
| 添加 X 关键词 | `config/sources.yaml` → `x_twitter.keywords` 追加关键词 |
| 添加关键词过滤 | `config/keywords.txt` 追加一行 |
| 添加热榜平台 | `config/sources.yaml` → `dailyhot.platforms` 追加平台名 |
| 换推送渠道 | `config/notify.yaml` 填入 Webhook，`enabled: true` |

---

## 推送渠道切换说明

当前架构：
```
脚本执行 → 输出结果 → OpenClaw → 飞书（现有绑定）
```

如需切换或新增推送渠道：
- **换渠道（飞书→钉钉等）**：在 OpenClaw 设置里更换 Webhook，脚本不用动
- **多渠道并推**：在 `config/notify.yaml` 填入各渠道 Webhook，`enabled: true`
- **仅本地留档**：`output/` 目录会自动保存，不依赖任何推送渠道

---

## 常见问题

**Q: DailyHot 启动后无法访问？**
```bash
docker logs dailyhot  # 查看错误日志
# 确认 6688 端口未被占用
lsof -i :6688
```

**Q: Nitter 实例不可用？**

在 `config/sources.yaml` 的 `nitter_instances` 中更换实例地址。
可用实例列表参考：https://github.com/nicehash/nitter-instances

**Q: YouTube 频道 ID 怎么找？**

打开频道页面 → 右键查看源代码 → 搜索 `channel_id` → 复制 `UC` 开头的字符串。

**Q: 如何设置定时任务？**

```bash
# Linux/Mac 使用 crontab
crontab -e

# 添加以下行（每天 8:00 执行）
0 8 * * * cd /path/to/work-collect-v2 && python scripts/collect.py --daily
0 8 * * * cd /path/to/work-collect-v2 && python scripts/trend.py --mode digest
```

---

## 后续计划

- [ ] Claude Code 版本（CLAUDE.md 格式）
- [ ] Codex 版本
- [ ] 微信公众号 RSS 代理集成
- [ ] 更多热榜平台支持

---

_由 work-collect-v2 提供支持 | 当前版本：v2.0 | 更新日期：2026-05-23_
