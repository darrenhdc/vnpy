#!/usr/bin/env python3
"""
CLI: ./sota — SOTA strategy briefing (A01/A02 standard)
"""
import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOTA_MD = ROOT / "research" / "SOTA.md"

# ── Color ──
def _use_color():
    if os.getenv("NO_COLOR"): return False
    return sys.stdout.isatty()

def c(name, text):
    if not _use_color(): return text
    codes = {"bold":"1","dim":"2","red":"31","green":"32","yellow":"33","cyan":"36","magenta":"35","white":"37"}
    return f"\033[{codes[name]}m{text}\033[0m"

def s_color(val):
    if val is None: return c("dim","—")
    try:
        v = float(str(val).replace("~","").replace("x",""))
        if v >= 1.0: return c("green", str(val))
        if v >= 0.5: return c("yellow", str(val))
        if v > 0: return c("dim", str(val))
        return c("red", str(val))
    except: return str(val)

def signed(v, suffix=""):
    if v is None: return c("dim","—")
    try:
        n = float(v)
        color = "green" if n > 0 else "red" if n < 0 else "dim"
        return c(color, f"{n:+.1f}{suffix}")
    except: return str(v)

# ── Parse SOTA.md ──
text = SOTA_MD.read_text() if SOTA_MD.exists() else ""
lines = text.split("\n")

def parse_table(heading):
    """Parse 2-col table (key | value) after a heading."""
    fields = {}
    in_sec = False; seen = False
    for line in lines:
        if heading in line:
            in_sec = True; continue
        if not in_sec: continue
        if line.startswith("|") and "---" not in line and "属性" not in line:
            parts = [p.strip().replace("*","") for p in line.split("|")]
            vals = [p for p in parts if p]
            if len(vals) >= 2: fields[vals[0]] = vals[1]; seen = True
        elif seen and line.strip() == "": break
    return fields

def parse_pool():
    """Parse candidate pool table."""
    rows = []
    in_sec = False
    for line in lines:
        if "候选策略池" in line: in_sec = True; continue
        if not in_sec: continue
        if line.startswith("|") and "状态" not in line and "---" not in line:
            parts = [p.strip().replace("*","") for p in line.split("|")]
            vals = [p for p in parts if p]
            if len(vals) >= 4: rows.append(vals)
        elif rows and line.strip() == "": break
    return rows

sota = parse_table("## 当前 SOTA")
pool = parse_pool()

# ── Output ──
print()
print(c("bold","════════════════════════════════════════════════════════════"))
print(c("bold",f"  US Stocks — SOTA Strategy"))
print(c("bold","════════════════════════════════════════════════════════════"))
print()

# 1. Profile
print(c("yellow",f"  {sota.get('策略名','?').strip('`')}  {c('dim',sota.get('版本',''))}"))
print(c("dim",f"  {sota.get('描述','')}"))
print()

# 2. Performance
print(c("bold","  Performance"))
print(f"  ┌{'─'*38}┬{'─'*20}┐")
for label, key, fmt_fn in [
    ("OOS Sharpe (mean)", "OOS Sharpe (mean)", s_color),
    ("OOS Sharpe (median)", "OOS Sharpe (median)", s_color),
    ("OOS Positive Years", "OOS 正收益年", lambda v: c("green",str(v)) if v and "/" in str(v) and int(str(v).split("/")[0].split()[0]) >= int(str(v).split("/")[1].split()[0]) else str(v) if v else "—"),
    ("OOS Negative Years", "OOS 负收益年", lambda v: str(v) if v else "—"),
    ("Param Stability", "参数稳定性", lambda v: v if v else "—"),
    ("Active Status", "活跃状态", lambda v: c("green",v) if "Paper" in str(v) else c("yellow",v) if "Research" in str(v) else str(v)),
]:
    val = sota.get(key, "—")
    if callable(fmt_fn): val = fmt_fn(val)
    val_str = str(val)[:35]
    print(f"  │ {label:<36} │ {val_str:>20} │")
print(f"  └{'─'*38}┴{'─'*20}┘")
print()

# 3. OOS Detail — Walk-Forward yearly
wf_data = [
    (2014, 0.200), (2015, -0.700), (2016, 1.010), (2017, 2.425),
    (2018, -1.682), (2019, 2.385), (2020, 1.227), (2021, 1.073),
    (2022, -0.680), (2023, 1.631), (2024, 0.909), (2025, 1.840), (2026, 1.722),
]
pos_years = sum(1 for _, v in wf_data if v > 0)
avg = sum(v for _, v in wf_data) / len(wf_data)

print(c("bold",f"  Walk-Forward (13 OOS years, expanding train / 1y test)"))
print(c("dim",f"  avg={avg:+.2f}  positive={pos_years}/{len(wf_data)}  green=positive  red=negative"))
print()

max_abs = max(abs(v) for _, v in wf_data)
max_bar = 30
for yr, val in wf_data:
    bar_len = max(1, int(abs(val) / max_abs * max_bar)) if max_abs > 0 else 1
    bar = "█" * bar_len
    if val >= 0:
        print(c("dim",f"  {yr}  ") + c("green",f"{bar:<{max_bar}s}") + c("green",f" {val:+.3f}"))
    else:
        print(c("dim",f"  {yr}  ") + c("red",f"{bar:<{max_bar}s}") + c("red",f" {val:+.3f}"))
print()

# 4. Key Methodology
print(c("bold","  Methodology"))
print("  • Expanding window train on all prior years")
print("  • Grid search (fast/slow) on train only → select best")
print("  • Test on next calendar year → report OOS Sharpe")
print("  • Parameter (10/15) confirmed stable across 11/13 years")
print()

# 5. Candidate Pool
print(c("bold","  Candidate Pool"))
for row in pool:
    if len(row) >= 4:
        name, status, sharpe, note = row[0], row[1], row[2], row[3]
        sc = c("green",status) if "Paper" in status else c("yellow",status) if "Research" in status else c("red",status) if "Reject" in status else c("dim",status)
        ssc = s_color(sharpe) if sharpe != "—" else c("dim","—")
        print(f"  {c('bold',name):<44} {sc:<18} {ssc:<14} {note[:30]}")
print()

# 6. Quick Start
print(c("cyan","─" * 60))
print(c("bold","  Quick Start"))
print(c("dim","  Paper trading:"))
print(f"    ./run-live --strategy VnpyMaCrossStrategy --symbol US.SPY --warmup 100")
print()

# Footer
print(c("dim","─" * 60))
print(f"  {c('cyan','Full details →')}  research/SOTA.md")
print(f"  {c('cyan','Archived strategies →')}  {c('yellow','./archived')}")
print(c("bold","════════════════════════════════════════════════════════════"))
