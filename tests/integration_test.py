"""Some things you just can't test as unit tests"""

import os
import subprocess
import sys
import tempfile
import unittest


example = """
def main():
    print(gcd(15, 10))
    print(gcd(45, 12))

def gcd(a, b):
    while b:
        a, b = b, a%b
    return a
"""

driver = """
from pyannotate_runtime import collect_types

if __name__ == '__main__':
    collect_types.init_types_collection()
    with collect_types.collect():
        main()
    collect_types.dump_stats('type_info.json')
"""


class IntegrationTest(unittest.TestCase):

    def setUp(self):
        self.savedir = os.getcwd()
        os.putenv('PYTHONPATH', self.savedir)
        self.tempdir = tempfile.mkdtemp()
        os.chdir(self.tempdir)

    def tearDown(self):
        os.chdir(self.savedir)

    def test_simple(self):
        with open('gcd.py', 'w') as f:
            f.write(example)
        with open('driver.py', 'w') as f:
            f.write('from gcd import main\n')
            f.write(driver)
        subprocess.check_call([sys.executable, 'driver.py'])
        output = subprocess.check_output([sys.executable, '-m', 'pyannotate_tools.annotations', 'gcd.py'])
        lines = output.splitlines()
        assert b'+    # type: () -> None' in lines
        assert b'+    # type: (int, int) -> int' in lines

    def test_package(self):
        os.makedirs('foo')
        with open('foo/__init__.py', 'w') as f:
            pass
        with open('foo/gcd.py', 'w') as f:
            f.write(example)
        with open('driver.py', 'w') as f:
            f.write('from foo.gcd import main\n')
            f.write(driver)
        subprocess.check_call([sys.executable, 'driver.py'])
        output = subprocess.check_output([sys.executable, '-m', 'pyannotate_tools.annotations', 'foo/gcd.py'])
        lines = output.splitlines()
        assert b'+    # type: () -> None' in lines
        assert b'+    # type: (int, int) -> int' in lines

    @unittest.skip("Doesn't work yet")
    def test_subdir(self):
        os.makedirs('foo')
        with open('foo/gcd.py', 'w') as f:
            f.write(example)
        with open('driver.py', 'w') as f:
            f.write('import sys\n')
            f.write('sys.path.insert(0, "foo")\n')
            f.write('from gcd import main\n')
            f.write(driver)
        subprocess.check_call([sys.executable, 'driver.py'])
        output = subprocess.check_output([sys.executable, '-m', 'pyannotate_tools.annotations', 'foo/gcd.py'])
        lines = output.splitlines()
        assert b'+    # type: () -> None' in lines
        assert b'+    # type: (int, int) -> int' in lines
