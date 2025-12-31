import pytest
import sys
import os
import pkgutil
import importlib.util
import types

# Compatibility: Python versions where pkgutil.get_loader was removed
if not hasattr(pkgutil, 'get_loader'):
    def _get_loader(name):
        spec = importlib.util.find_spec(name)
        return spec.loader if spec is not None else None
    pkgutil.get_loader = _get_loader

# Ensure project root is on sys.path so tests can import `app`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_index(client):
    resp = client.get('/')
    assert resp.status_code in (200, 302)
