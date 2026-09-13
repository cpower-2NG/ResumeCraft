import io
import json

data = json.load(io.open("output/tmp/metrics.json", encoding="utf-8"))
print("file                      pages  per-page fill% (overflowPx if clipped)")
for name, pages in sorted(data.items()):
    cells = []
    for p in pages:
        cell = f"{p['fillPct']}%"
        if p["overflowPx"]:
            cell += f"!+{p['overflowPx']}"
        cells.append(cell)
    flag = "  <-- OVERFLOW" if any(p["overflowPx"] > 2 for p in pages) else ""
    print(f"{name:<22}{len(pages):>5}  {' '.join(cells)}{flag}")
