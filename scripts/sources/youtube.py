"""
youtube.py - YouTube 频道 RSS 订阅
无需 API Key，使用 YouTube 官方 RSS Feed
RSS 地址格式：https://www.youtube.com/feeds/videos.xml?channel_id=频道ID
"""
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime


# YouTube RSS 命名空间
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}

YOUTUBE_RSS_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def fetch_channel(channel_id: str, top_n: int = 10) -> list[dict]:
    """
    抓取 YouTube 频道最新视频
    
    Args:
        channel_id: YouTube 频道 ID（UCxxxxxx 格式）
        top_n: 取最新 N 个视频
    
    Returns:
        标准化视频列表
    
    如何获取频道 ID：
        方法1：打开频道主页 → 右键查看源代码 → 搜索 "channel_id"
        方法2：频道 URL 如果是 /channel/UCxxxxxx 格式，UCxxxxxx 即为 ID
        方法3：使用浏览器插件 "YouTube Channel ID"
    """
    url = YOUTUBE_RSS_TEMPLATE.format(channel_id=channel_id)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; work-collect-v2/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
    except Exception as e:
        print(f"[YouTube] 频道 {channel_id} 抓取失败: {e}")
        return []
    
    return _parse_youtube_feed(content, channel_id, top_n)


def _parse_youtube_feed(content: bytes, channel_id: str, top_n: int) -> list[dict]:
    """解析 YouTube Atom Feed"""
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"[YouTube] 解析失败 {channel_id}: {e}")
        return items
    
    # 获取频道名称
    channel_name = root.findtext("{http://www.w3.org/2005/Atom}title", channel_id)
    
    entries = root.findall("{http://www.w3.org/2005/Atom}entry")[:top_n]
    for entry in entries:
        title = entry.findtext("{http://www.w3.org/2005/Atom}title", "").strip()
        video_id = entry.findtext(
            "{http://www.youtube.com/xml/schemas/2015}videoId", "")
        link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
        url = link_elem.get("href", "") if link_elem is not None else ""
        published = entry.findtext(
            "{http://www.w3.org/2005/Atom}published", "")
        
        # 获取描述
        media_group = entry.find(
            "{http://search.yahoo.com/mrss/}group")
        desc = ""
        if media_group is not None:
            desc_elem = media_group.find(
                "{http://search.yahoo.com/mrss/}description")
            if desc_elem is not None and desc_elem.text:
                desc = desc_elem.text[:200].strip()
        
        # 获取作者（频道名）
        author_elem = entry.find("{http://www.w3.org/2005/Atom}author")
        author = channel_name
        if author_elem is not None:
            author = author_elem.findtext(
                "{http://www.w3.org/2005/Atom}name", channel_name)
        
        if title and url:
            items.append({
                "title": title,
                "url": url,
                "desc": desc,
                "author": author,
                "channel_id": channel_id,
                "video_id": video_id,
                "date": published,
                "source": f"YouTube - {channel_name}",
                "platform": "youtube",
                "hot": "",
            })
    
    print(f"[YouTube] 频道 {channel_name}（{channel_id}）: 获取 {len(items)} 个视频")
    return items


def fetch_all(config: dict, top_n: int = 10) -> list[dict]:
    """
    批量抓取所有配置的 YouTube 频道
    
    Args:
        config: sources.yaml 中的 youtube 配置
        top_n: 每个频道取最新 N 个视频
    
    Returns:
        所有频道视频合并列表
    """
    if not config.get("enabled", True):
        print("[YouTube] YouTube 订阅已禁用，跳过")
        return []
    
    channels = config.get("channels", [])
    if not channels:
        print("[YouTube] 未配置频道，请在 config/sources.yaml 的 youtube.channels 中添加频道 ID")
        return []
    
    all_items = []
    for channel_id in channels:
        if channel_id:
            items = fetch_channel(channel_id.strip(), top_n)
            all_items.extend(items)
    
    return all_items
