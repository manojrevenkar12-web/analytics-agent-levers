import shutil

import helpers


def pytest_sessionfinish(session, exitstatus):
    if helpers.session.cache_info().currsize:
        s = helpers.session()
        s.close()
        shutil.rmtree(s.workdir, ignore_errors=True)
