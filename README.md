PyAnnotate: Auto-generate PEP-484 annotations
=============================================

Insert annotations into your source code based on call arguments and
return types observed at runtime.

For license and copyright see the end of this file.

Blog post: http://mypy-lang.blogspot.com/2017/11/dropbox-releases-pyannotate-auto.html

How to use
==========

See also the example directory.

Phase 1: Collecting types at runtime
------------------------------------

- Install the usual way (see "red tape" section below)
- Add `from pyannotate_runtime import collect_types` to your test
- Early in your test setup, call `collect_types.init_types_collection()`
- Bracket your test execution between calls to `collect_types.start()` and
  `collect_types.stop()` (or use the context manager below)
- When done, call `collect_types.dump_stats(filename)`

All calls between the `start()` and `stop()` calls will be analyzed
and the observed types will be written (in JSON form) to the filename
you pass to `dump_stats()`.  You can have multiple start/stop pairs
per dump call.

If you'd like to automatically collect types when you run `pytest`,
see `example/example_conftest.py` and `example/README.md`.

Instead of using `start()` and `stop()` you can also use a context
manager:
```
collect_types.init_types_collection()
with collect_types.collect():
    <your code here>
collect_types.dump_stats(<filename>)
```

Phase 2: Inserting types into your source code
----------------------------------------------

The command-line tool `pyannotate` can add annotations into your
source code based on the annotations collected in phase 1.  The key
arguments are:

- Use `--type-info FILE` to tell it the file you passed to `dump_stats()`
- Positional arguments are source files you want to annotate
- With no other flags the tool will print a diff indicating what it
  proposes to do but won't do anything.  Review the output.
- Add `-w` to make the tool actually update your files.
  (Use git or some other way to keep a backup.)

At this point you should probably run mypy and iterate.  You probably
will have to tweak the changes to make mypy completely happy.

Notes and tips
--------------

- It's best to do one file at a time, at least until you're
  comfortable with the tool.
- The tool doesn't touch functions that already have an annotation.
- The tool can generate either of:
  - type comments, i.e. Python 2 style annotations
  - inline type annotations, i.e. Python 3 style annotations, using `--py3` in v1.0.7+

Red tape
========

Installation
------------

This should work for Python 2.7 as well as for Python 3.4 and higher.

```
pip install pyannotate
```

This installs several items:

- A runtime module, pyannotate_runtime/collect_types.py, which collects
  and dumps types observed at runtime using a profiling hook.

- A library package, pyannotate_tools, containing code that can read the
  data dumped by the runtime module and insert annotations into your
  source code.

- An entry point, pyannotate, which runs the library package on your files.

For dependencies, see setup.py and requirements.txt.

Testing etc.
------------

To run the unit tests, use pytest:

```
pytest
```

TO DO
-----

We'd love your help with some of these issues:

- Better documentation.
- Python 3 code generation.
- Refactor the tool modules (currently its legacy architecture shines through).

Acknowledgments
---------------

The following people contributed significantly to this tool:

- Tony Grue
- Sergei Vorobev
- Jukka Lehtosalo
- Guido van Rossum

Licence etc.
------------

1. License: Apache 2.0.
2. Copyright attribution: Copyright (c) 2017 Dropbox, Inc.
3. External contributions to the project should be subject to
   Dropbox's Contributor License Agreement (CLA):
   https://opensource.dropbox.com/cla/
