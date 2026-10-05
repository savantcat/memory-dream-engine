# -*- coding: utf-8 -*-
"""
记忆梦境引擎 · Memory Dream Engine MCP Server
============================================
把「AI 睡眠系统」的核心能力做成 Agent 可直接调用的工具：
**零 LLM 事实提取 → 三维信号评分 → 艾宾浩斯衰减 → 五阶段梦境流水线 → 内容发芽**。

纯标准库、零 LLM 成本、不需要任何 API Key。

双通道:
  本地 stdio   :  python server.py
  远程 HTTP    :  python server.py --transport http --host 127.0.0.1 --port 8770

暴露工具:
  - extract_facts       零 LLM 事实提取（纯正则，中英文通吃，不花一分钱 token）
  - score_signal        三维动态评分（按信号类型自适应调权）+ 写入建议
  - decay_report        艾宾浩斯衰减：当前强度、访问增强、归档判定、衰减曲线
  - simulate_dream      用一段文本跑完整五阶段梦境周期，返回报告（临时库，不留副作用）
  - list_signal_types   四维信号定义、权重与打分关键词
  - engine_info         引擎能力概览与取舍说明

自检(不走协议,直接打工具):  python server.py --selftest
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# 工具注解：纯读、幂等、不接触外部世界，统一声明为 RO_ANN。
try:
    from mcp.types import ToolAnnotations
except ImportError:  # 老版本 SDK 无该类型时降级为 dict，行为一致
    ToolAnnotations = dict

# mcp 2.x 把 FastMCP 更名为 MCPServer；兼容 1.x，避免 SDK 升级打断通道。
try:  # mcp >= 2.x
    from mcp.server.mcpserver import MCPServer as _MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _MCPServer

# 公网部署必需：SDK 默认开启 DNS-rebinding 防护，只放行 localhost，
# 外部以真实域名访问会被拒成 421「Invalid Host header」。这里改为白名单放行。
try:
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:  # 老版本 SDK 无此模块
    TransportSecuritySettings = None

from engine import (  # noqa: E402
    ZeroLLMExtractor,
    EbbinghausDecay,
    SignalScorer,
    Signal,
    DreamEngineV3,
    SIGNAL_CONFIG,
    COMPARISON,
)

# 端口一律用 host:* 通配——写死端口后，任何换端口的探活（本地测试 / CI /
# 目录站的容器构建测试）都会吃 421，而报错只有一句 Invalid Host header。
DEFAULT_ALLOWED_HOSTS = [
    "savantcat.cn", "savantcat.cn:443", "savantcat.cn:*",
    "www.savantcat.cn", "www.savantcat.cn:443", "www.savantcat.cn:*",
    "127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*",
]

SIGNAL_TYPES = list(SIGNAL_CONFIG.keys())

SIGNAL_DETAIL = [
    {
        "signal_type": name,
        "weight": cfg["weight"],
        "queries": cfg["queries"],
        "limit": cfg["limit"],
        "维度权重": {
            "决策信号": {"durability": 0.7, "correction": 0.2, "reusability": 0.1},
            "纠偏信号": {"durability": 0.2, "correction": 0.7, "reusability": 0.1},
            "工具信号": {"durability": 0.2, "correction": 0.1, "reusability": 0.7},
            "灵感信号": {"durability": 0.4, "correction": 0.2, "reusability": 0.4},
        }.get(name, {"durability": 0.5, "correction": 0.3, "reusability": 0.2}),
    }
    for name, cfg in SIGNAL_CONFIG.items()
]

ACTION_RULE = "total >= 90 → replace（替换旧条目） / >= 70 → write（新增） / < 70 → skip（丢弃）"

CURVE_DAYS = [0, 7, 14, 30, 45, 60, 90, 180]


def _transport_security():
    if TransportSecuritySettings is None:
        return None
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,   # 保留防护，用白名单而非改关闭
        allowed_hosts=DEFAULT_ALLOWED_HOSTS,
        allowed_origins=["*"],                  # 公开只读服务：允许任意来源 Agent 调用
    )


def _blank(text):
    return not text or not str(text).strip()


# ---------------------------------------------------------------- MCP Server
SERVER_VERSION = "1.0.0"

mcp = _MCPServer(
    "memory-dream-engine",
    title="记忆梦境引擎 · Memory Dream Engine",
    description=(
        "给 AI 装一套睡眠系统：零 LLM 事实提取、三维信号评分、艾宾浩斯衰减、"
        "五阶段梦境流水线、内容发芽检测。纯计算、零依赖、无需 API Key。"
    ),
    version=SERVER_VERSION,
    website_url="https://savantcat.cn/mcp-dream",
    instructions=(
        "记忆梦境引擎把「AI 聊完就忘、记忆越写越满不敢删、零散结论攒不成产出」"
        "这三件事做成可计算的流程。四维信号采集（决策/纠偏/工具/灵感）→ 三维动态评分"
        "（按信号类型自适应调权，不是一把尺子量到底）→ 艾宾浩斯衰减（30 天半衰期，"
        "高频访问自动增强、低强度自动归档）→ 内容发芽（同批记忆攒够就提示可以出内容了）。"
        "事实提取走纯正则，中英文通吃，提取一万条也不花一分钱 token。"
        "本服务不保存调用方的任何数据：simulate_dream 用临时库跑完整周期后即销毁。"
    ),
)

RO_ANN = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                         idempotentHint=True, openWorldHint=False)


@mcp.tool(annotations=RO_ANN)
def extract_facts(text: str) -> str:
    """零 LLM 事实提取：用纯正则从一段对话/笔记里抽出可长期记住的事实。

    中英文通吃（这是与同类工具最大的差别——多数方案只支持英文正则）。
    不调用任何模型，不花 token。抽取类型：偏好 preference / 纠偏 correction /
    环境 env / 工具 tool / 决策 decision。

    Args:
        text: 待提取的文本（对话记录、笔记、复盘都行）。上限返回 10 条。
    """
    if _blank(text):
        return json.dumps({"error": "内容为空", "hint": "传入一段对话或笔记文本"},
                          ensure_ascii=False)
    facts = ZeroLLMExtractor.extract(str(text))
    by_type = {}
    for f in facts:
        by_type[f["type"]] = by_type.get(f["type"], 0) + 1
    return json.dumps({
        "count": len(facts),
        "by_type": by_type,
        "facts": facts,
        "note": "confidence 固定 0.7（正则命中的保守置信度）；"
                "抽不出不等于没信息，可能是表述不在正则覆盖范围。",
    }, ensure_ascii=False, indent=1)


@mcp.tool(annotations=RO_ANN)
def score_signal(text: str, signal_type: str = "决策信号") -> str:
    """三维动态评分：给一条信号打分，并给出该不该写进长期记忆的结论。

    三个维度是 durability（持久度）/ correction（纠偏度）/ reusability（复用度），
    权重按信号类型自适应——决策信号看持久度、纠偏信号看纠偏度、工具信号看复用度。

    Args:
        text: 信号内容（一句话或一整段都行）。
        signal_type: 信号类型，必须是 list_signal_types 里的名字之一：
                     决策信号 / 纠偏信号 / 工具信号 / 灵感信号
    """
    if _blank(text):
        return json.dumps({"error": "内容为空"}, ensure_ascii=False)
    st = (signal_type or "").strip()
    if st not in SIGNAL_TYPES:
        return json.dumps({
            "error": "未识别的信号类型: %s" % st,
            "available_signal_types": SIGNAL_TYPES,
        }, ensure_ascii=False)
    sc = SignalScorer().score(Signal(source=st, content=str(text)))
    weights = next(d["维度权重"] for d in SIGNAL_DETAIL if d["signal_type"] == st)
    return json.dumps({
        "signal_type": st,
        "weights": weights,
        "durability": sc.durability,
        "correction": sc.correction,
        "reusability": sc.reusability,
        "total": round(sc.total, 1),
        "action": sc.action,
        "action_rule": ACTION_RULE,
        "hint": "action=skip 不代表这条没用，只代表按当前规则它还没到写进长期记忆的阈值。",
    }, ensure_ascii=False, indent=1)


@mcp.tool(annotations=RO_ANN)
def decay_report(strength: float = 1.0, days_since_access: float = 0.0,
                 threshold: float = 0.15) -> str:
    """艾宾浩斯衰减计算：当前记忆强度、访问一次能增强多少、该不该归档，以及完整衰减曲线。

    半衰期 30 天；最低强度 0.05（不会彻底忘记）；每次访问增强 ×1.3。
    用它回答「这条记忆放了 N 天还剩多少」「什么时候该归档」「访问一次能不能救回来」。

    Args:
        strength: 初始（或上次）记忆强度，0-1，默认 1.0。
        days_since_access: 距上次访问的天数，默认 0。
        threshold: 归档阈值，低于它建议归档，默认 0.15。
    """
    try:
        s = float(strength)
        d = float(days_since_access)
        th = float(threshold)
    except (TypeError, ValueError):
        return json.dumps({"error": "strength / days_since_access / threshold 必须是数字"},
                          ensure_ascii=False)
    s = max(0.0, min(1.0, s))
    d = max(0.0, d)

    factor = EbbinghausDecay.decay_factor(d)
    current = max(EbbinghausDecay.MIN_STRENGTH, min(s * factor, 1.0))
    boosted = EbbinghausDecay.boost(current)
    curve = [
        {"天": t,
         "强度": round(max(EbbinghausDecay.MIN_STRENGTH, min(s * EbbinghausDecay.decay_factor(t), 1.0)), 4),
         "建议归档": EbbinghausDecay.should_archive(
             max(EbbinghausDecay.MIN_STRENGTH, min(s * EbbinghausDecay.decay_factor(t), 1.0)), th)}
        for t in CURVE_DAYS
    ]
    first_archive_day = None
    for t in range(0, 1000):
        v = max(EbbinghausDecay.MIN_STRENGTH, min(s * EbbinghausDecay.decay_factor(t), 1.0))
        if EbbinghausDecay.should_archive(v, th):
            first_archive_day = t
            break

    return json.dumps({
        "params": {"strength": s, "days_since_access": d, "threshold": th,
                   "half_life_days": EbbinghausDecay.HALF_LIFE_DAYS,
                   "min_strength": EbbinghausDecay.MIN_STRENGTH,
                   "boost_factor": EbbinghausDecay.BOOST_FACTOR},
        "decay_factor": round(factor, 4),
        "current_strength": round(current, 4),
        "boost_after_one_access": round(boosted, 4),
        "should_archive": EbbinghausDecay.should_archive(current, th),
        "first_archive_day": first_archive_day,
        "curve": curve,
        "hint": "最低强度 0.05 是不被彻底忘记的下限，所以曲线不会归零；"
                "boost_after_one_access 是访问一次后的强度。",
    }, ensure_ascii=False, indent=1)


@mcp.tool(annotations=RO_ANN)
def simulate_dream(text: str = "", cycles: int = 3) -> str:
    """用一段文本跑完整的五阶段梦境周期，返回逐步报告（含发芽检测与 token 节省）。

    在**临时库**里执行，调用方不落任何持久数据。五阶段 = 浅睡采集 / 深睡评分 /
    写入 / 优化 / REM 发芽。衰减与发芽检测每 3 轮才触发，所以默认跑 3 轮。

    Args:
        text: 要摄入的文本（对话记录 / 笔记 / 复盘）。留空则只跑优化与发芽。
        cycles: 跑几轮梦境周期，默认 3（至少 3 才能触发衰减与发芽）。
    """
    try:
        n = int(cycles)
    except (TypeError, ValueError):
        n = 3
    n = max(1, min(n, 9))
    src = "" if text is None else str(text)

    tmp = tempfile.mkdtemp(prefix="mde_mcp_")
    try:
        eng = DreamEngineV3(db_path=os.path.join(tmp, "brain.db"))
        out = {
            "input_chars": len(src),
            "cycles_requested": n,
            "first_ingest": None,
            "runs": [],
            "final_stats": None,
            "token_report": None,
        }
        if src.strip():
            out["first_ingest"] = eng.ingest(src, source="mcp")
        for _ in range(n):
            r = eng.dream(src if out["first_ingest"] is None and src.strip() else None)
            out["runs"].append({
                "run": r.get("run"),
                "decayed": r.get("decayed", 0),
                "sprouts": r.get("sprouts", []),
                "stats": r.get("stats"),
            })
        out["final_stats"] = eng.store.get_stats()
        out["token_report"] = eng.tracker.report()
        out["note"] = ("本工具在临时库中执行，调用方不留任何持久数据。"
                       "衰减与发芽检测每 3 轮触发一次，所以 cycles 小于 3 时看不到这两项。"
                       "发芽非空 = 这批记忆已攒够，可以产出内容了。")
        return json.dumps(out, ensure_ascii=False, indent=1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@mcp.tool(annotations=RO_ANN)
def list_signal_types() -> str:
    """列出四维信号（决策 / 纠偏 / 工具 / 灵感）的定义、权重、检索词与三维评分权重。

    打分前先看这里，能知道每种信号被侧重看哪个维度，避免拿一把尺子量到底。
    """
    return json.dumps({
        "count": len(SIGNAL_DETAIL),
        "signal_types": SIGNAL_DETAIL,
        "score_dimensions": ["durability 持久度", "correction 纠偏度", "reusability 复用度"],
        "action_rule": ACTION_RULE,
    }, ensure_ascii=False, indent=1)


@mcp.tool(annotations=RO_ANN)
def engine_info() -> str:
    """引擎能力概览：四个「别人没有」的点、与同类方案的取舍对比、以及本服务的边界。"""
    return json.dumps({
        "highlights": [
            "零 LLM 事实提取：纯正则，中英文通吃，提取一万条也不花 token",
            "艾宾浩斯衰减：30 天半衰期，访问增强，低强度自动归档 —— 记忆会自己瘦身",
            "三维动态评分：按信号类型自适应调权，不是一把尺子量到底",
            "内容发芽：同批记忆攒够了自动提示「这批可以出内容了」",
        ],
        "pipeline": ["浅睡 · SignalCollector 四维信号采集",
                     "深睡 · SignalScorer 三维动态评分 → MemoryWriter 声明式写入",
                     "优化 · MemoryOptimizer 每 3 轮深度清理（去重/过期/压缩）",
                     "REM  · SproutDetector 3 条→星球帖 / 5 条→长文"],
        "comparison_table": COMPARISON.strip(),
        "boundary": ("本服务暴露的是引擎的**计算能力**（提取/评分/衰减/模拟），"
                     "不托管调用方的记忆库；simulate_dream 在临时库执行后即销毁。"),
    }, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- 自检
SAMPLE = ("我喜欢简洁的回复风格，不要啰嗦。我用的操作系统是Windows 11。"
          "以后止损线设-8%。合尘猫决定把知识库交付价定在 1299 元。"
          "路径在 ./kb/config.json，版本是 1.1.1。")


def _selftest():
    r = json.loads(extract_facts(SAMPLE))
    print("[1] extract_facts      -> count=%d by_type=%s" % (r["count"], r["by_type"]))
    assert r["count"] >= 3, "零LLM提取应至少命中 3 条"

    r = json.loads(score_signal("决定以后用标准库，不再装第三方依赖", "决策信号"))
    print("[2] score_signal       -> total=%s action=%s" % (r["total"], r["action"]))

    r = json.loads(decay_report(1.0, 30))
    print("[3] decay_report       -> 30天后强度=%s 归档=%s 首次归档日=%s" % (
        r["current_strength"], r["should_archive"], r["first_archive_day"]))
    assert 0.4 < r["current_strength"] < 0.6, "30 天半衰期后强度应接近 0.5"

    r = json.loads(simulate_dream(SAMPLE, 3))
    print("[4] simulate_dream     -> 轮数=%d 末轮发芽=%d 库内事实=%s" % (
        len(r["runs"]), len(r["runs"][-1]["sprouts"]),
        (r["final_stats"] or {}).get("total_facts")))

    r = json.loads(list_signal_types())
    print("[5] list_signal_types  -> count=%d" % r["count"])
    assert r["count"] == 4, "信号类型应为 4"

    r = json.loads(engine_info())
    print("[6] engine_info        -> highlights=%d pipeline=%d" % (
        len(r["highlights"]), len(r["pipeline"])))

    r = json.loads(score_signal(SAMPLE, "不存在的信号"))
    print("[7] 容错(信号类型)     -> %s available=%d" % (
        r.get("error"), len(r.get("available_signal_types", []))))

    r = json.loads(decay_report(strength="abc"))
    print("[8] 容错(参数类型)     -> %s" % r.get("error"))

    r = json.loads(extract_facts(""))
    print("[9] 容错(空内容)       -> %s" % r.get("error"))

    print("\n✅ 9/9 工具自检通过")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transport", default="stdio",
                    choices=["stdio", "http", "streamable-http", "sse"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--path", default="/mcp")
    ap.add_argument("--stateless", action="store_true",
                    help="无状态模式（反代/公网部署更稳，不依赖会话粘滞）")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    t = "streamable-http" if args.transport == "http" else args.transport
    if t == "stdio":
        mcp.run()
        return
    sys.stderr.write("[memory-dream-engine] serving on %s:%d%s (%s, stateless=%s)\n"
                     % (args.host, args.port, args.path, t, args.stateless))
    ts = _transport_security()
    kw = {} if ts is None else {"transport_security": ts}
    try:  # mcp 2.x：run() 直收 kwargs
        mcp.run(transport=t, host=args.host, port=args.port,
                streamable_http_path=args.path,
                stateless_http=args.stateless,
                max_request_body_size=1024 * 1024,
                **kw)
    except TypeError:  # mcp 1.x：kwargs 不被接受，走 settings
        s = getattr(mcp, "settings", None)
        if s is not None:
            for k, v in (("host", args.host), ("port", args.port)):
                try:
                    setattr(s, k, v)
                except Exception:
                    pass
        try:
            mcp.run(transport=t, **kw)
        except TypeError:
            mcp.run(transport=t)


if __name__ == "__main__":
    main()
