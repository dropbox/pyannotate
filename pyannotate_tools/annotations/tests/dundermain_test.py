"""Some (nearly) end-to-end testing."""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest

# There seems to be no way to have this work and type-check without an
# explicit version check. :-(
if sys.version_info[0] == 2:
    from cStringIO import StringIO
else:
    from io import StringIO

from typing import Iterator, List

from pyannotate_tools.annotations.__main__ import main as dunder_main


class TestDunderMain(unittest.TestCase):
    def setUp(self):
        # type: () -> None
        self.tempdirname = tempfile.mkdtemp()
        self.tempfiles = []  # type: List[str]
        self.olddir = os.getcwd()
        os.chdir(self.tempdirname)

    def tearDown(self):
        # type: () -> None
        os.chdir(self.olddir)
        shutil.rmtree(self.tempdirname)

    def write_file(self, name, data):
        # type: (str, str) -> None
        self.tempfiles.append(name)
        with open(name, 'w') as f:
            f.write(data)
    
    def test_help(self):
        # type: () -> None
        self.main_test(["--help"], r"^usage:", r"^$", 0)

    def test_preview(self):
        # type: () -> None
        self.prototype_test(write=False)

    def test_final(self):
        # type: () -> None
        self.prototype_test(write=True)
        with open('gcd.py') as f:
            lines = [line.strip() for line in f.readlines()]
        assert '# type: (int, int) -> int' in lines

    def test_bad_encoding_message(self):
        # type: () -> None
        source_text = "# coding: unknownencoding\ndef f():\n  pass\n"
        self.write_file('gcd.py', source_text)
        self.write_file('type_info.json', '[]')
        encoding_message = "Can't parse gcd.py: unknown encoding: unknownencoding"
        self.main_test(['gcd.py'],
                       r'\A\Z',
                       r'\A' + re.escape(encoding_message),
                       0)

    def prototype_test(self, write):
        # type: (bool) -> None
        type_info = [
            {
                "path": "gcd.py",
                "line": 1,
                "func_name": "gcd",
                "type_comments": [
                    "(int, int) -> int"
                ],
                "samples": 2
            }
        ]
        source_text = """\
def gcd(a, b):
    while b:
        a, b = b, a%b
    return a
"""
        stdout_expected = """\
--- gcd.py	(original)
+++ gcd.py	(refactored)
@@ -1,4 +1,5 @@
 def gcd(a, b):
+    # type: (int, int) -> int
     while b:
         a, b = b, a%b
     return a
"""
        if not write:
            stderr_expected = """\
Refactored gcd.py
Files that need to be modified:
gcd.py
NOTE: this was a dry run; use -w to write files
"""
        else:
            stderr_expected = """\
Refactored gcd.py
Files that were modified:
gcd.py
"""
        self.write_file('type_info.json', json.dumps(type_info))
        self.write_file('gcd.py', source_text)
        args = ['gcd.py']
        if write:
            args.append('-w')
        self.main_test(args,
                       re.escape(stdout_expected) + r'\Z',
                       re.escape(stderr_expected) + r'\Z',
                       0)

    def main_test(self, args, stdout_pattern, stderr_pattern, exit_code):
        # type: (List[str], str, str, int) -> None
        save_stdout = sys.stdout
        save_stderr = sys.stderr
        stdout = StringIO()
        stderr = StringIO()
        try:
            sys.stdout = stdout
            sys.stderr = stderr
            dunder_main(args)
            code = 0
        except SystemExit as err:
            code = err.code
        finally:
            sys.stdout = save_stdout
            sys.stderr = save_stderr
        stdout_value = stdout.getvalue()
        stderr_value = stderr.getvalue()
        assert re.match(stdout_pattern, stdout_value)
        match = re.match(stderr_pattern, stderr_value)
        ## if not match: print("\nNah")
        ## else: print("\nYa!")
        ## print(stderr_value)
        ## import pdb; pdb.set_trace()
        assert code == exit_code
