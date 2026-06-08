# 记忆梦境引擎 v3.0

让你的 AI Agent「记住过去、优化现在、产出未来」

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)](engine.py)
[![Tests](https://img.shields.io/badge/tests-8%2F8%20passed-brightgreen.svg)](tests/)
[![Gitee](https://img.shields.io/badge/Gitee-%E6%98%9F%E6%98%9F%20%E6%88%91-red.svg)](https://gitee.com/savantcat/memory-dream-engine)

---

## 一句话

你的 AI Agent 聊完就忘？给它装一个「做梦」系统——每 3 小时自动采集记忆、评分、清理、发芽。零 LLM 成本，即装即用。

## 核心能力

- **五阶段流水线**：采集 → 评分 → 写入 → 优化 → 发芽。像人类的睡眠周期一样运作
- **艾宾浩斯衰减**：30 天半衰期，高频访问自动增强，低强度自动归档
- **零 LLM 事实提取**：中英文正则匹配，零 token 成本提取关键信息
- **SQLite 持久化**：双时序事实管理，完整审计追踪
- **Token 节省追踪**：每次运行量化节省的 token 消耗

## 工作原理

```
用户交互 (决策/纠偏/工具/灵感)
    ↓
SignalCollector 采集信号 (每180分钟)
    ↓
SignalScorer 三维评分 (≥70分写入，≥90分替换)
    ↓
MemoryWriter 写入长期记忆 (声明式，≤80字/条)
    ↓
MemoryOptimizer 深度清理 (每3次触发，去重/过期/压缩)
    ↓
SproutDetector 内容发芽 (3条→星球帖，5条→公众号)
```

## 快速开始

```bash
# 1. 安装
pip install -r requirements.txt

# 2. 配置 (编辑 .env)
# SESSION_SEARCH_FN=...
# MEMORY_FN=...

# 3. 运行引擎
python engine.py ingest
python engine.py dream

# 4. 设置 Cron (每180分钟)
# 详见 部署指南.md
```

完整安装步骤和使用说明请查看 [部署指南.md](部署指南.md)。

## Hermes Agent 集成

本引擎专为 Hermes Agent 设计，也适配任何支持 `session_search` 和 `memory` 工具的系统。

Hermes 用户可以直接安装 Skill 文件：
1. 下载 [SKILL.md](SKILL.md) 到 `~/.hermes/skills/memory-dream-engine/`
2. 添加 Cron 配置（每180分钟运行）
3. 首次交互式运行后执行阶段3+4的memory写入

## 与溯忆(Suyi)对比

| 特性 | 梦境引擎 | 溯忆 |
|------|---------|------|
| 艾宾浩斯衰减 | ✅ | ✅ |
| 零LLM提取 | ✅ 中英文 | ✅ 英文 |
| 五阶段流水线 | ✅ 独有 | ❌ |
| 信号采集 | ✅ 独有 | ❌ |
| 内容发芽 | ✅ 独有 | ❌ |
| Token追踪 | ✅ 独有 | ❌ |

## 项目结构

```
engine.py       ~800行，核心引擎
cli.py          命令行入口 + 适配器示例
SKILL.md        Hermes Agent 集成指南
部署指南.md     两种部署方式 + FAQ
tests/          8个单元测试
```

## 开源许可

MIT License — 自由使用、修改、分发。

## 作者

合尘猫 x 小甜甜 | 2026年6月

---

> 记忆不是越多越好，而是越「活」越好。
