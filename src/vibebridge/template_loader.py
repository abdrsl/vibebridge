"""Serves the main MyCompany WebUI template from a file for easier maintenance."""
from fastapi.responses import HTMLResponse
from pathlib import Path

_TEMPLATE = Path(__file__).parent / "templates" / "index.html"

def serve_webui():
    if _TEMPLATE.exists():
        content = _TEMPLATE.read_text(encoding="utf-8")
    else:
        content = "<h1>MyCompany WebUI</h1><p>Template not found. Run: mycompany start</p>"
    return HTMLResponse(content=content)
