"""Self-contained, offline report. Embedded records cannot become HTML/script."""
import json
from importlib.resources import files
from pathlib import Path


def render(data, output):
    raw = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template = files("flightdeck").joinpath("report.html").read_text(encoding="utf-8")
    Path(output).write_text(template.replace("__FLIGHTDECK_DATA__", raw), encoding="utf-8")
