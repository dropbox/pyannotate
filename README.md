AddTypes: Auto-generate PEP-484 annotations
===========================================

Insert annotations into your source code based on call arguments and
return types observed at runtime.

Licence etc.
------------

1. License: Apache 2.0.
2. Copyright attribution: Copyright (c) 2017 Dropbox, Inc.
3. External contributions to the project should be subject to
   Dropbox's Contributor License Agreement (CLA):
   https://opensource.dropbox.com/cla/

Installation etc.
-----------------

This should work for Python 2.7 as well as for Python 3.6 and higher.

```
pip install addtypes
```

This installs several items:

- A runtime module, addtypes_runtime/collect_types.py, which collects
  and dumps types observed at runtime using a profiling hook.

- A library package, addtypes_tools, containing code that can read the
  data dumped by the runtime module and insert annotations into your
  source code.

- An entry point, addtypes, which runs the library package on your files.

For dependencies, see setup.py and requirements.txt.

Testing etc.
------------

To run the unit tests, use pytest:

```
pytest
```
