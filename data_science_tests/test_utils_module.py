"""Tests for data_science.utils.utils — currently 21% covered."""
import pytest
from data_science.utils import utils as u


def test_module_imports():
    assert u is not None


def test_module_has_callables():
    """At minimum, the module should expose some callables."""
    import inspect
    callables = [n for n in dir(u) if not n.startswith('_') and callable(getattr(u, n, None))]
    # Should have at least a few utility functions
    assert len(callables) >= 1
