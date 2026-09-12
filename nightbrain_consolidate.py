"""
NightBrain Consolidation — 记忆梦境引擎第六阶段
夜间巩固知识库：扫描新知→关联旧知→标记陈旧→更新索引
v1.0 | 2026-06-06 | 合尘猫 × 小甜甜
"""
import os, sys, datetime, re, json, sqlite3
from pathlib import Path

# 知识库根目录：优先读环境变量，避免把个人路径写死在代码里
KB_ROOT = os.environ.get("MEMORY_KB_ROOT") or str(Path.home() / "memory-kb")
STALENESS_DAYS = 30  # 30天未更新标记为可能需要刷新

def scan_new_files():
    """扫描最近24小时新增/修改的知识库文件"""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=1)
    new_files = []
    for root, dirs, files in os.walk(KB_ROOT):
        for f in files:
            if not f.endswith('.md'):
                continue
            fpath = os.path.join(root, f)
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
            ctime = datetime.datetime.fromtimestamp(os.path.getctime(fpath))
            if mtime > cutoff or ctime > cutoff:
                rel = os.path.relpath(fpath, KB_ROOT)
                new_files.append({
                    "path": rel,
                    "mtime": mtime.strftime("%Y-%m-%d %H:%M"),
                    "ctime": ctime.strftime("%Y-%m-%d %H:%M"),
                })
    return new_files

def check_staleness():
    """检查知识库中可能陈旧的文件"""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=STALENESS_DAYS)
    stale = []
    for root, dirs, files in os.walk(KB_ROOT):
        for f in files:
            if not f.endswith('.md'):
                continue
            fpath = os.path.join(root, f)
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime < cutoff:
                rel = os.path.relpath(fpath, KB_ROOT)
                days_old = (datetime.datetime.now() - mtime).days
                stale.append({"path": rel, "days_old": days_old})
    return stale

def check_cross_references():
    """检查知识库文件之间的交叉引用"""
    refs = {}
    orphans = []
    for root, dirs, files in os.walk(KB_ROOT):
        for f in files:
            if not f.endswith('.md'):
                continue
            fpath = os.path.join(root, f)
            rel = os.path.relpath(fpath, KB_ROOT)
            with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                content = fh.read()
            # Count wiki-style links
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
            refs[rel] = len(links)
    
    # Find orphans (files with 0 outgoing links, excluding index/README)
    for fname, count in refs.items():
        if count == 0 and fname not in ['index.md', 'README.md']:
            orphans.append(fname)
    
    return orphans, refs

def update_index():
    """更新 index.md 导航"""
    sections = {}
    for root, dirs, files in os.walk(KB_ROOT):
        rel = os.path.relpath(root, KB_ROOT)
        if rel == '.':
            continue
        md_files = [f for f in files if f.endswith('.md') and f not in ['index.md', 'README.md']]
        if md_files:
            sections[rel] = len(md_files)
    
    index_content = f"""# 知识库索引

> 自动生成: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
> 总文件数: {sum(sections.values())}

## 📊 统计

| 目录 | 文件数 |
|:-----|:------:|
"""
    for sec, count in sorted(sections.items()):
        index_content += f"| {sec} | {count} |\n"
    
    index_content += "\n---\n*索引由夜间巩固cron自动更新*\n"
    
    idx_path = os.path.join(KB_ROOT, "index.md")
    with open(idx_path, 'w', encoding='utf-8') as f:
        f.write(index_content)

def main():
    now = datetime.datetime.now()
    
    # 1. Scan new files
    new_files = scan_new_files()
    
    # 2. Check staleness
    stale_files = check_staleness()
    
    # 3. Check cross-references
    orphans, refs = check_cross_references()
    
    # 4. Update index
    update_index()
    
    # 5. Generate report
    report = f"""## 🌙 夜间知识巩固报告 — {now.strftime("%Y-%m-%d %H:%M")}

### 📥 24h新增/修改 ({len(new_files)}个)
"""
    if new_files:
        for f in new_files[:10]:
            report += f"- `{f['path']}` ({f['mtime']})\n"
        if len(new_files) > 10:
            report += f"- ... 还有{len(new_files)-10}个\n"
    else:
        report += "（无）\n"
    
    report += f"\n### ⏰ 可能陈旧 (>30天未更新, {len(stale_files)}个)\n"
    if stale_files:
        for f in sorted(stale_files, key=lambda x: -x['days_old'])[:5]:
            report += f"- `{f['path']}` ({f['days_old']}天)\n"
    else:
        report += "（无）\n"
    
    report += f"\n### 🔗 交叉引用\n"
    report += f"- 孤立文件(无出链): {len(orphans)}个\n"
    if orphans:
        for o in orphans[:5]:
            report += f"  - `{o}`\n"
    
    report += f"\n### 📊 总览\n"
    total = sum(refs.values())
    report += f"- 总文件: {len(refs)}\n"
    report += f"- 总引用链接: {total}\n"
    report += f"- 平均引用/文件: {total/max(len(refs),1):.1f}\n"
    
    report += f"\n> 🔄 记忆梦境引擎已同步 | 下次运行: 24小时后\n"
    
    print(report)

if __name__ == "__main__":
    main()
