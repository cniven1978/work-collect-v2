"""
collect.py - 定向信息收集主脚本
功能：抓取订阅源最新内容、手动收藏内容处理、每日简报生成

使用方式：
  python scripts/collect.py --daily          # 每日定时采集所有订阅源
  python scripts/collect.py --save <url>     # 手动收藏单条内容
  python scripts/collect.py --list           # 列出所有订阅源
"""
import sys
import json
import argparse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sources.utils import (
    load_sources_config, load_notify_config, load_keywords,
    filter_items_by_keywords, dedup_items,
    load_seen_hashes, save_seen_hashes,
    save_output, push_feishu, write_log,
    format_digest_markdown
)

BASE_DIR = Path(__file__).parent.parent
COLLECTION_DIR = BASE_DIR / "collection"
INBOX_DIR = BASE_DIR / "inbox"
CONTENT_INDEX = BASE_DIR / "content_index.json"


# ---------------------------------------------------------------
# RSS 抓取
# ---------------------------------------------------------------
def fetch_rss(url: str, top_n: int = 10) -> list[dict]:
    """通用 RSS 抓取"""
    if not url:
        return []
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; work-collect-v2/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
    except Exception as e:
        print(f"[RSS] 抓取失败 {url}: {e}")
        return []

    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return items

    for item in root.findall(".//item")[:top_n]:
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        desc = item.findtext("description", "").strip()
        pub_date = item.findtext("pubDate", "").strip()
        author = item.findtext("author", "").strip()

        # 去除 HTML 标签
        import re
        desc = re.sub(r"<[^>]+>", "", desc)[:200]

        if title:
            items.append({
                "title": title,
                "url": link,
                "desc": desc,
                "author": author,
                "date": pub_date,
                "platform": "rss",
            })
    return items


def fetch_website(site: dict, top_n: int = 10) -> list[dict]:
    """抓取单个网站订阅源"""
    name = site.get("name", "")
    rss_url = site.get("rss", "")
    category = site.get("category", "工作参考")

    items = []
    if rss_url:
        items = fetch_rss(rss_url, top_n)
        for item in items:
            item["source"] = name
            item["category"] = category
        print(f"[订阅源] {name}: 获取 {len(items)} 条")
    else:
        print(f"[订阅源] {name}: 未配置 RSS，跳过（可手动收藏）")
    return items


# ---------------------------------------------------------------
# 手动收藏
# ---------------------------------------------------------------
def save_content(url: str) -> dict:
    """
    手动收藏单条内容（链接/文章）
    提取标题、正文、来源，格式化为标准 Markdown
    """
    print(f"[收藏] 正在处理：{url}")

    # 基础信息提取
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; work-collect-v2/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[收藏] 无法访问链接：{e}")
        return {}

    # 提取标题
    import re
    title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else "未知标题"
    title = re.sub(r"<[^>]+>", "", title)

    # 提取正文（简单提取，实际使用建议配合 readability 库）
    body = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.DOTALL)
    body = re.sub(r"<[^>]+>", "", body)
    body = re.sub(r"\s+", " ", body).strip()[:3000]

    now = datetime.now()
    item = {
        "title": title,
        "url": url,
        "source": _detect_source(url),
        "collected_at": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "desc": body[:200],
        "body": body,
        "category": "inbox",
        "platform": "web",
    }

    # 生成 Markdown
    md = _format_article_markdown(item)

    # 保存到 inbox
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:50]
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{safe_title}"
    md_file = INBOX_DIR / f"{filename}.md"
    md_file.write_text(md, encoding="utf-8")

    # 更新 content_index.json
    _update_content_index(item, str(md_file.relative_to(BASE_DIR)))

    print(f"[收藏] ✅ 已保存：{md_file}")
    print(f"[收藏] 请通过主人指令将内容从 inbox/ 移至对应分类")
    return item


def _detect_source(url: str) -> str:
    """根据 URL 检测来源平台"""
    url_lower = url.lower()
    if "vbdata.cn" in url_lower:
        return "动脉网"
    if "36kr.com" in url_lower:
        return "36氪"
    if "qimingpian.com" in url_lower:
        return "企名片"
    if "10jqka.com.cn" in url_lower:
        return "同花顺"
    if "mp.weixin.qq.com" in url_lower:
        return "微信公众号"
    if "xiaohongshu.com" in url_lower or "xhslink.com" in url_lower:
        return "小红书"
    if "weibo.com" in url_lower:
        return "微博"
    if "zhihu.com" in url_lower:
        return "知乎"
    if "bilibili.com" in url_lower:
        return "B站"
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    if "twitter.com" in url_lower or "x.com" in url_lower:
        return "X/Twitter"
    return "网页"


def _format_article_markdown(item: dict) -> str:
    """生成标准 Markdown 格式"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""---
title: {item.get('title', '未知标题')}
source: {item.get('source', '未知来源')}
author: {item.get('author', '')}
date: {item.get('date', '')}
original_url: {item.get('url', '')}
collected_at: {item.get('collected_at', now)}
tags: []
category: {item.get('category', 'inbox')}
reading_time: 约{max(1, len(item.get('body', '')) // 400)}分钟
---

# {item.get('title', '未知标题')}

## 摘要

> ⚠️ 摘要待整理：请阅读正文后补充摘要（不超过1000字，一句话定位+核心内容+关键数据/结论）

## 正文

{item.get('body', '正文提取失败，请手动粘贴原文')}

### 备注

_由 work-collect-v2 自动收录，收录时间：{now}_
"""


def _update_content_index(item: dict, file_path: str):
    """更新 content_index.json"""
    index = {"version": "1.0", "last_updated": "", "total_articles": 0, "articles": []}
    if CONTENT_INDEX.exists():
        try:
            index = json.loads(CONTENT_INDEX.read_text(encoding="utf-8"))
        except Exception:
            pass

    articles = index.get("articles", [])
    new_id = max((a.get("id", 0) for a in articles), default=0) + 1

    articles.append({
        "id": new_id,
        "title": item.get("title", ""),
        "source": item.get("source", ""),
        "author": item.get("author", ""),
        "date": item.get("date", ""),
        "category": item.get("category", "inbox"),
        "file_path": file_path,
        "tags": item.get("tags", []),
        "reading_time": f"约{max(1, len(item.get('body', '')) // 400)}分钟",
    })

    index["articles"] = articles
    index["total_articles"] = len(articles)
    index["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    CONTENT_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------
# 每日采集
# ---------------------------------------------------------------
def run_daily():
    """每日定时采集所有订阅源"""
    print(f"\n{'='*50}")
    print(f"[每日采集] 开始，时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    config = load_sources_config()
    keywords = load_keywords()
    notify_config = load_notify_config()

    all_items = []

    # 抓取网站订阅源
    for site in config.get("websites", []):
        if site.get("status") == "active":
            items = fetch_website(site)
            all_items.extend(items)

    print(f"\n[每日采集] 共获取 {len(all_items)} 条原始内容")

    # 关键词过滤
    if keywords:
        filtered = filter_items_by_keywords(all_items, keywords)
        print(f"[过滤] 命中关键词：{len(filtered)} 条")
    else:
        filtered = all_items

    # 去重
    seen = load_seen_hashes("collect", 24)
    new_items, new_hashes = dedup_items(filtered, seen)
    print(f"[去重] 新增内容：{len(new_items)} 条")

    if not new_items:
        print("[每日采集] 无新内容")
        return

    # 生成简报
    content_md = format_digest_markdown(new_items, "每日订阅源更新", "digest")

    # 留档
    timestamp = datetime.now().strftime("%H%M%S")
    md_file, json_file = save_output("collect", f"daily_{timestamp}", content_md, new_items)
    print(f"\n[留档] {md_file}")

    # 更新去重记录
    save_seen_hashes("collect", new_hashes, 24)

    # 飞书推送
    feishu_config = notify_config.get("feishu", {})
    webhook = feishu_config.get("webhook", "")
    if webhook and feishu_config.get("enabled", False):
        push_feishu(webhook, content_md[:4000], "每日订阅源更新")

    # 输出到终端
    print(f"\n{'='*50}")
    print(content_md)
    print(f"{'='*50}\n")

    write_log(f"每日采集完成，新增={len(new_items)}", "INFO")
    return content_md


# ---------------------------------------------------------------
# 列出订阅源
# ---------------------------------------------------------------
def list_sources():
    """列出所有配置的订阅源"""
    config = load_sources_config()

    print("\n📋 当前订阅源列表\n")

    websites = config.get("websites", [])
    if websites:
        print("## 📰 网站/媒体")
        for s in websites:
            status = "✅" if s.get("status") == "active" else "⏳"
            print(f"  {status} {s['name']} - {s.get('note', '')} ({s.get('url', '')})")

    wechats = config.get("wechat", [])
    if wechats:
        print("\n## 💬 微信公众号（via DailyHot）")
        for s in wechats:
            status = "✅" if s.get("status") == "active" else "⏳"
            print(f"  {status} {s['name']} - {s.get('note', '')}")

    x_config = config.get("x_twitter", {})
    accounts = x_config.get("accounts", [])
    keywords = x_config.get("keywords", [])
    if accounts or keywords:
        print("\n## 🐦 X/Twitter（via Nitter RSS）")
        for a in accounts:
            print(f"  ✅ @{a}")
        for k in keywords:
            print(f"  🔍 关键词：{k}")

    yt_config = config.get("youtube", {})
    channels = yt_config.get("channels", [])
    if channels:
        print("\n## 📺 YouTube 频道")
        for c in channels:
            print(f"  ✅ {c}")

    dh_config = config.get("dailyhot", {})
    platforms = dh_config.get("platforms", [])
    if platforms:
        print("\n## 🔥 热点平台（DailyHot）")
        print(f"  实例地址：{dh_config.get('base_url', 'http://localhost:6688')}")
        print(f"  平台：{', '.join(platforms)}")

    print("\n修改订阅源：编辑 config/sources.yaml 即可，无需重启")


# ---------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="work-collect-v2 定向信息收集")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--daily", action="store_true", help="每日定时采集所有订阅源")
    group.add_argument("--save", metavar="URL", help="手动收藏单条内容")
    group.add_argument("--list", action="store_true", help="列出所有订阅源")
    args = parser.parse_args()

    if args.daily:
        run_daily()
    elif args.save:
        save_content(args.save)
    elif args.list:
        list_sources()


if __name__ == "__main__":
    main()
