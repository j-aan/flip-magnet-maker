"""Build index.html (stand-alone site, e.g. GitHub Pages) from src/flip-magnet.html.

The source file is written for claude.ai artifacts, which add the <html>/<head>
skeleton themselves. This wraps it so it also works as a normal web page.

    python build.py
"""
from pathlib import Path

ROOT = Path(__file__).parent
src = (ROOT / "src" / "flip-magnet.html").read_text(encoding="utf-8")
head = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    "<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>"
    "</head><body>\n"
)
(ROOT / "index.html").write_text(head + src + "\n</body></html>\n", encoding="utf-8")
print("wrote index.html")
