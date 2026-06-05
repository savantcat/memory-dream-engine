
"""
记忆梦境引擎 v2.0 — 核心流水线
五阶段：采集 → 评分 → 写入 → 优化 → 发芽
"""

import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from difflib import SequenceMatcher


SIGNAL_CONFIG = {
    "决策信号": {"queries": ["决定 选择 建仓 换 停 改"], "limit": 3, "weight": 1.0},
    "纠偏信号": {"queries": ["不对 错了 不是 应该 注意"], "limit": 3, "weight": 1.2},
    "工具信号": {"queries": ["安装 配置 创建 API Key"], "limit": 2, "weight": 0.8},
    "灵感信号": {"queries": ["想法 可以做 写一篇 试试"], "limit": 2, "weight": 0.9},
}


@dataclass
class Signal:
    source: str
    session_id: str = ""
    content: str = ""
    timestamp: str = ""
    match_context: str = ""


@dataclass
class ScoredSignal:
    signal: Signal
    durability: float = 0.0
    correction: float = 0.0
    reusability: float = 0.0
    total: float = 0.0
    action: str = ""


@dataclass
class Sprout:
    topic: str
    memory_count: int
    action_type: str
    suggestion: str


@dataclass
class OptimizationReport:
    dedup_count: int = 0
    expired_count: int = 0
    compressed_count: int = 0
    merged_items: list = field(default_factory=list)


@dataclass
class DreamReport:
    timestamp: str
    signals_collected: int = 0
    signals_scored: list = field(default_factory=list)
    memory_writes: list = field(default_factory=list)
    optimization: Optional[OptimizationReport] = None
    sprouts: list = field(default_factory=list)
    run_count: int = 0

    def summary(self) -> str:
        lines = [f"## 记忆梦境引擎 — {self.timestamp}"]
        passed = len([s for s in self.signals_scored if s.action != "skip"])
        lines.append(f"采集 {self.signals_collected} 条 -> 评分通过 {passed} 条 -> 写入 {len(self.memory_writes)} 条")
        if self.optimization:
            opt = self.optimization
            parts = []
            if opt.dedup_count: parts.append(f"去重{opt.dedup_count}对")
            if opt.expired_count: parts.append(f"过期{opt.expired_count}条")
            if opt.compressed_count: parts.append(f"压缩{opt.compressed_count}条")
            if parts: lines.append(f"优化：{'，'.join(parts)}")
        if self.sprouts:
            lines.append(f"发芽 {len(self.sprouts)} 个：")
            for s in self.sprouts:
                lines.append(f"  - [{s.action_type}] {s.suggestion}")
        return "\n".join(lines)


class SignalCollector:
    def __init__(self, session_search_fn):
        self.search = session_search_fn

    def collect(self, days_back: int = 2) -> list[Signal]:
        all_signals = []
        for signal_type, config in SIGNAL_CONFIG.items():
            for query in config["queries"]:
                results = self.search(query=query, limit=config["limit"], sort="newest")
                for r in (results or []):
                    all_signals.append(Signal(
                        source=signal_type,
                        session_id=r.get("session_id", ""),
                        content=r.get("content", ""),
                        timestamp=r.get("timestamp", ""),
                        match_context=r.get("match_context", ""),
                    ))
        return all_signals[:10]


class SignalScorer:
    DURABLE_KW = ["规则", "原则", "偏好", "铁律", "不再", "以后", "配置", "环境", "API", "路径", "工作流", "止损", "仓位", "策略", "流程", "方法"]
    CORRECTION_KW = ["不对", "不是", "错了", "不要", "别", "禁止", "不能", "不允许", "纠正", "错误", "改", "换", "停"]
    REUSABLE_KW = ["方法", "步骤", "模板", "脚本", "skill", "怎么做", "如何", "方案", "流程"]

    def score(self, signal: Signal) -> ScoredSignal:
        text = signal.content + signal.match_context
        durability = min(100, 40 + sum(20 for kw in self.DURABLE_KW if kw in text) + (15 if signal.source == "决策信号" else 0))
        correction = min(100, 30 + sum(25 for kw in self.CORRECTION_KW if kw in text) + (20 if signal.source == "纠偏信号" else 0))
        reusability = min(100, 30 + sum(25 for kw in self.REUSABLE_KW if kw in text) + (15 if signal.source == "工具信号" else 0))
        # 按信号类型动态调整权重：优先维度占比70%
        weights = {"决策信号": (0.7, 0.2, 0.1), "纠偏信号": (0.2, 0.7, 0.1),
                   "工具信号": (0.2, 0.1, 0.7), "灵感信号": (0.4, 0.2, 0.4)}
        w = weights.get(signal.source, (0.5, 0.3, 0.2))
        total = durability * w[0] + correction * w[1] + reusability * w[2]
        action = "replace" if total >= 90 else ("write" if total >= 70 else "skip")
        return ScoredSignal(signal=signal, durability=durability, correction=correction, reusability=reusability, total=total, action=action)


class MemoryWriter:
    MAX_LEN = 80

    def __init__(self, memory_fn, get_usage_fn):
        self.memory = memory_fn
        self.get_usage = get_usage_fn

    def format_entry(self, scored: ScoredSignal) -> str:
        text = re.sub(r'^(需要|必须|应该|要|请|注意)\s*', '', scored.signal.content.strip())
        return text[:self.MAX_LEN - 3] + "..." if len(text) > self.MAX_LEN else text

    def write(self, scored: ScoredSignal, existing: list[str] = None) -> dict:
        entry = self.format_entry(scored)
        if scored.action == "replace":
            target = self._find_similar(entry, existing or [])
            return self.memory(action="replace", target="memory", content=entry, old_text=target)
        elif scored.action == "write":
            if existing:
                for mem in existing:
                    if SequenceMatcher(None, entry, mem).ratio() > 0.7:
                        return {"status": "skipped", "reason": "duplicate"}
            return self.memory(action="add", target="memory", content=entry)
        return {"status": "skipped", "reason": "low_score"}

    def _find_similar(self, text: str, memories: list[str]) -> str:
        best = ("", 0)
        for mem in memories:
            sim = SequenceMatcher(None, text, mem).ratio()
            if sim > best[1]: best = (mem, sim)
        return best[0] if best[1] > 0.4 else ""


class MemoryOptimizer:
    DEDUP = 0.7
    EXPIRE_DAYS = 30
    COMPRESS = 85

    def __init__(self, memory_fn, get_usage_fn):
        self.memory = memory_fn
        self.get_usage = get_usage_fn

    def optimize(self, memories: list[dict], run_count: int) -> OptimizationReport:
        report = OptimizationReport()
        if run_count % 3 != 0: return report
        report.merged_items = self._dedup(memories)
        report.dedup_count = len(report.merged_items)
        report.expired_count = self._expire(memories)
        used, total = self.get_usage()
        if total > 0 and (used / total * 100) > self.COMPRESS:
            report.compressed_count = self._compress(memories)
        return report

    def _dedup(self, memories): 
        merged, visited = [], set()
        for i, m1 in enumerate(memories):
            if i in visited: continue
            for j, m2 in enumerate(memories):
                if j <= i or j in visited: continue
                if SequenceMatcher(None, m1["content"], m2["content"]).ratio() > self.DEDUP:
                    merged.append((m1["content"], m2["content"])); visited.add(j)
        return merged

    def _expire(self, memories):
        cutoff = datetime.now() - timedelta(days=self.EXPIRE_DAYS)
        tech_kw = ["API", "path", "路径", "端口", "版本", "URL", "命令"]
        return sum(1 for m in memories if any(kw in m["content"] for kw in tech_kw))

    def _compress(self, memories):
        shorts = [m for m in memories if len(m["content"]) < 20]
        if len(shorts) >= 3:
            combined = "§".join([s["content"] for s in shorts[:5]])
            self.memory(action="add", target="memory", content=combined)
            return len(shorts[:5])
        return 0


class SproutDetector:
    def detect(self, memories: list[dict]) -> list[Sprout]:
        clusters = self._cluster(memories)
        sprouts = []
        for topic, items in clusters.items():
            n = len(items)
            if n >= 5: sprouts.append(Sprout(topic, n, "公众号文章", f"「{topic}」已积累{n}条记忆，够一篇公众号文章"))
            elif n >= 3: sprouts.append(Sprout(topic, n, "星球帖", f"「{topic}」已积累{n}条记忆，可以写星球洞察帖"))
        return sprouts

    def _cluster(self, memories):
        clusters = {}
        topics = {"主动做事": ["主动", "等指令"], "投资": ["持仓", "A股"], "内容": ["公众号", "文章"], "工具": ["配置", "API"]}
        for m in memories:
            for topic, kws in topics.items():
                if any(kw in m["content"] for kw in kws):
                    clusters.setdefault(topic, []).append(m); break
        return clusters


class DreamEngine:
    def __init__(self, session_search_fn, memory_fn, get_usage_fn):
        self.collector = SignalCollector(session_search_fn)
        self.scorer = SignalScorer()
        self.writer = MemoryWriter(memory_fn, get_usage_fn)
        self.optimizer = MemoryOptimizer(memory_fn, get_usage_fn)
        self.detector = SproutDetector()
        self.run_count = 0

    def dream(self, days_back: int = 2, existing_memories: list[dict] = None) -> DreamReport:
        self.run_count += 1
        report = DreamReport(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"), run_count=self.run_count)
        signals = self.collector.collect(days_back)
        report.signals_collected = len(signals)
        for sig in signals: report.signals_scored.append(self.scorer.score(sig))
        existing_texts = [m["content"] for m in (existing_memories or [])]
        for scored in report.signals_scored:
            if scored.action != "skip":
                report.memory_writes.append(self.writer.write(scored, existing_texts))
        if self.run_count % 3 == 0:
            report.optimization = self.optimizer.optimize(existing_memories or [], self.run_count)
        report.sprouts = self.detector.detect(existing_memories or [])
        return report



def report_to_dict(report: DreamReport) -> dict:
    """将 DreamReport 导出为 JSON 兼容的字典"""
    return {
        "timestamp": report.timestamp,
        "run_count": report.run_count,
        "signals_collected": report.signals_collected,
        "passed_signals": [
            {
                "source": s.signal.source,
                "content": s.signal.content[:100],
                "scores": {"durability": s.durability, "correction": s.correction,
                          "reusability": s.reusability, "total": round(s.total, 1)},
                "action": s.action,
            }
            for s in report.signals_scored if s.action != "skip"
        ],
        "writes": len(report.memory_writes),
        "optimization": {
            "dedup": report.optimization.dedup_count if report.optimization else 0,
            "expired": report.optimization.expired_count if report.optimization else 0,
            "compressed": report.optimization.compressed_count if report.optimization else 0,
        },
        "sprouts": [
            {"topic": s.topic, "type": s.action_type, "count": s.memory_count, "suggestion": s.suggestion}
            for s in report.sprouts
        ],
    }

if __name__ == "__main__":
    print("记忆梦境引擎 v2.0 核心模块已就绪")
    print("  SignalCollector / SignalScorer / MemoryWriter / MemoryOptimizer / SproutDetector")
    print("  DreamEngine.dream() -> DreamReport")
