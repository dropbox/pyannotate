# Configuration for pytest to automatically collect types.
# Thanks to Guilherme Salgado.

import pytest
from pyannotate_runtime import collect_types

collect_types.init_types_collection()


@pytest.fixture(autouse=True)
def collect_types_fixture():
    collect_types.resume()
    yield
    collect_types.pause()


def pytest_sessionfinish(session, exitstatus):
    collect_types.dump_stats("type_info.json")
