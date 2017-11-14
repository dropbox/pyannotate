from __future__ import absolute_import

from distutils.core import setup
from Cython.Build import cythonize

modules = cythonize('fastprof.pyx')

setup(name='fastprof',
      version='0.0',
      description="Package containing a sampling profile hook",
      ext_modules=modules,
      )
