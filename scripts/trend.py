"""
trend.py - 热点追踪主脚本
聚合多平台热榜 + 关键词过滤 + X/YouTube + 留档推送

使用方式：
  python scripts/trend.py --mode current      # 当前热榜快照
  python scripts/trend.py --mode incremental  # 仅新增热点
  python scripts/trend.py --mode digest       # 每日汇总简报
"""
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# 添加 sources 到路径
sys.path.insert(0, str(Path(__file__).parent))

from sources.dailyhot import fetch_all_platforms, check_connection
from sources.nitter import fetch_all as fetch_x
from sources.youtube import fetch_all as fetch_youtube
from sources.utils import (
    load_keywords, load_sources_config, load_notify_config,
    filter_items_by_keywords, dedup_items,
    load_seen_hashes, save_seen_hashes,
    format_digest_markdown, save_output,
    push_feishu, write_log
)


def run(mode: str = "incremental"):
    """
    执行热点追踪
    
    Args:
        mode: current / incremental / digest
    """
    print(f"\n{'='*50}")
    print(f"[热点追踪] 开始执行，模式：{mode}")
    print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    config = load_sources_config()
    keywords = load_keywords()
    notify_config = load_notify_config()
    
    trend_config = config.get("trend", {})
    top_n = trend_config.get("top_n", 20)
    dedup_hours = trend_config.get("dedup_window_hours", 24)

    # -------------------------------------------------------
    # 1. 国内平台（DailyHot）
    # -------------------------------------------------------
    all_items = []
    dh_config = config.get("dailyhot", {})
    
    if dh_config.get("enabled", True):
        base_url = dh_config.get("base_url", "http://localhost:6688")
        
        if not check_connection(base_url):
            print(f"[DailyHot] ⚠️  无法连接到 {base_url}")
            print(f"[DailyHot] 请先启动 DailyHot：cd docker && docker compose up -d")
            write_log(f"DailyHot 连接失败: {base_url}", "WARN")
        else:
            platforms = dh_config.get("platforms", ["weibo", "zhihu", "bilibili"])
            items = fetch_all_platforms(base_url, platforms, top_n)
            all_items.extend(items)
            print(f"\n[DailyHot] 共获取 {len(items)} 条热点")

    # -------------------------------------------------------
    # 2. X/Twitter（Nitter RSS）
    # -------------------------------------------------------
    x_config = config.get("x_twitter", {})
    if x_config.get("accounts") or x_config.get("keywords"):
        x_items = fetch_x(x_config, top_n=10)
        all_items.extend(x_items)
        print(f"\n[X/Twitter] 共获取 {len(x_items)} 条")

    # -------------------------------------------------------
    # 3. YouTube
    # -------------------------------------------------------
    yt_config = config.get("youtube", {})
    if yt_config.get("channels"):
        yt_items = fetch_youtube(yt_config, top_n=5)
        all_items.extend(yt_items)
        print(f"\n[YouTube] 共获取 {len(yt_items)} 条")

    print(f"\n[总计] 原始条目：{len(all_items)} 条")

    if not all_items:
        print("\n[热点追踪] 未获取到任何数据，请检查网络和配置")
        return

    # -------------------------------------------------------
    # 4. 关键词过滤
    # -------------------------------------------------------
    if keywords:
        filtered = filter_items_by_keywords(all_items, keywords)
        print(f"[过滤] 关键词命中：{len(filtered)} 条（过滤掉 {len(all_items)-len(filtered)} 条）")
    else:
        filtered = all_items
        print("[过滤] 未配置关键词，返回全部条目")

    # -------------------------------------------------------
    # 5. 去重（incremental 模式才去重）
    # -------------------------------------------------------
    new_hashes = set()
    if mode == "incremental":
        seen = load_seen_hashes("trend", dedup_hours)
        filtered, new_hashes = dedup_items(filtered, seen)
        print(f"[去重] 新增条目：{len(filtered)} 条")
    else:
        # current / digest 模式不去重，但也更新 seen hashes
        from sources.utils import item_hash
        new_hashes = {item_hash(item) for item in filtered}

    if not filtered:
        print("\n[热点追踪] 无新增热点（自上次执行以来）")
        if mode == "incremental":
            print("提示：使用 --mode current 查看当前完整热榜")
        return

    # -------------------------------------------------------
    # 6. 生成输出
    # -------------------------------------------------------
    title_map = {
        "current": "当前热榜快照",
        "incremental": "新增热点",
        "digest": "每日信息简报",
    }
    title = title_map.get(mode, "热点追踪")
    
    content_md = format_digest_markdown(filtered, title, mode)
    
    # -------------------------------------------------------
    # 7. 留档
    # -------------------------------------------------------
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"trend_{mode}_{timestamp}"
    md_file, json_file = save_output("trend", filename, content_md, filtered)
    print(f"\n[留档] Markdown: {md_file}")
    print(f"[留档] JSON:     {json_file}")

    # -------------------------------------------------------
    # 8. 更新去重记录
    # -------------------------------------------------------
    save_seen_hashes("trend", new_hashes, dedup_hours)

    # -------------------------------------------------------
    # 9. 推送（仅当飞书 Webhook 直接配置时）
    # -------------------------------------------------------
    feishu_config = notify_config.get("feishu", {})
    webhook = feishu_config.get("webhook", "")
    if webhook and feishu_config.get("enabled", False):
        success = push_feishu(webhook, content_md[:4000], title)
        print(f"[飞书] 推送{'成功' if success else '失败'}")
    else:
        print("[飞书] 走 OpenClaw 绑定渠道推送（无需额外配置）")

    # -------------------------------------------------------
    # 10. 输出到终端（供 OpenClaw 读取）
    # -------------------------------------------------------
    print(f"\n{'='*50}")
    print(content_md)
    print(f"{'='*50}\n")
    
    write_log(f"热点追踪完成，模式={mode}，条目={len(filtered)}", "INFO")
    return content_md


def main():
    parser = argparse.ArgumentParser(description="work-collect-v2 热点追踪")
    parser.add_argument(
        "--mode",
        choices=["current", "incremental", "digest"],
        default="incremental",
        help="追踪模式：current=当前快照 incremental=新增热点 digest=每日汇总"
    )
    args = parser.parse_args()
    run(args.mode)


if __name__ == "__main__":
    main()
