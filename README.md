AddTypes: Auto-generate PEP-484 annotations
===========================================

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

This installs both halves of the tool:

- A runtime module, addtypes_runtime/collect_types.py, which collects
  and dumps types observed at runtime using a profiling hook.

- A tool, scripts/annotate.sh that takes the collected types and
  inserts them into your source code.  This script just invokes
  addtypes_tools/annotations/main.py to do the work.

Testing etc.
------------

```
pytest
```
