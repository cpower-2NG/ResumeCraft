"""Summarize output/tmp/metrics.json (written by web/scripts/measure_pages.mjs).

Per render: page count and each page's fill% (plus !+N when the page clips N px
of content). The aggregate block at the end is the acceptance gate used while
re-tuning the layout: no page may clip, and a non-final page must not be thin.

The fill threshold is 74%: a section is an atomic unit, so a page can legitimately end
short by however tall the next section is. Measured worst cases sit at 75-77% (quill's
classic line layout on a section boundary; single-column layouts have no pairing to
absorb a leftover section), and the failure this gate exists to catch looked nothing
like that — premature splits left non-final pages at 13-28%. So the threshold sits just
below the legitimate worst case: it still catches a genuinely under-filled page while
tolerating a normal section boundary.

    python scripts/gen_samples.py
    node web/scripts/measure_pages.mjs output/tmp > output/tmp/metrics.json
    python scripts/summarize_metrics.py
"""
import io
import json

MIN_FILL_PCT = 74

data = json.load(io.open("output/tmp/metrics.json", encoding="utf-8"))
print("file                      pages  per-page fill% (overflowPx if clipped)")
clipped = []
thin_pages = []
for name, pages in sorted(data.items()):
    cells = []
    for p in pages:
        cell = f"{p['fillPct']}%"
        if p["overflowPx"]:
            cell += f"!+{p['overflowPx']}"
        cells.append(cell)
    flag = ""
    if any(p["overflowPx"] > 2 for p in pages):
        flag = "  <-- OVERFLOW"
        clipped.append(name)
    # 非末页太空，说明这一页被过早切断（末页天然可能不满）。
    for index, p in enumerate(pages[:-1]):
        if p["fillPct"] < MIN_FILL_PCT:
            thin_pages.append(f"{name} p{index + 1} {p['fillPct']}%")
    print(f"{name:<22}{len(pages):>5}  {' '.join(cells)}{flag}")

pages_total = sum(len(v) for v in data.values())
print()
print(f"renders {len(data)}  pages {pages_total}  " f"single-page {sum(1 for v in data.values() if len(v) == 1)}")
print(f"clipped renders: {len(clipped)}{' -> ' + ', '.join(clipped) if clipped else ''}")
print(f"under-filled non-final pages: {len(thin_pages)}"
      + (" -> " + ", ".join(thin_pages[:8]) + (" …" if len(thin_pages) > 8 else "") if thin_pages else ""))
