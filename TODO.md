
Use Cases:
==========

Question: should we always default to pyhon2 annotations, or should we
          choose annotation style depending on the version of python running
          pyannotate ?

1. Annotate python 2 code:
	- code is strong python 2  (uses print >>foo, "bar" and other python2-ities)
	- annotations should be generated for python 2 (comments)
	- pyannotate may be run with python 2 or python 3, but most likely python 2
	- we have a match version of python executing pyannotate, annotation style to generate

2. Annotate python 3 code:
	- code is strong python 3 (uses py3 type annotations, { **d }, ... )
	- annotations should be generated for python 3
	- pyannotate may be run with python 2 or python 3, but most likely python 3
	- we have a match version of python executing pyannotate, annotation style to generate

3. Annotate python 2-3 code:
	- code is compatible with both python 2 and 3 (uses six package)
	- annotations should be generated for python 2 (comments)
	- pyannotate may be run with python 2 or python 3, nothing is most likely
	- no match a between version of python executing pyannotate and annotation style to generate
	- could be pyannotate run with python 3, generating python 2 style annotations

4. 
    a. Convert python 2 annotations to python 3
	- run pyannotate in special mode:
		+ collect existing py2 type annotations
		+ remove py2 type annotations
		+ add py3 type annotations
	note: this assume that pyannotate can read annotations from multiple sources, like
	      default values, python 2 annotations and type_info.json
	- pyannotate may be run with python 2 or python 3, but most likely python 2


    b. Convert python 3 annotations to python 2
	- do the opposite of 4.a.
	- pyannotate may be run with python 2 or python 3, but most likely python 3



NOTES:
======
- understand why there is a mode to annotate with Any / Any
- def test_return_expr_not_none(self): why not return Optional[int]
- when argument annotation is invalid, should we still annotate for return type
- no long form for py3 type annotations


TODO Short Term:
================
- [x] command-line argument for python 3 mode
- [x] merge pyannotate3 into pyannotate
- [x] convert test_annotate_json.py to test_annotate_json_py3
- [x] rename test_annotate[3] to _py2 and py3 versions
- [x] annnotation + default value: add space aroundt the '='
- [x] list use cases


TODO Middle-term:
=================
- [ ] add code coverage reporting
- [ ] add type annotation
- [ ] verify code with mypy in strict mode
- [ ] improve documentation
- [ ] support python 3 code
- [ ] provide scripts with shorter names and easier to use imports


TODO Long Term:
===============
- [ ] fix tests related to stderr in pyannotate_tools/tests/dundermain_test.py 
- [ ] current fixer does not detect new style classes
- [ ] only Any is added at the start of the import statements
- [ ] in python3 mode, type unicode should be str
- [ ] add a fixer for 2to3
- [ ] add a plugin for PyCharm
- [ ] convert annotations to python 3 style
- [ ] accept multiple sources of annotations info
- [ ] extend the default value analysis for annotations



