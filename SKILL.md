---
name: memory-dream-engine
description: >-
  记忆梦境引擎 — 让你的AI拥有持续记忆、自动清理、内容发芽能力。
  五阶段流水线：采集→评分→写入→优化→发芽。
  engine.py 为核心Python实现，SKILL.md 为Hermes Agent集成指南。
version: 2.1
author: 合尘猫 × 小甜甜
license: MIT
tags:
  - memory
  - dreaming
  - knowledge-management
  - agent
  - second-brain
  - python
---

# 🌙 记忆梦境引擎 v2.1

> 让你的AI「记住过去、优化现在、产出未来」

## 项目组成

| 文件 | 用途 |
|:-----|:-----|
| `engine.py` | **核心引擎** — 五阶段流水线Python实现（可独立运行） |
| `cli.py` | 命令行入口 + 适配器示例 |
| `SKILL.md` | 本文件 — Hermes Agent 集成指南 |
| `README.md` | 项目说明 + 快速开始 |

## 两种使用方式

### 方式A：作为 Python 库（推荐）

```python
from engine import DreamEngine

engine = DreamEngine(
    session_search_fn=your_search,
    memory_fn=your_memory,
    get_usage_fn=your_usage,
)

report = engine.dream(days_back=2, existing_memories=[...])
print(report.summary())
```

需要实现三个适配器函数（见 README.md）。

### 方式B：作为 Hermes Agent Skill

本 SKILL.md 在 Hermes Agent 中作为技能加载。Agent 使用内置的 `session_search` + `memory` 工具，按五阶段流水线指令执行。

Cron 配置（每3小时）：
```yaml
schedule: every 180m
skills: ["memory-dream-engine"]
prompt: 执行记忆梦境引擎五阶段流程。无新发现输出 [SILENT]。
```

## 架构

```
┌─────────────────────────────────────────────┐
│              DreamEngine                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Collector │→ │ Scorer   │→ │ Writer   │  │
│  │ 采集信号  │  │ 三维评分  │  │ 写入记忆  │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│         ↓                          ↓        │
│  ┌──────────┐               ┌──────────┐   │
│  │Optimizer │←──────────────│ Detector │   │
│  │ 去重/过期 │  每3次触发    │ 发芽建议  │   │
│  └──────────┘               └──────────┘   │
└─────────────────────────────────────────────┘
```

## 评分算法

| 维度 | 权重 | 评分逻辑 |
|:-----|:----:|:---------|
| 持久价值 | 50% | 含"规则/配置/API/工作流"关键词 +15分/个 |
| 纠偏价值 | 30% | 含"不对/不要/禁止"关键词 +20分/个 |
| 可复用 | 20% | 含"方法/模板/脚本/skill"关键词 +20分/个 |

≥90分 → replace | ≥70分 → write | <70分 → skip

## 发芽阈值

| 积累量 | 触发 |
|:------:|:-----|
| 3+ 条同主题记忆 | → 建议写星球洞察帖 |
| 5+ 条同主题记忆 | → 建议写公众号文章 |
| 3+ 次同类工作流 | → 建议创建skill |

## 设计哲学

记忆不是越多越好，而是越「活」越好。
五阶段流水线 = AI的「睡眠周期」：浅睡(采集) → 深睡(评分写入) → REM(发芽产出)

## 适配

引擎核心 (`engine.py`) 不依赖任何特定Agent框架。三个函数接口连接任何系统。

## 作者

合尘猫 × 小甜甜（AI分身）
2026年6月

## License

MIT — 自由使用、修改、分发。
