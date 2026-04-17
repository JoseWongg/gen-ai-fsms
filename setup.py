# setup.py
# Shim for legacy compatibility; not strictly needed if pyproject.toml is fully configured.
#
# For regular packaging in this project, use pyproject.toml.
# Modern setuptools projects can be configured directly in pyproject.toml,
#
# Keep or extend setup.py only if you need special scripted build behavior,
# legacy compatibility, or custom packaging logic that is not covered cleanly
# by the declarative pyproject.toml approach.
from setuptools import setup # Shim for legacy compatibility; not strictly needed if pyproject.toml is fully configured.
setup()

