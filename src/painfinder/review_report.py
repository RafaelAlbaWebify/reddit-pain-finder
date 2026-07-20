from __future__ import annotations

from html import escape
from pathlib import Path

from painfinder.domain import SourceItem
from painfinder.review import ReviewedCluster


def write_review_report(
    output: Path,
    *,
    items: list[SourceItem],
    reviewed: dict[str, ReviewedCluster],
) -> None:
    items_by_id = {item.external_id: item for item in items}
    cards: list[str] = []

    for key, value in sorted(
        reviewed.items(),
        key=lambda entry: (-entry[1].cluster.score, entry[1].cluster.label),
    ):
        cluster = value.cluster
        sources = "".join(
            _source_link(source_id, items_by_id)
            for source_id in cluster.source_ids
        )
        annotations = "".join(
            f"<dt>{escape(field.replace('_', ' ').title())}</dt>"
            f"<dd>{escape(annotation)}</dd>"
            for field, annotation in sorted(value.annotations.items())
        )
        derived = ", ".join(value.derived_from) or key
        cards.append(
            "<section class='card'>"
            f"<h2>{escape(cluster.label)}</h2>"
            f"<p><strong>Status:</strong> {escape(value.status.value)}</p>"
            f"<p><strong>Score:</strong> {cluster.score:.1f}/100</p>"
            f"<p><strong>Derived from:</strong> {escape(derived)}</p>"
            f"<p><strong>Categories:</strong> "
            f"{escape(', '.join(cluster.categories))}</p>"
            f"<p><strong>Evidence:</strong> {cluster.evidence_count} unique source item(s)</p>"
            f"<dl>{annotations}</dl>"
            f"<ul>{sources}</ul>"
            "</section>"
        )

    empty = ""
    if not cards:
        empty = "<p class='empty'>No reviewed clusters are available.</p>"

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reddit Pain Finder — Reviewed Opportunities</title>
<style>
body {{
  font-family: system-ui, sans-serif;
  max-width: 1100px;
  margin: 40px auto;
  padding: 0 20px;
  background: #f5f6f8;
  color: #1f2937;
}}
header, .card, .empty {{
  background: white;
  border: 1px solid #d9dde5;
  border-radius: 14px;
  padding: 24px;
  margin-bottom: 18px;
}}
h1, h2 {{ margin-top: 0; }}
dl {{ display: grid; grid-template-columns: 180px 1fr; gap: 6px 16px; }}
dt {{ font-weight: 700; }}
dd {{ margin: 0; }}
li {{ margin-bottom: 8px; }}
</style>
</head>
<body>
<header>
<h1>Reviewed Opportunity Report</h1>
<p>Machine-generated clusters are shown with append-only analyst decisions.</p>
<p>Accepted status is an analyst judgment, not proof of market demand.</p>
</header>
{empty}
{"".join(cards)}
</body>
</html>"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def _source_link(source_id: str, items_by_id: dict[str, SourceItem]) -> str:
    item = items_by_id.get(source_id)
    if item is None:
        return f"<li>{escape(source_id)} — source record unavailable</li>"
    return (
        "<li>"
        f"<a href='{escape(str(item.canonical_url), quote=True)}'>"
        f"{escape(source_id)}</a> — {escape(item.title or item.body[:100])}"
        "</li>"
    )
