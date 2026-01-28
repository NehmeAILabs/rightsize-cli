from __future__ import annotations

from pathlib import Path
from typing import Callable

from jinja2 import Environment


def load_template(path: Path) -> Callable[[str], str]:
    content = path.read_text()
    suffix = path.suffix.lower()
    if suffix in {".j2", ".jinja", ".jinja2"} or "{{" in content or "{%" in content:
        env = Environment(autoescape=False)
        template = env.from_string(content)
        return lambda input_data: template.render(input_data=input_data)
    return lambda input_data: content.format_map({"input_data": input_data})
