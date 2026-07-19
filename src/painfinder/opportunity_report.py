from __future__ import annotations

from html import escape
from pathlib import Path

from painfinder.domain import SourceItem
from painfinder.opportunities import OpportunityCluster


def write_opportunity_report(
    output: Path,
    *,
    items: list[SourceItem],
    clusters: list[OpportunityCluster],
) -> None:
    cards = []
    for rank, cluster in enumerate(clusters, start=1):
        excerpts = "".join(
            f"<li>{escape(excerpt)}</li>" for excerpt in cluster.sample_excerpts
        )
        cards.append(
            "<section class='card'>"
            f"<div class='rank'>#{rank}</div>"
            f"<h2>{escape(cluster.label)}</h2>"
            f"<p class='score'>Opportunity score: {cluster.score:.1f}/100</p>"
            "<dl>"
            f"<dt>Evidence</dt><dd>{cluster.evidence_count} independent item(s)</dd>"
            f"<dt>Communities</dt><dd>{cluster.independent_communities}</dd>"
            f"<dt>Average confidence</dt><dd>{cluster.average_confidence:.2f}</dd>"
            f"<dt>Categories</dt><dd>{escape(', '.join(cluster.categories))}</dd>"
            "</dl>"
            f"<ul>{excerpts}</ul>"
            "</section>"
        )

    empty_state = ""
    if not cards:
        empty_state = (
            "<p class='empty'>No candidate opportunity clusters were detected. "
            "Review the imported evidence and detection rules.</p>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reddit Pain Finder — Opportunity Discovery</title>
<style>
body {{
  font-family: system-ui, sans-serif;
  max-width: 1100px;
  margin: 40px auto;
  padding: 0 20px;
  background: #f5f6f8;
  color: #1f2937;
}}
header, .card {{
  background: white;
  border: 1px solid #d9dde5;
  border-radius: 14px;
  padding: 24px;
  margin-bottom: 18px;
}}
h1, h2 {{ margin-top: 0; }}
.card {{ position: relative; }}
.rank {{
  position: absolute;
  right: 20px;
  top: 20px;
  font-weight: 700;
  color: #667085;
}}
.score {{ font-size: 1.1rem; font-weight: 700; }}
dl {{ display: grid; grid-template-columns: 180px 1fr; gap: 6px 16px; }}
dt {{ font-weight: 700; }}
dd {{ margin: 0; }}
li {{ margin-bottom: 8px; }}
.empty {{ background: white; padding: 24px; border-radius: 14px; }}
</style>
</head>
<body>
<header>
<h1>Opportunity Discovery Report</h1>
<p>Imported source items: {len(items)} · Candidate clusters: {len(clusters)}</p>
<p>Scores prioritize evidence for review. They do not prove market demand.</p>
</header>
{empty_state}
{"".join(cards)}
</body>
</html>"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
