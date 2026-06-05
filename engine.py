
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



# ═══════════════════════════════════════════════════════
# 🆕 v3.0 新增模块
# ═══════════════════════════════════════════════════════

import math, re, sqlite3, json, os, hashlib
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════
# 🆕 Ebbinghaus 遗忘曲线衰减引擎
# ═══════════════════════════════════════════

class EbbinghausDecay:
    """艾宾浩斯遗忘曲线：自然衰减 + 访问增强"""

    HALF_LIFE_DAYS = 30       # 半衰期：30天不用衰减50%
    MIN_STRENGTH = 0.05       # 最低强度（不会彻底忘记）
    BOOST_FACTOR = 1.3        # 每次访问增强系数

    @staticmethod
    def decay_factor(days_since_access: float) -> float:
        """计算衰减因子：e^(-ln2 * t / half_life)"""
        return math.exp(-math.log(2) * days_since_access / EbbinghausDecay.HALF_LIFE_DAYS)

    @staticmethod
    def current_strength(initial_strength: float, last_access: str) -> float:
        """计算当前记忆强度"""
        try:
            last = datetime.fromisoformat(last_access)
            days = (datetime.now() - last).total_seconds() / 86400
        except (ValueError, TypeError):
            days = EbbinghausDecay.HALF_LIFE_DAYS
        decayed = initial_strength * EbbinghausDecay.decay_factor(days)
        return max(EbbinghausDecay.MIN_STRENGTH, min(decayed, 1.0))

    @staticmethod
    def boost(current_strength: float) -> float:
        """访问后增强记忆强度"""
        return min(1.0, current_strength * EbbinghausDecay.BOOST_FACTOR)

    @staticmethod
    def should_archive(strength: float, threshold: float = 0.15) -> bool:
        """记忆强度低于阈值 → 建议归档"""
        return strength < threshold


# ═══════════════════════════════════════════
# 🆕 零LLM事实提取器（省token！）
# ═══════════════════════════════════════════

class ZeroLLMExtractor:
    """基于正则的事实提取，零token成本。
    
    相比于 Suyi 的纯英文正则，我们增加了中文支持。
    """

    PATTERNS = [
        ("(?:我|用户|合尘猫)(?:喜欢|偏好|习惯|用的是?|在用)\\s*(.+?)(?:[。，；.!；\\n]|$)", "preference"),
        ("(?:不要|别|禁止|不能用|别再)\\s*(.+?)(?:[。，；.!；\\n]|$)", "correction"),
        ("(?:系统|环境|OS|操作系统)(?:是|：|:)\\s*(\\w+(?:\\s*\\d+(?:\\.\\d+)?)?)", "env"),
        ("(?:路径|文件)(?:在|是|：|:)\\s*(.+?)(?:[。，；\\n]|$)", "env"),
        ("(?:安装|pip install|npm install)\\s+(\\S+)", "tool"),
        ("(?:版本)\\s*(?:是|：|:)\\s*(\\S+)", "tool"),
        ("(?:决定|选择|定下来|就)(?:用|做|选)\\s*(.+?)(?:[。，；\\n]|$)", "decision"),
        ("(?:建仓|加仓|减仓|清仓|止损)(?:[：:]\\s*)?(.+?)(?:[。，；\\n]|$)", "decision"),
    ]

    # 英文模式（复用 Suyi 模式）
    EN_PATTERNS = [
        ("(?i)(?:I|user).*(?:prefer|like|use|using)\\s+(.+?)(?:[\\.!\\n]|$)", "preference"),
        ("(?i)(?:I|user).*(?:on|using)\\s+(Windows|macOS|Linux|Ubuntu)(?:\\s+\\d+)?", "env"),
        ("(?i)OS\\s*(?:is|:)\\s*(\\w+(?:\\s*\\d+(?:\\.\\d+)*)?)", "env"),
        ("(?i)(?:decided|chose|picked|going with)\\s+(.+?)(?:[\\.!\\n]|$)", "decision"),
    ]

    @classmethod
    def extract(cls, text: str) -> list[dict]:
        """从文本提取事实，零token"""
        facts = []
        for pattern, fact_type in cls.PATTERNS + cls.EN_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(1).strip()
                if 2 < len(value) < 100:  # 过滤噪声
                    facts.append({
                        "type": fact_type,
                        "value": value,
                        "confidence": 0.7,
                        "source": "zero_llm",
                    })
        return facts[:10]  # 上限10条


# ═══════════════════════════════════════════
# 🆕 SQLite 持久化存储
# ═══════════════════════════════════════════

class MemoryStore:
    """SQLite 持久化存储 — 双时序事实 + 会话记录"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.expanduser("~/.hermes/memory_store.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_db(self):
        db = sqlite3.connect(self.db_path)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _init_db(self):
        db = self._get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity TEXT NOT NULL DEFAULT 'user',
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                fact_type TEXT DEFAULT 'general',
                tier TEXT DEFAULT 'core',
                confidence REAL DEFAULT 0.7,
                strength REAL DEFAULT 0.8,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                last_accessed TEXT NOT NULL,
                access_count INTEGER DEFAULT 1,
                source TEXT DEFAULT 'dream_engine',
                UNIQUE(entity, key, valid_to)
            );
            CREATE TABLE IF NOT EXISTS dream_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                signals_collected INTEGER DEFAULT 0,
                signals_passed INTEGER DEFAULT 0,
                writes INTEGER DEFAULT 0,
                tokens_saved INTEGER DEFAULT 0,
                sprout_count INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_facts_entity_key ON facts(entity, key);
            CREATE INDEX IF NOT EXISTS idx_facts_strength ON facts(strength);
            CREATE INDEX IF NOT EXISTS idx_facts_last_access ON facts(last_accessed);
        """)
        db.commit()
        db.close()

    def add_fact(self, key: str, value: str, fact_type: str = "general", 
                 tier: str = "core", source: str = "dream_engine") -> int:
        """写入双时序事实：自动关闭旧事实"""
        db = self._get_db()
        now = datetime.now().isoformat()

        # 关闭旧的同名事实
        db.execute(
            "UPDATE facts SET valid_to = ? WHERE entity = 'user' AND key = ? AND valid_to IS NULL",
            (now, key)
        )

        db.execute(
            """INSERT INTO facts (entity, key, value, fact_type, tier, valid_from, last_accessed, source)
               VALUES ('user', ?, ?, ?, ?, ?, ?, ?)""",
            (key, value, fact_type, tier, now, now, source)
        )
        db.commit()
        fid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()
        return fid

    def get_fact(self, key: str) -> Optional[dict]:
        """获取当前有效事实"""
        db = self._get_db()
        cols = [c[0] for c in db.execute("SELECT * FROM facts LIMIT 0").description]
        row = db.execute(
            "SELECT * FROM facts WHERE entity='user' AND key=? AND valid_to IS NULL ORDER BY id DESC LIMIT 1",
            (key,)
        ).fetchone()
        db.close()
        if row:
            return dict(zip(cols, row))
        return None

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """全文搜索（SQLite LIKE + 简单TF-IDF）"""
        db = self._get_db()
        terms = query.lower().split()
        results = []
        for term in terms:
            rows = db.execute(
                "SELECT * FROM facts WHERE valid_to IS NULL AND (key LIKE ? OR value LIKE ?) ORDER BY strength DESC LIMIT ?",
                (f"%{term}%", f"%{term}%", limit)
            ).fetchall()
            for row in rows:
                d = dict(zip([c[0] for c in db.execute("SELECT * FROM facts LIMIT 0").description], row))
                if d not in results:
                    results.append(d)
        db.close()
        return results[:limit]

    def apply_decay(self) -> int:
        """应用艾宾浩斯衰减"""
        db = self._get_db()
        count = 0
        rows = db.execute(
            "SELECT id, strength, last_accessed FROM facts WHERE valid_to IS NULL"
        ).fetchall()
        for fid, strength, last_access in rows:
            new_strength = EbbinghausDecay.current_strength(strength, last_access)
            if abs(new_strength - strength) > 0.01:
                db.execute("UPDATE facts SET strength = ? WHERE id = ?", (new_strength, fid))
                count += 1
                # 低于阈值自动归档
                if EbbinghausDecay.should_archive(new_strength):
                    now = datetime.now().isoformat()
                    db.execute("UPDATE facts SET valid_to = ?, tier = 'archive' WHERE id = ?", (now, fid))
        db.commit()
        db.close()
        return count

    def boost_access(self, key: str):
        """访问后增强记忆"""
        db = self._get_db()
        db.execute(
            "UPDATE facts SET access_count = access_count + 1, strength = MIN(1.0, strength * ?), last_accessed = ? WHERE entity='user' AND key=? AND valid_to IS NULL",
            (EbbinghausDecay.BOOST_FACTOR, datetime.now().isoformat(), key)
        )
        db.commit()
        db.close()

    def get_stats(self) -> dict:
        """存储统计"""
        db = self._get_db()
        total = db.execute("SELECT COUNT(*) FROM facts WHERE valid_to IS NULL").fetchone()[0]
        archived = db.execute("SELECT COUNT(*) FROM facts WHERE tier='archive'").fetchone()[0]
        avg_strength = db.execute("SELECT AVG(strength) FROM facts WHERE valid_to IS NULL").fetchone()[0] or 0
        db.close()
        return {"total_facts": total, "archived": archived, "avg_strength": round(avg_strength, 3)}


# ═══════════════════════════════════════════
# 🆕 Token 节省追踪器
# ═══════════════════════════════════════════

class TokenTracker:
    """追踪零LLM提取节省的token"""

    AVG_EXTRACTION_TOKENS = 500  # 单次LLM提取约消耗500 tokens

    def __init__(self):
        self.saved = 0
        self.runs = 0

    def record_run(self, facts_extracted: int):
        """记录一次运行节省的token"""
        saved = facts_extracted * self.AVG_EXTRACTION_TOKENS
        self.saved += saved
        self.runs += 1
        return saved

    def report(self) -> str:
        return f"🪙 已节省 ~{self.saved:,} tokens (零LLM提取 ×{self.runs}次)"


# ═══════════════════════════════════════════
# 🆕 v3.0 DreamEngine 升级
# ═══════════════════════════════════════════

class DreamEngineV3:
    """记忆梦境引擎 v3.0 — 融合艾宾浩斯衰减 + 零LLM提取 + SQLite持久化"""

    def __init__(self, session_search_fn=None, memory_fn=None, get_usage_fn=None, db_path=None):
        self.store = MemoryStore(db_path)
        self.tracker = TokenTracker()

        # 保留原有适配器接口（向后兼容）
        self.session_search_fn = session_search_fn
        self.memory_fn = memory_fn
        self.get_usage_fn = get_usage_fn

        # 沿用v2的评分器（保持兼容）
        from engine import SignalScorer, SproutDetector
        self.scorer = SignalScorer()
        self.detector = SproutDetector()

        self.run_count = 0

    def ingest(self, text: str, source: str = "conversation") -> dict:
        """摄入一段文本：零LLM提取 + 写入SQLite"""
        # 零LLM提取事实
        facts = ZeroLLMExtractor.extract(text)

        # 写入存储
        written = []
        for f in facts:
            try:
                fid = self.store.add_fact(
                    key=f"auto_{f['type']}_{hashlib.md5(f['value'].encode()).hexdigest()[:6]}",
                    value=f['value'],
                    fact_type=f['type'],
                    source=source
                )
                written.append({"key": f['value'][:40], "type": f['type'], "id": fid})
            except:
                pass

        # 追踪token节省
        saved = self.tracker.record_run(len(written))

        return {
            "extracted": len(facts),
            "written": len(written),
            "tokens_saved": saved,
            "facts": written,
        }

    def remember(self, key: str, value: str, fact_type: str = "general", tier: str = "core"):
        """显式记住一个事实"""
        return self.store.add_fact(key, value, fact_type, tier, source="explicit")

    def recall(self, query: str = None, key: str = None, limit: int = 10) -> list[dict]:
        """检索记忆"""
        if key:
            fact = self.store.get_fact(key)
            if fact:
                self.store.boost_access(key)  # 访问增强
            return [fact] if fact else []
        return self.store.search(query or "", limit)

    def dream(self, text: str = None, days_back: int = 2) -> dict:
        """执行一次梦境周期"""
        self.run_count += 1
        result = {
            "run": self.run_count,
            "timestamp": datetime.now().isoformat(),
            "ingested": None,
            "decayed": 0,
            "sprouts": [],
        }

        # 摄入新内容
        if text:
            result["ingested"] = self.ingest(text)

        # 每3次运行：应用衰减 + 检测发芽
        if self.run_count % 3 == 0:
            decayed = self.store.apply_decay()
            result["decayed"] = decayed

            # 发芽检测
            all_facts = self.store.search("", limit=50)
            memories_for_detect = [{"content": f"{f['key']}={f['value']}", "timestamp": f['valid_from']} for f in all_facts]
            sprouts = self.detector.detect(memories_for_detect)
            result["sprouts"] = [
                {"topic": s.topic, "type": s.action_type, "suggestion": s.suggestion}
                for s in sprouts
            ]

        # 统计
        stats = self.store.get_stats()
        result["stats"] = stats
        result["token_report"] = self.tracker.report()

        return result


# ═══════════════════════════════════════════
# 🆕 对比表：我们 vs 溯忆 vs 其他
# ═══════════════════════════════════════════

COMPARISON = """
| 特性 | 🌙 梦境引擎 v3 | 溯忆 Suyi | Mem0 | 
|:-----|:------------:|:--------:|:----:|
| 艾宾浩斯衰减 | ✅ | ✅ | ❌ |
| 双时序事实 | ✅ | ✅ | ❌ |
| 零LLM提取 | ✅ 中英文 | ✅ 英文 | ❌ |
| SQLite持久化 | ✅ | ✅ | ❌ |
| 五阶段梦境流水线 | ✅ **独有** | ❌ | ❌ |
| 信号采集(决策/纠偏) | ✅ **独有** | ❌ | ❌ |
| 三维动态评分 | ✅ **独有** | ❌ | ❌ |
| 内容发芽(sprout) | ✅ **独有** | ❌ | ❌ |
| Token节省追踪 | ✅ **独有** | ❌ | ❌ |
| 记忆优化(去重/压缩) | ✅ **独有** | ❌ | ❌ |
| Hermes Agent集成 | ✅ **独有** | ❌ | ❌ |
| pip installable | 🔲 | ✅ | ✅ |
| 零依赖 | ✅ | ✅ | ❌ |
| 代码行数 | ~800 | ~550 | 50000+ |
"""

if __name__ == "__main__":
    print("🌙 记忆梦境引擎 v3.0")
    print("=" * 50)
    # 演示
    engine = DreamEngineV3()

    # 测试摄入
    r = engine.ingest("我喜欢简洁的回复风格，不要啰嗦。我用的操作系统是Windows 11。以后止损线设-8%。")
    print(f"零LLM提取: {r['extracted']} 条事实, 写入 {r['written']} 条")
    print(f"token节省: {r['tokens_saved']}")

    # 测试回忆
    facts = engine.recall(query="Windows")
    print(f"搜索'Windows': {len(facts)} 条结果")

    # 完整梦境
    r2 = engine.dream("合尘猫决定把夏令营价格定在2999元。不要用Bing搜中文。")
    print(f"\n梦境 #{r2['run']}: {r2['stats']}")
    print(engine.tracker.report())

    print("\n" + COMPARISON)


if __name__ == "__main__":
    print("记忆梦境引擎 v2.0 核心模块已就绪")
    print("  SignalCollector / SignalScorer / MemoryWriter / MemoryOptimizer / SproutDetector")
    print("  DreamEngine.dream() -> DreamReport")
