from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "prd": ("PRD", {"## Objetivo"}),
    "specs": ("SPEC", {"## Objetivo", "## Critérios de aceite"}),
    "adrs": ("ADR", {"## Status", "## Decisão", "## Alternativas consideradas", "## Consequências"}),
}
errors = []

for folder, (prefix, headings) in RULES.items():
    path = ROOT / "docs" / folder
    docs = sorted(path.glob("*.md")) if path.exists() else []
    if not docs:
        errors.append(f"No docs in {path}")
        continue
    seen = set()
    for file in docs:
        text = file.read_text(encoding="utf-8")
        m = re.match(rf"{prefix.lower()}-(\d{{3}})-", file.name)
        if not m:
            errors.append(f"{file}: invalid filename")
            continue
        num = m.group(1)
        if num in seen:
            errors.append(f"{file}: duplicate {prefix}-{num}")
        seen.add(num)
        if not text.startswith(f"# {prefix}-{num}"):
            errors.append(f"{file}: invalid first heading")
        for heading in headings:
            if heading not in text:
                errors.append(f"{file}: missing {heading}")

if errors:
    print("Documentation validation failed:")
    for e in errors:
        print(f"- {e}")
    sys.exit(1)

print("Documentation validation passed.")
