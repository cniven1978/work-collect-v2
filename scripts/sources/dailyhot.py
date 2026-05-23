"""
dailyhot.py - DailyHot API 数据抓取
支持：微信/小红书/微博/知乎/B站/百度/抖音/凤凰网等 35+ 平台
自部署文档：https://github.com/imsyy/DailyHotApi
"""
import json
import urllib.request
import urllib.error
from typing import Optional


# 平台中文名映射
PLATFORM_NAMES = {
    "weixin": "微信公众号",
    "xiaohongshu": "小红书",
    "weibo": "微博热搜",
    "zhihu": "知乎热榜",
    "bilibili": "B站热搜",
    "baidu": "百度热搜",
    "toutiao": "今日头条",
    "douyin": "抖音热搜",
    "ifeng": "凤凰网",
    "tieba": "百度贴吧",
    "36kr": "36氪",
    "ithome": "IT之家",
    "lol": "英雄联盟",
    "github": "GitHub Trending",
    "juejin": "掘金",
}


def fetch_platform(base_url: str, platform: str, top_n: int = 20) -> list[dict]:
    """
    从 DailyHot 拉取指定平台热榜
    
    Args:
        base_url: DailyHot 实例地址，如 http://localhost:6688
        platform: 平台标识，如 weixin / xiaohongshu
        top_n: 取前 N 条
    
    Returns:
        标准化后的条目列表
    """
    url = f"{base_url.rstrip('/')}/{platform}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "work-collect-v2/1.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"[DailyHot] 无法连接 {url}: {e}")
        print(f"[DailyHot] 请确认 DailyHot 已启动：cd docker && docker compose up -d")
        return []
    except Exception as e:
        print(f"[DailyHot] {platform} 抓取失败: {e}")
        return []

    # DailyHot 返回格式：{"code": 200, "name": "...", "data": [...]}
    if not isinstance(data, dict) or data.get("code") != 200:
        print(f"[DailyHot] {platform} 返回异常: {data.get('message', '未知错误')}")
        return []

    raw_items = data.get("data", [])[:top_n]
    source_name = PLATFORM_NAMES.get(platform, platform)
    
    items = []
    for item in raw_items:
        items.append({
            "title": item.get("title", "").strip(),
            "url": item.get("url") or item.get("mobileUrl", ""),
            "desc": item.get("desc", "").strip(),
            "hot": _format_hot(item.get("hot")),
            "author": item.get("author", ""),
            "source": source_name,
            "platform": platform,
            "timestamp": item.get("timestamp", ""),
        })
    
    return items


def fetch_all_platforms(base_url: str, platforms: list[str], top_n: int = 20) -> list[dict]:
    """
    批量抓取多个平台热榜
    
    Args:
        base_url: DailyHot 实例地址
        platforms: 平台列表
        top_n: 每平台取前 N 条
    
    Returns:
        所有平台条目合并列表
    """
    all_items = []
    for platform in platforms:
        items = fetch_platform(base_url, platform, top_n)
        if items:
            print(f"[DailyHot] {PLATFORM_NAMES.get(platform, platform)}: 获取 {len(items)} 条")
            all_items.extend(items)
        else:
            print(f"[DailyHot] {PLATFORM_NAMES.get(platform, platform)}: 无数据")
    return all_items


def check_connection(base_url: str) -> bool:
    """检查 DailyHot 实例是否可访问"""
    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/",
            headers={"User-Agent": "work-collect-v2/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


def _format_hot(hot_val) -> str:
    """格式化热度值"""
    if hot_val is None:
        return ""
    try:
        n = int(hot_val)
        if n >= 10000:
            return f"{n / 10000:.1f}万"
        return str(n)
    except (ValueError, TypeError):
        return str(hot_val)
