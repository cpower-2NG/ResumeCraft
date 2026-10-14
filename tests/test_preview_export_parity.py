"""预览与导出必须共用同一套估算常数。

分页在两处各有一份实现：导出侧 `app/services.py`，预览侧 `web/src/lib/resume.ts`。
两份表是手抄的，历史上漂移过两次，而且症状都不明显：

- `chars_per_line` 只在一侧按字宽单位改过，预览与导出的断页就会错位；
- 并排额度只改了导出侧，于是**预览把两个栏目并排、导出的纸上却是整宽通排**——
  用户在预览里看到的分页与拿到的 HTML 不是同一份版面。

这个测试直接读 TS 源码里的常量表，逐项与 Python 侧比对。改版式常数时改一处就会失败，
逼着两边同步（`tests/test_template_compatibility.py::test_preview_matches_export_rhythm`
比对的是 CSS 数值，这里是估算模型，两者互补）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services import (LAYOUT_METRICS, PAIR_BUDGET_BY_LAYOUT, PAIR_MAX_SHARE,
                          PAIR_MIN_BALANCE, PAIR_MIN_SAVING, PAIR_REF_CHARS, PAGE_BUDGET_PX)

RESUME_TS = Path(__file__).resolve().parents[1] / "web" / "src" / "lib" / "resume.ts"
TS = RESUME_TS.read_text(encoding="utf-8")

METRIC_KEYS = tuple(LAYOUT_METRICS["sidebar"])


def _ts_number(name: str) -> float:
    match = re.search(rf"const {name}\s*=\s*([\d.]+)", TS)
    assert match, f"{RESUME_TS.name} 里找不到常数 {name}"
    return float(match.group(1))


def _ts_metrics() -> dict[str, dict[str, float]]:
    """LAYOUT_METRICS 的 TS 字面量 → {layout: {key: value}}。"""
    body = re.search(r"const LAYOUT_METRICS:Record<string,\{[^}]*\}> = \{(.*?)\n\}", TS, re.S)
    assert body, "解析不到 LAYOUT_METRICS 字面量"
    table: dict[str, dict[str, float]] = {}
    for line in body.group(1).splitlines():
        entry = re.match(r"\s*(\w+):\s*\{([^}]*)\}", line)
        if not entry:
            continue
        table[entry.group(1)] = dict(re.findall(r"(\w+):([\d.]+)", entry.group(2)))
    return table


def _ts_pair_budget() -> dict[str, int]:
    match = re.search(r"const PAIR_BUDGET_BY_LAYOUT:Record<string,number>=\{([^}]*)\}", TS)
    assert match, "解析不到 PAIR_BUDGET_BY_LAYOUT 字面量"
    return {key: int(value) for key, value in re.findall(r"(\w+):(\d+)", match.group(1))}


def test_layout_metrics_tables_match():
    ts = _ts_metrics()
    assert set(ts) == set(LAYOUT_METRICS), f"两端的布局集合不一致：{set(ts) ^ set(LAYOUT_METRICS)}"
    for layout, row in LAYOUT_METRICS.items():
        for key in METRIC_KEYS:
            assert key in ts[layout], f"预览侧 {layout} 缺少 {key}"
            assert float(row[key]) == float(ts[layout][key]), (
                f"{layout}.{key} 两端不一致：导出 {row[key]} vs 预览 {ts[layout][key]}"
            )


def test_page_budgets_match():
    """页预算：导出侧是 PAGE_BUDGET_PX，预览侧是 BUDGETS 字面量 + 若干具名常数。"""
    ts_budgets = {key: int(value) for key, value in
                  re.findall(r"(\w+):([\d]+)", re.search(r"const BUDGETS:Record<string,number>=\{(.*?)\}", TS, re.S).group(1))}
    for layout, name in (("sidebar", "MAIN_BUDGET"), ("side", "SIDE_BUDGET"), ("banner", "BANNER_BUDGET"),
                         ("grid", "GRID_BUDGET"), ("line", "LINE_BUDGET"), ("timeline", "TIMELINE_BUDGET"),
                         ("rail", "RAIL_BUDGET")):
        ts_budgets[layout] = int(_ts_number(name))
    for layout, value in PAGE_BUDGET_PX.items():
        assert layout in ts_budgets, f"预览侧缺少 {layout} 的页预算"
        assert float(value) == ts_budgets[layout], f"{layout} 的页预算不一致：导出 {value} vs 预览 {ts_budgets[layout]}"


@pytest.mark.parametrize("py_value,ts_name", [
    (PAIR_MAX_SHARE, "PAIR_MAX_SHARE"),
    (PAIR_REF_CHARS, "PAIR_REF_CHARS"),
    (PAIR_MIN_SAVING, "PAIR_MIN_SAVING"),
    (PAIR_MIN_BALANCE, "PAIR_MIN_BALANCE"),
])
def test_pair_constants_match(py_value, ts_name):
    assert float(py_value) == _ts_number(ts_name), f"{ts_name} 两端不一致：导出 {py_value} vs 预览 {_ts_number(ts_name)}"


def test_pair_budget_matches():
    ts = _ts_pair_budget()
    assert ts == dict(PAIR_BUDGET_BY_LAYOUT), f"并排额度两端不一致：导出 {PAIR_BUDGET_BY_LAYOUT} vs 预览 {ts}"
