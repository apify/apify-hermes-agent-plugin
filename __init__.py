"""Hermes plugin entry point for apify.

Thin shim: Hermes' native (git-clone) plugin loader imports ``<plugin-dir>/__init__.py``
directly; the real implementation is the PyPI-distributed ``apify_hermes_agent_plugin``
package under ``src/``, so this just re-exports its ``register()``. A ``pip install
apify-hermes-agent-plugin`` install never touches this file — it resolves the
``hermes_agent.plugins`` entry point in ``pyproject.toml`` directly.
"""

try:
    # Hermes loads directory plugins as a synthetic package rooted at the repo root, so this
    # reaches the bundled implementation under src/.
    from .src.apify_hermes_agent_plugin import register
except ImportError:
    # Keep working for a direct pip/editable install, where the package is import-root-level.
    from apify_hermes_agent_plugin import register

__all__ = ["register"]
