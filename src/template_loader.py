"""Serves the main MyCompany WebUI template from a file for easier maintenance."""
from fastapi.responses import HTMLResponse
from pathlib import Path

_TEMPLATE = Path(__file__).parent / "templates" / "index.html"
if _TEMPLATE.exists():
    _CONTENT = _TEMPLATE.read_text(encoding="utf-8")
else:
    _CONTENT = "<h1>MyCompany WebUI</h1><p>Template not found. Run: mycompany start</p>"

def serve_webui():
    return HTMLResponse(content=_CONTENT)
