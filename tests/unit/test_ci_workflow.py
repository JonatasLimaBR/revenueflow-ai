from pathlib import Path

_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "terraform.yml"


def test_push_trigger_covers_every_dockerfile_copy_source() -> None:
    # Real production gap (2026-09-06): the deploy job builds and pushes a
    # new image on every push to main, but the path filter only covered
    # src/ — scripts/, migrations/ and seeds/ are COPYed into the image too
    # (Dockerfile) yet weren't in the filter, so a scripts-only fix (PR #74)
    # merged to main without ever triggering a rebuild/redeploy.
    body = _WORKFLOW.read_text()
    push_block = body.split("push:", 1)[1].split("workflow_dispatch:", 1)[0]
    for path in (
        '"Dockerfile"',
        '"pyproject.toml"',
        '"src/**"',
        '"scripts/**"',
        '"migrations/**"',
        '"seeds/**"',
    ):
        assert path in push_block, f"{path} missing from the push trigger's path filter"


def test_dockerfile_copy_sources_match_the_trigger() -> None:
    # The inverse check: every directory the Dockerfile COPYs from the repo
    # root has a matching entry in the push trigger above — keeps the two
    # lists from drifting apart again the way they just did.
    dockerfile = (_WORKFLOW.parents[2] / "Dockerfile").read_text()
    copied_dirs = {
        line.split()[1].rstrip("/")
        for line in dockerfile.splitlines()
        if line.startswith("COPY ") and not line.split()[1].endswith((".toml", ".txt", ".lock"))
    }
    push_block = _WORKFLOW.read_text().split("push:", 1)[1].split("workflow_dispatch:", 1)[0]
    for d in copied_dirs:
        assert (
            f'"{d}/**"' in push_block
        ), f"Dockerfile COPYs {d}/ but the push trigger doesn't watch it"
