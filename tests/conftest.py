from jinja2 import Environment, FileSystemLoader
from jinja_super_macros import configure_environment
import os
import pytest


@pytest.fixture()
def templates_path():
    return os.path.join(os.path.dirname(__file__), "templates")


@pytest.fixture()
def env(templates_path):
    env = Environment(loader=FileSystemLoader(templates_path))
    configure_environment(env)
    return env