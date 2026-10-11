import pytest

from src import checks, config, simulate


@pytest.fixture(scope="session")
def raw_tables(tmp_path_factory):
    """Simulate once into a temporary folder and load it like the real pipeline does."""
    old = config.DATA_DIR
    config.DATA_DIR = tmp_path_factory.mktemp("data")
    simulate.save(simulate.simulate())
    t = simulate.load()
    config.DATA_DIR = old
    return t


@pytest.fixture(scope="session")
def tables(raw_tables):
    t, _ = checks.run_checks(raw_tables)
    return t
