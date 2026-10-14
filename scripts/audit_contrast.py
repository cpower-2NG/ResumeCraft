"""Check every colour role against the surface it is actually painted on.

Paper roles are checked against the white paper; dark-band roles against
``sidebar_bg``. Run before/after palette edits — a failure here means some text
is too faint to read, which is exactly the defect class this file exists for.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.templates import (BUILTIN_TEMPLATES, DARK_TOKENS, HAS_DARK_BAND, MIN_CONTRAST,
                           PAPER_TEXT_TOKENS, contrast)

PAPER = "#ffffff"


def main() -> None:
    failures = []
    for slug, d in BUILTIN_TEMPLATES.items():
        for token in PAPER_TEXT_TOKENS:
            value = contrast(d[token], PAPER)
            if value < MIN_CONTRAST:
                failures.append((slug, f"{token} on paper", d[token], PAPER, value))
        # 栏目标题坐在标题条底色上，这一对也要达标。
        value = contrast(d["heading"], d["tint"])
        if value < MIN_CONTRAST:
            failures.append((slug, "heading on tint", d["heading"], d["tint"], value))
        if d["layout"] in HAS_DARK_BAND:
            for token in DARK_TOKENS:
                if token == "sidebar_bg":
                    continue
                value = contrast(d[token], d["sidebar_bg"])
                if value < MIN_CONTRAST:
                    failures.append((slug, f"{token} on dark", d[token], d["sidebar_bg"], value))
    for slug, pair, fg, bg, value in failures:
        print(f"{slug:<11}{pair:<24}{fg:<9}on {bg:<9}{value:.2f}")
    print(f"\n{len(BUILTIN_TEMPLATES)} 个模板，{len(failures)} 处不达 {MIN_CONTRAST}:1")


if __name__ == "__main__":
    main()
