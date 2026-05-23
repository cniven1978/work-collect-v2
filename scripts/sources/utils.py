"""
utils.py - 公共工具函数
去重、关键词过滤、格式化、存档
"""
import json
import os
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"


def load_keywords() -> list[str]:
    """从 keywords.txt 加载关键词列表"""
    kw_file = CONFIG_DIR / "keywords.txt"
    keywords = []
    if kw_file.exists():
        for line in kw_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                keywords.append(line)
    return keywords


def load_sources_config() -> dict:
    """加载 sources.yaml 配置"""
    try:
        import yaml
        config_file = CONFIG_DIR / "sources.yaml"
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                return yaml.safe_load(f)
    except ImportError:
        pass
    return {}


def load_notify_config() -> dict:
    """加载 notify.yaml 推送配置"""
    try:
        import yaml
        notify_file = CONFIG_DIR / "notify.yaml"
        if notify_file.exists():
            with open(notify_file, encoding="utf-8") as f:
                return yaml.safe_load(f)
    except ImportError:
        pass
    return {}


# ---------------------------------------------------------------
# 关键词过滤
# ---------------------------------------------------------------
def match_keywords(text: str, keywords: list[str]) -> list[str]:
    """返回 text 中命中的关键词列表，空列表表示未命中"""
    if not keywords:
        return ["*"]  # 无关键词配置时全部通过
    text_lower = text.lower()
    matched = []
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)
    return matched


def filter_items_by_keywords(items: list[dict], keywords: list[str]) -> list[dict]:
    """过滤列表，只保留命中关键词的条目，并附上命中词"""
    if not keywords:
        return items
    result = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('desc', '')} {item.get('author', '')}"
        matched = match_keywords(text, keywords)
        if matched:
            item["matched_keywords"] = matched
            result.append(item)
    return result


# ---------------------------------------------------------------
# 去重
# ---------------------------------------------------------------
def item_hash(item: dict) -> str:
    """生成条目唯一 hash（基于标题+来源）"""
    key = f"{item.get('title', '')}{item.get('source', '')}{item.get('url', '')}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def load_seen_hashes(output_type: str, window_hours: int = 24) -> set:
    """读取最近 window_hours 内已见过的条目 hash"""
    seen = set()
    seen_file = OUTPUT_DIR / output_type / "seen_hashes.json"
    if not seen_file.exists():
        return seen
    try:
        data = json.loads(seen_file.read_text(encoding="utf-8"))
        cutoff = datetime.now() - timedelta(hours=window_hours)
        for h, ts in data.items():
            if datetime.fromisoformat(ts) > cutoff:
                seen.add(h)
    except Exception:
        pass
    return seen


def save_seen_hashes(output_type: str, hashes: set, window_hours: int = 24):
    """保存已见 hash，自动清理过期记录"""
    seen_file = OUTPUT_DIR / output_type / "seen_hashes.json"
    seen_file.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if seen_file.exists():
        try:
            existing = json.loads(seen_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    cutoff = datetime.now() - timedelta(hours=window_hours)
    cleaned = {h: ts for h, ts in existing.items()
               if datetime.fromisoformat(ts) > cutoff}
    now_str = datetime.now().isoformat()
    for h in hashes:
        cleaned[h] = now_str
    seen_file.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")


def dedup_items(items: list[dict], seen_hashes: set) -> tuple[list[dict], set]:
    """去重，返回新条目列表和本批次的 hash 集合"""
    new_items = []
    new_hashes = set()
    for item in items:
        h = item_hash(item)
        if h not in seen_hashes:
            new_items.append(item)
            new_hashes.add(h)
    return new_items, new_hashes


# ---------------------------------------------------------------
# 格式化输出
# ---------------------------------------------------------------
def format_item_markdown(item: dict, index: int = 0) -> str:
    """将单条热点格式化为 Markdown"""
    title = item.get("title", "无标题")
    source = item.get("source", "未知来源")
    url = item.get("url", "")
    desc = item.get("desc", "")
    hot = item.get("hot", "")
    matched = item.get("matched_keywords", [])

    lines = [f"**{index}. {title}**"]
    if url:
        lines[0] = f"**{index}. [{title}]({url})**"
    lines.append(f"来源：{source}" + (f" | 热度：{hot}" if hot else ""))
    if desc:
        lines.append(f"> {desc[:100]}{'...' if len(desc) > 100 else ''}")
    if matched and matched != ["*"]:
        lines.append(f"🏷️ 命中关键词：{', '.join(matched)}")
    return "\n".join(lines)


def format_digest_markdown(items: list[dict], title: str, mode: str) -> str:
    """生成简报 Markdown 全文"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    mode_label = {"current": "当前热榜", "incremental": "新增热点", "digest": "每日简报"}.get(mode, mode)
    
    lines = [
        f"# 📋 {title}",
        f"**{mode_label}** | 生成时间：{now} | 共 {len(items)} 条",
        "",
        "---",
        "",
    ]
    
    # 按来源平台分组
    by_source = {}
    for item in items:
        src = item.get("source", "其他")
        by_source.setdefault(src, []).append(item)
    
    for source, source_items in by_source.items():
        lines.append(f"## {source}")
        for i, item in enumerate(source_items, 1):
            lines.append(format_item_markdown(item, i))
            lines.append("")
    
    lines += ["---", f"_由 work-collect-v2 自动生成 | {now}_"]
    return "\n".join(lines)


# ---------------------------------------------------------------
# 存档
# ---------------------------------------------------------------
def save_output(output_type: str, filename: str, content_md: str, content_json: list):
    """保存 Markdown + JSON 双格式留档"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = OUTPUT_DIR / output_type / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    
    md_file = out_dir / f"{filename}.md"
    md_file.write_text(content_md, encoding="utf-8")
    
    json_file = out_dir / f"{filename}.json"
    json_file.write_text(
        json.dumps({"generated_at": datetime.now().isoformat(), "items": content_json},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return md_file, json_file


def write_log(message: str, level: str = "INFO"):
    """写入日志"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{date_str}.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{level}] {message}\n")


# ---------------------------------------------------------------
# 飞书推送
# ---------------------------------------------------------------
def push_feishu(webhook: str, content: str, title: str = "信息简报"):
    """推送到飞书（仅当 notify.yaml 中 webhook 非空时调用）"""
    if not webhook:
        return False
    try:
        import urllib.request
        payload = json.dumps({
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title}},
                "elements": [{"tag": "markdown", "content": content[:4000]}]
            }
        }).encode("utf-8")
        req = urllib.request.Request(
            webhook,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        write_log(f"飞书推送失败: {e}", "ERROR")
        return False
