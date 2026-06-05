#!/usr/bin/env python3
"""记忆梦境引擎 CLI — 命令行入口"""

import json, sys, os
from engine import DreamEngine, report_to_dict

def mock_session_search(query, limit, sort):
    """适配器示例：实际使用时替换为真实的session_search调用"""
    print(f"  [适配器] session_search(query='{query[:30]}...', limit={limit})")
    return []

def mock_memory(action, target, content, old_text=None):
    """适配器示例：实际使用时替换为真实的memory调用"""
    print(f"  [适配器] memory(action='{action}', target='{target}', content='{content[:30]}...')")
    return {"status": "ok"}

def mock_get_usage():
    """适配器示例"""
    return (2000, 2200)

def main():
    print("=" * 50)
    print("  记忆梦境引擎 v2.0")
    print("=" * 50)

    engine = DreamEngine(
        session_search_fn=mock_session_search,
        memory_fn=mock_memory,
        get_usage_fn=mock_get_usage,
    )

    # 模拟已有记忆
    existing = [
        {"content": "用户偏好：希望AI主动做事而非等指令", "timestamp": "2026-06-04"},
        {"content": "持仓：润泽2500@88.855、金域8500@23.34", "timestamp": "2026-06-05"},
    ]

    report = engine.dream(days_back=2, existing_memories=existing)
    print(report.summary())

    # 输出JSON
    json_path = os.path.join(os.path.dirname(__file__), "dream_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_to_dict(report), f, ensure_ascii=False, indent=2)
    print(f"
报告已保存: {json_path}")

if __name__ == "__main__":
    main()
