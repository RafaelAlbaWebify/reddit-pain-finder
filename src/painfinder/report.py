from __future__ import annotations

from html import escape
from pathlib import Path

from painfinder.domain import PainSignal, SourceItem


def write_html_report(
    output: Path,
    items: list[SourceItem],
    signals: list[PainSignal],
) -> None:
    by_id = {item.external_id: item for item in items}
    rows = []
    for signal in signals:
        source = by_id[signal.source_external_id]
        rows.append(
            "<tr>"
            f"<td>{escape(signal.category.value)}</td>"
            f"<td>{signal.confidence:.2f}</td>"
            f"<td>{escape(signal.excerpt)}</td>"
            f"<td>{escape('; '.join(signal.reasons))}</td>"
            f'<td><a href="{escape(str(source.canonical_url))}">source</a></td>'
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Reddit Pain Finder — Fixture Evidence Report</title>
<style>
body {{
  font-family: system-ui, sans-serif;
  max-width: 1200px;
  margin: 40px auto;
  padding: 0 20px;
}}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{
  border: 1px solid #ccc;
  padding: 10px;
  text-align: left;
  vertical-align: top;
}}
.warning {{
  padding: 12px;
  background: #fff3cd;
  border: 1px solid #ffe69c;
}}
</style>
</head>
<body>
<h1>Fixture Evidence Report</h1>
<p class="warning">
This report was produced from a local test fixture,
not a verified live Reddit collection.
</p>
<p>Source items: {len(items)} · Candidate pain signals: {len(signals)}</p>
<table>
<thead>
<tr>
<th>Category</th><th>Confidence</th><th>Evidence</th>
<th>Reasons</th><th>Link</th>
</tr>
</thead>
<tbody>{"".join(rows)}</tbody>
</table>
</body>
</html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
