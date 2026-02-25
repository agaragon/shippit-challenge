from __future__ import annotations

import sys
import pathlib

# Ensure the backend directory is importable when pytest is run from anywhere.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from suppliers import load_products, SUPPLIERS


# ---------------------------------------------------------------------------
# Shared helper (used by test_agents.py and test_main.py directly)
# ---------------------------------------------------------------------------

def fake_completion(content: str) -> MagicMock:
    """Return a minimal mock of an OpenAI ChatCompletion response."""
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def products():
    """Load and return all products from products.json."""
    return load_products()


@pytest.fixture
def suppliers():
    """Return the 3 hardcoded SupplierProfile objects."""
    return list(SUPPLIERS)


@pytest.fixture
def quantities():
    """Default order quantities matching the spec (10k Pulse Pro, 5k each other)."""
    return {
        "FSH013": 10000,
        "FSH014": 5000,
        "FSH016": 5000,
        "FSH019": 5000,
        "FSH021": 5000,
    }


@pytest.fixture(autouse=True)
def mock_openai():
    """
    Auto-used: patches agents._get_client for every test so no test can
    accidentally reach the real OpenAI API.  Tests that configure specific
    LLM responses receive the mock client via fixture injection.
    """
    client = AsyncMock()
    client.chat.completions.create.return_value = fake_completion("Mocked LLM response.")
    with patch("agents._get_client", return_value=client):
        yield client
