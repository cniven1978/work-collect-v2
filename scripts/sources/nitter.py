"""
nitter.py - X/Twitter 内容抓取（via Nitter RSS）
支持：固定账号时间线监控 + 关键词话题追踪
Nitter 是 Twitter 的开源前端，提供 RSS 订阅，无需 API Key
"""
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional


# RSS 命名空间
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _get_working_instance(instances: list[str], path: str, timeout: int = 8) -> Optional[str]:
    """
    遍历 Nitter 实例列表，返回第一个可用的实例
    自动容灾切换
    """
    for instance in instances:
        url = f"{instance.rstrip('/')}/{path}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; work-collect-v2/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return instance
        except Exception:
            continue
    return None


def _parse_rss(content: bytes) -> list[dict]:
    """解析 RSS/Atom XML，返回标准化条目列表"""
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return items

    # RSS 2.0 格式
    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        url = item.findtext("link", "").strip()
        desc = item.findtext("description", "").strip()
        pub_date = item.findtext("pubDate", "").strip()
        author = item.findtext("dc:creator", namespaces=NS) or \
                 item.findtext("author", "").strip()
        
        # 清理 HTML 标签
        desc = _strip_html(desc)
        
        if title:
            items.append({
                "title": title,
                "url": url,
                "desc": desc[:200],
                "author": author,
                "date": pub_date,
                "source": "X/Twitter",
                "platform": "x_twitter",
            })
    
    return items


def _strip_html(text: str) -> str:
    """简单去除 HTML 标签"""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace(
        "&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    return clean.strip()


def fetch_account(instances: list[str], username: str, top_n: int = 20) -> list[dict]:
    """
    抓取指定 X 账号的最新推文
    
    Args:
        instances: Nitter 实例列表（自动容灾）
        username: X 用户名（不含@）
        top_n: 取最新 N 条
    
    Returns:
        标准化推文列表
    """
    path = f"{username}/rss"
    working = _get_working_instance(instances, path)
    if not working:
        print(f"[Nitter] 所有实例不可用，跳过账号 @{username}")
        print(f"[Nitter] 实例列表: {instances}")
        return []
    
    url = f"{working.rstrip('/')}/{path}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; work-collect-v2/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
    except Exception as e:
        print(f"[Nitter] 抓取 @{username} 失败: {e}")
        return []
    
    items = _parse_rss(content)[:top_n]
    for item in items:
        item["author"] = item["author"] or f"@{username}"
        item["account"] = username
    
    print(f"[Nitter] @{username}: 获取 {len(items)} 条")
    return items


def fetch_keyword(instances: list[str], keyword: str, top_n: int = 20) -> list[dict]:
    """
    追踪 X 上的关键词/话题
    
    Args:
        instances: Nitter 实例列表
        keyword: 搜索关键词
        top_n: 取前 N 条
    
    Returns:
        标准化结果列表
    """
    encoded = urllib.parse.quote(keyword)
    path = f"search/rss?q={encoded}&f=tweets"
    working = _get_working_instance(instances, path)
    if not working:
        print(f"[Nitter] 所有实例不可用，跳过关键词「{keyword}」")
        return []
    
    url = f"{working.rstrip('/')}/{path}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; work-collect-v2/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
    except Exception as e:
        print(f"[Nitter] 关键词「{keyword}」抓取失败: {e}")
        return []
    
    items = _parse_rss(content)[:top_n]
    for item in items:
        item["keyword"] = keyword
        item["source"] = f"X/Twitter #{keyword}"
    
    print(f"[Nitter] 关键词「{keyword}」: 获取 {len(items)} 条")
    return items


def fetch_all(config: dict, top_n: int = 20) -> list[dict]:
    """
    批量抓取所有配置的账号和关键词
    
    Args:
        config: sources.yaml 中的 x_twitter 配置
        top_n: 每个账号/关键词取前 N 条
    
    Returns:
        所有条目合并列表
    """
    if not config.get("enabled", True):
        print("[Nitter] X/Twitter 已禁用，跳过")
        return []
    
    instances = config.get("nitter_instances", [
        "https://nitter.net",
        "https://nitter.privacydev.net",
    ])
    
    all_items = []
    
    # 抓取固定账号
    for account in config.get("accounts", []):
        items = fetch_account(instances, account, top_n)
        all_items.extend(items)
    
    # 追踪关键词
    for keyword in config.get("keywords", []):
        items = fetch_keyword(instances, keyword, top_n)
        all_items.extend(items)
    
    return all_items
