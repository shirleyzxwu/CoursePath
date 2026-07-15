"""
tests/conftest.py

Sets the working directory to the project root before any tests run,
so that coursepath/planner.py can open "coursepath/data/courses.json"
with a relative path regardless of where pytest is invoked from.
"""

import os
import pytest

# Project root = one level above this file (tests/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def pytest_configure(config):
    os.chdir(PROJECT_ROOT)
