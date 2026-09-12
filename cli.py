#!/usr/bin/env python3
"""记忆梦境引擎 CLI — 命令行入口 / 适配器示例

引擎本身不绑定任何 Agent 框架，通过三个适配器函数接入：
    session_search_fn(query, limit, sort) -> 搜索结果
    memory_fn(action, target, content, old_text=None) -> 写入/替换结果
    get_usage_fn() -> (已用字符数, 总字符数)

把下面三个 mock_* 换成你自己框架的真实调用即可。
"""
import json
import os
import sys

from engine import DreamEngine, report_to_dict


def mock_session_search(query, limit, sort):
    """适配器示例：替换为真实的 session_search 调用"""
    print("  [适配器] session_search(query='%s...', limit=%s)" % (query[:30], limit))
    return []


def mock_memory(action, target, content, old_text=None):
    """适配器示例：替换为真实的 memory 调用"""
    print("  [适配器] memory(action='%s', target='%s', content='%s...')"
          % (action, target, content[:30]))
    return {"status": "ok"}


def mock_get_usage():
    """适配器示例：返回 (已用, 上限) 字符数"""
    return (2000, 2200)


def main():
    print("=" * 52)
    print("  记忆梦境引擎 v3.0 — CLI 演示")
    print("=" * 52)

    engine = DreamEngine(
        session_search_fn=mock_session_search,
        memory_fn=mock_memory,
        get_usage_fn=mock_get_usage,
    )

    # 模拟"已有记忆"——仅用于演示去重逻辑，示例内容为虚构
    existing = [
        {"content": "用户偏好：希望 AI 主动做事而非等指令", "timestamp": "2026-06-04"},
        {"content": "示例记忆：公众号文章控制在 1500–2500 字", "timestamp": "2026-06-05"},
    ]

    report = engine.dream(days_back=2, existing_memories=existing)
    print(report.summary())

    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dream_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_to_dict(report), f, ensure_ascii=False, indent=2)
    print("\n报告已保存: %s" % json_path)


if __name__ == "__main__":
    main()
