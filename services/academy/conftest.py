"""
Root conftest.py — ensures the 'qtown' proto package is importable.

The generated gRPC stubs live in academy/qtown/ and import each other
as ``from qtown import ...``. We add the academy package dir to sys.path
so Python can find the ``qtown`` package.
"""
import os
import sys

_academy_pkg = os.path.join(os.path.dirname(__file__), "academy")
if _academy_pkg not in sys.path:
    sys.path.insert(0, _academy_pkg)
