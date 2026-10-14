"""Print the derived palette of every builtin template.

Run after editing app/templates.py to review what the two colour rules produced:
the derived on-dark accent, and whether any dark-surface text role still sits
below MIN_CONTRAST.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.templates import BUILTIN_TEMPLATES, HAS_DARK_BAND, MIN_CONTRAST, RETIRED_TEMPLATES, contrast

DARK_ROLES = ("sidebar_fg", "sidebar_muted", "sidebar_heading", "on_dark_accent")


def main() -> None:
    print(f"模板 {len(BUILTIN_TEMPLATES)} 个，退役 {len(RETIRED_TEMPLATES)} 个\n")
    header = f"{'slug':<11}{'layout':<10}{'accent':<9}{'on_dark_accent':<16}{'on-dark':<9}{'accent/paper'}"
    print(header)
    print("-" * len(header))
    problems = 0
    for slug, d in BUILTIN_TEMPLATES.items():
        has_band = d["layout"] in HAS_DARK_BAND
        dark = contrast(d["on_dark_accent"], d["sidebar_bg"])
        paper = contrast(d["accent"], "#ffffff")
        flags = []
        if has_band and dark < MIN_CONTRAST:
            flags.append("on-dark!")
        if paper < MIN_CONTRAST:
            flags.append("paper!")
        problems += len(flags)
        on_dark = f"{dark:.2f}" if has_band else "—"
        print(f"{slug:<11}{d['layout']:<10}{d['accent']:<9}{d['on_dark_accent']:<16}{on_dark:<9}{paper:<6.2f}{' '.join(flags)}")
    print()
    print("深色面各角色的对比度（仅统计真正有深色文字面的版式，低于门槛的列出）：")
    low = [(slug, role, contrast(d[role], d["sidebar_bg"]))
           for slug, d in BUILTIN_TEMPLATES.items() if d["layout"] in HAS_DARK_BAND
           for role in DARK_ROLES if contrast(d[role], d["sidebar_bg"]) < MIN_CONTRAST]
    for slug, role, value in low:
        print(f"  {slug:<11}{role:<18}{value:.2f}")
    print("  （无）" if not low else "")
    print(f"\n共 {problems} 处不达 {MIN_CONTRAST}:1")


if __name__ == "__main__":
    main()
