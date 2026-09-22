from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def schema() -> Path:
    return REPO_ROOT / "src" / "schema" / "glossary.yaml"


@pytest.fixture
def fixture_definitions() -> list[Path]:
    return sorted((FIXTURES / "definitions").glob("*.yaml"))


@pytest.fixture
def fixture_agents() -> Path:
    return FIXTURES / "agents.yaml"


@pytest.fixture
def fixture_content() -> Path:
    return FIXTURES / "content"


@pytest.fixture
def glossary(fixture_definitions, fixture_agents):
    from glossary_site.model import load

    return load(
        fixture_definitions,
        fixture_agents,
        FIXTURES,
        prefixes={"unmc": "https://w3id.org/unmc/glossary/"},
    )
