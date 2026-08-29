import json
import re
import sys

payload = json.load(sys.stdin)
tool_input = payload.get("tool_input", {}) or {}
command = tool_input.get("command", "") or ""

BLOCK = [
    r"\bterraform\s+destroy\b",
    r"\bterraform\s+apply\b",
    r"\bgcloud\s+projects\s+delete\b",
    r"\bgcloud\s+sql\s+instances\s+delete\b",
    r"\bgcloud\s+run\s+services\s+delete\b",
    r"\bgcloud\s+storage\s+rm\b.*--recursive",
    r"\bgsutil\s+-m\s+rm\s+-r\b",
    r"\bgcloud\s+iam\s+service-accounts\s+delete\b",
    r"\bgcloud\s+projects\s+remove-iam-policy-binding\b",
    r"\bkubectl\s+delete\b.*\bnamespace\b",
]

for pattern in BLOCK:
    if re.search(pattern, command, flags=re.IGNORECASE | re.DOTALL):
        print(
            "BLOCKED: destructive/high-risk command. "
            "Require explicit human approval and execute manually if truly intended.",
            file=sys.stderr,
        )
        sys.exit(2)

sys.exit(0)
