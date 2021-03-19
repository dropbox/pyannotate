import pytest


def pytest_addoption(parser):
    group = parser.getgroup("pyannotate")
    group.addoption(
        "--type-info",
        default="type_info.json",
        help="File to write type information to (default: %(default)s).")


def pytest_configure(config):
    if config.pluginmanager.hasplugin('xdist'):
        if config.getoption('dist') != 'no':
            print('Disabling xdist for pyannotate collection.')
            config.option.dist = 'no'


def pytest_collection_finish(session):
    """Handle the pytest collection finish hook: configure pyannotate.

    Explicitly delay importing `collect_types` until all tests have
    been collected.  This gives gevent a chance to monkey patch the
    world before importing pyannotate.
    """
    from pyannotate_runtime import collect_types
    collect_types.init_types_collection()


@pytest.fixture(autouse=True)
def collect_types_fixture():
    from pyannotate_runtime import collect_types
    collect_types.start()
    yield
    collect_types.stop()


def pytest_sessionfinish(session, exitstatus):
    from pyannotate_runtime import collect_types
    collect_types.dump_stats(session.config.option.type_info)
