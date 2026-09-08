import json


def parse_tags(value: str | None) -> list[str]:
    try:
        result = json.loads(value or "[]")
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


def score_item(item, target_tags: set[str]) -> tuple[int, list[str]]:
    item_tags = set(parse_tags(item.tags))
    matches = sorted(item_tags & target_tags)
    return len(matches), matches


def recommend(items, target_tags: set[str], limit: int | None = None):
    ranked = []
    for item in items:
        score, matches = score_item(item, target_tags)
        ranked.append((score, -getattr(item, "sort_order", 0), item, matches))
    ranked.sort(key=lambda value: (value[0], value[1]), reverse=True)
    if limit:
        ranked = ranked[:limit]
    return ranked

