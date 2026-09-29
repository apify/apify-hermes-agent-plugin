"""Hermes plugin entry point for apify.

Thin shim: Hermes' native (git-clone) plugin loader imports ``<plugin-dir>/__init__.py``
directly; the real implementation is the PyPI-distributed ``apify_hermes_agent_plugin``
package under ``src/``, so this just re-exports its ``register()``. A ``pip install
apify-hermes-agent-plugin`` install never touches this file — it resolves the
``hermes_agent.plugins`` entry point in ``pyproject.toml`` directly.

``src/apify_hermes_agent_plugin``'s own modules import each other by absolute name
(``from apify_hermes_agent_plugin.cli import ...``), matching a real pip install. Put
``src`` on ``sys.path`` before importing so those absolute imports resolve the same way
under Hermes' git-clone loader — the pin IS the code.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from apify_hermes_agent_plugin import register

__all__ = ["register"]
