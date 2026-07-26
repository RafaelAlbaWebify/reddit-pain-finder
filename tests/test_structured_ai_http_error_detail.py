from __future__ import annotations

import io
import urllib.error

from painfinder.structured_ai_http import _http_error_detail


def test_http_error_detail_reads_nested_server_body() -> None:
    http_error = urllib.error.HTTPError(
        url="http://127.0.0.1:11434/v1/chat/completions",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"model runner crashed"}'),
    )
    wrapped = RuntimeError("request failed")
    wrapped.__cause__ = http_error

    assert _http_error_detail(wrapped) == '{"error":"model runner crashed"}'
