"""记忆梦境引擎 单元测试"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import Signal, ScoredSignal, SignalScorer, DreamEngine, DreamReport, report_to_dict


class TestSignalScorer:
    """阶段2：评分器测试"""

    def setup(self):
        self.scorer = SignalScorer()

    def test_decision_signal_scores_high(self):
        """决策信号应获得高分"""
        sig = Signal(source="决策信号", content="用户规则：持仓需设止损线，每只票不超过-8%必须割")
        result = self.scorer.score(sig)
        assert result.total >= 70, f"Expected >=70, got {result.total:.0f}"
        assert result.action == "write"

    def test_correction_signal_scores_high(self):
        """纠偏信号应获得高分"""
        sig = Signal(source="纠偏信号", content="不对，不要用Bing搜中文，改用新浪新闻直连")
        result = self.scorer.score(sig)
        assert result.total >= 70, f"Expected >=70, got {result.total:.0f}"

    def test_noise_signal_is_skipped(self):
        """噪音应被跳过"""
        sig = Signal(source="灵感信号", content="今天天气不错适合出去玩")
        result = self.scorer.score(sig)
        assert result.total < 70, f"Expected <70, got {result.total:.0f}"
        assert result.action == "skip"

    def test_tool_signal_scores_high(self):
        """工具信号应获得高分"""
        sig = Signal(source="工具信号", content="API Key配置方法：写入.env文件的ZAI_API_KEY字段")
        result = self.scorer.score(sig)
        assert result.total >= 70, f"Expected >=70, got {result.total:.0f}"

    def test_empty_signal_is_low(self):
        """空信号得分低"""
        sig = Signal(source="灵感信号", content="")
        result = self.scorer.score(sig)
        assert result.action == "skip"


class TestDreamEngine:
    """完整流水线测试"""

    def setup(self):
        self.memories = []
        def mock_search(query, limit, sort):
            return [
                {"session_id": "abc", "content": "用户规则：止损-8%", "timestamp": "2026-06-05"},
                {"session_id": "def", "content": "不对，不要用Bing", "timestamp": "2026-06-04"},
            ]
        def mock_memory(action, target, content, old_text=None):
            self.memories.append({"action": action, "content": content})
            return {"status": "ok"}
        def mock_usage():
            return (1500, 2200)

        self.engine = DreamEngine(mock_search, mock_memory, mock_usage)

    def test_dream_returns_report(self):
        """dream() 应返回 DreamReport"""
        existing = [{"content": "偏好：主动做事", "timestamp": "2026-06-01"}]
        report = self.engine.dream(existing_memories=existing)
        assert isinstance(report, DreamReport)
        assert report.signals_collected > 0

    def test_report_to_dict(self):
        """report_to_dict 导出正确"""
        existing = [{"content": "测试记忆", "timestamp": "2026-06-01"}]
        report = self.engine.dream(existing_memories=existing)
        d = report_to_dict(report)
        assert "timestamp" in d
        assert "signals_collected" in d
        assert isinstance(d["sprouts"], list)


class TestSignalCollector:
    """阶段1：采集器测试"""

    def test_collect_limits_to_10(self):
        from engine import SignalCollector
        def mock_search(query, limit, sort):
            return [{"session_id": f"s{i}", "content": f"signal {i}", "timestamp": "2026-06-05"} for i in range(20)]
        collector = SignalCollector(mock_search)
        signals = collector.collect()
        assert len(signals) <= 10


if __name__ == "__main__":
    # Simple test runner
    passed = failed = 0
    for cls in [TestSignalScorer, TestDreamEngine, TestSignalCollector]:
        test = cls()
        if hasattr(test, 'setup'):
            test.setup()
        for name in dir(test):
            if name.startswith("test_"):
                try:
                    getattr(test, name)()
                    print(f"  ✅ {cls.__name__}.{name}")
                    passed += 1
                except Exception as e:
                    print(f"  ❌ {cls.__name__}.{name}: {e}")
                    failed += 1
    print(f"\n{passed} passed, {failed} failed")
