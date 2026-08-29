from pathlib import Path

def test_agents_file_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "AGENTS.md").exists()

def test_documentation_directories_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    for folder in ("prd", "specs", "adrs"):
        assert (root / "docs" / folder).exists()
