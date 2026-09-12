# 🌙 记忆梦境引擎 · Memory Dream Engine

### 你的 AI 聊完就忘，不是它笨 —— 是它从来不做梦。

一个可插拔的「AI 睡眠系统」：**采集 → 评分 → 写入 → 优化 → 发芽**，每 3 小时自动跑一轮。
零 LLM 成本、纯标准库、~800 行 Python、8/8 单元测试通过。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-green.svg)](engine.py)
[![Tests](https://img.shields.io/badge/tests-8%2F8%20passed-brightgreen.svg)](tests/)
[![Deps](https://img.shields.io/badge/dependencies-zero-success.svg)](requirements.txt)

---

## 🤔 你大概率遇到过这三种情况

| 症状 | 真实原因 |
|---|---|
| 「我上周明确说过不要这样，你怎么又忘了？」 | 记忆只在**当次对话**里，从不沉淀 |
| memory 越写越满，快撑爆上限，但**不敢删** | 没有衰减机制，不知道哪条该淘汰 |
| 攒了一堆零散结论，**没人把它们变成产出** | 采集和产出之间断了一环 |

梦境引擎就是补这三环的。

## 🧠 它怎么工作 —— 像人一样睡觉

```
        ┌─ 浅睡 ── SignalCollector   采集四维信号（决策 / 纠偏 / 工具 / 灵感）
        │
一轮 ───┼─ 深睡 ── SignalScorer      三维动态评分（按信号类型自适应调权）
(180min)│           MemoryWriter      去重 + 合并 + 替换，声明式写入
        │
        └─ REM ── SproutDetector    3 条 → 星球帖   /   5 条 → 公众号文章
                          ▲
                    MemoryOptimizer  每 3 轮深度清理（去重 / 过期 / 压缩）
```

## ⚡ 四个「别人没有」的点

| 能力 | 说明 |
|---|---|
| **零 LLM 事实提取** | 纯正则，中英文通吃，提取一万条也不花一分钱 token |
| **艾宾浩斯衰减** | 30 天半衰期，高频访问自动增强，低强度自动归档 —— 记忆会自己「瘦身」 |
| **三维动态评分** | 决策信号看持久度、纠偏信号看纠偏度、工具信号看复用度，不是一把尺子量到底 |
| **内容发芽** | 同一批记忆攒够了，自动提示「这批可以出一篇公众号了」 |

## 🆚 和溯忆(Suyi)比

溯忆是**被动存储**，梦境引擎是**主动生长**：

| 特性 | 梦境引擎 | 溯忆 |
|---|:---:|:---:|
| 艾宾浩斯衰减 | ✅ | ✅ |
| 零 LLM 提取 | ✅ 中英文 | ⚠️ 仅英文 |
| 五阶段流水线 | ✅ | ❌ |
| 四维信号采集 | ✅ | ❌ |
| 三维动态评分 | ✅ | ❌ |
| 内容发芽 | ✅ | ❌ |
| Token 节省追踪 | ✅ | ❌ |
| 三方依赖 | **零** | 需向量库 |

## 🚀 60 秒跑起来

```bash
git clone https://gitee.com/savantcat/memory-dream-engine.git
cd memory-dream-engine

# 依赖为零；只有跑测试才需要 pytest
python -m pip install -r requirements.txt

# 看演示（用内置 mock 适配器，不需要接任何框架）
python cli.py
```

想看核心能力，直接跑引擎自带的 v3 演示：

```bash
python engine.py
```

## 🔌 接入你自己的 Agent

引擎**不绑定任何框架**，只需实现三个适配器函数：

```python
from engine import DreamEngine

def my_session_search(query, limit, sort):
    """换成你框架的搜索接口"""
    return [{"content": "...", "role": "user"}]

def my_memory(action, target, content, old_text=None):
    """换成你框架的记忆写入接口"""
    return {"status": "ok"}

def my_get_usage():
    """返回 (已用字符数, 总字符数)"""
    return (1500, 2200)

engine = DreamEngine(
    session_search_fn=my_session_search,
    memory_fn=my_memory,
    get_usage_fn=my_get_usage,
)

report = engine.dream(days_back=2, existing_memories=[...])
print(report.summary())
```

> ⚠️ **文档澄清**：早期版本的 README 里出现过「编辑 `.env` 配置 `SESSION_SEARCH_FN` / `MEMORY_FN`」的说明，
> **那是错的 —— 引擎从不读取任何环境变量**。接入方式只有上面这一种：传 Python 函数。

## ⏰ 定时运行（Hermes Agent）

```yaml
schedule: every 180m
skills: ["memory-dream-engine"]
prompt: 执行记忆梦境引擎五阶段流程。无新发现输出 [SILENT]。
```

## ⚠️ 必读：Cron 环境写不了 Memory（最大的运维坑）

多数 Agent 框架的 cron 子进程**没有 memory 工具权限**，会导致阶段 3（写入）和阶段 4（优化）**静默失败** ——
引擎照常采集和评分，但 ≥70 分的条目会持续积压。

**症状**：报告反复出现「阶段3：写入 — 受阻」，同一批高分记忆连着几轮都没写进去。

**做法**：每跑 3 轮 cron，安排一次**交互式会话**手动补写阶段 3+4；memory 占用到 95% 时立即执行清理。

## 📁 项目结构

```
engine.py                  ~800 行核心引擎（五阶段 + 衰减 + 零LLM提取 + SQLite）
cli.py                     命令行入口 + 三个适配器示例
nightbrain_consolidate.py  可选：夜间知识库巩固（扫描新知/标记陈旧/更新索引）
SKILL.md                   Hermes Agent 集成指南
部署指南.md                 两种部署方式 + FAQ
tests/                     8 个单元测试（pytest）
```

## 🧪 测试

```bash
python -m pip install pytest
python -m pytest tests/ -q      # 8 passed
```

> 测试为 pytest 风格（裸 assert + `setup` 方法），**不兼容 `unittest discover`**，请用 pytest 运行。

## 📄 License

MIT — 自由使用、修改、分发。

## 👤 作者

**合尘猫** · 一个人 + 一个 AI 分身的 AI 落地实践 —— 知识库 · AI 客服合规 · 内容自动化。

- 🏠 更多作品与实战记录：<https://savantcat.cn>
- 🐙 全部开源仓库：<https://gitee.com/savantcat>

如果这个引擎帮你的 AI 真正"记住"了什么，给个 ⭐ 就是最好的反馈。

---

> 记忆不是越多越好，而是越「活」越好。
