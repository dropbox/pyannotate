#!/usr/bin/env python

import os
from setuptools import setup

def get_long_description():
    filename = os.path.join(os.path.dirname(__file__), 'README.md')
    with open(filename) as f:
        return f.read()

setup(name='pyannotate',
      version='1.2.0',
      description="PyAnnotate: Auto-generate PEP-484 annotations",
      long_description=get_long_description(),
      long_description_content_type="text/markdown",
      author='Dropbox',
      author_email='guido@dropbox.com',
      url='https://github.com/dropbox/pyannotate',
      license='Apache 2.0',
      platforms=['POSIX'],
      packages=['pyannotate_runtime', 'pyannotate_tools',
                'pyannotate_tools.annotations', 'pyannotate_tools.fixes'],
      entry_points={'console_scripts': ['pyannotate=pyannotate_tools.annotations.__main__:main']},
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Software Development',
          ],
      install_requires = ['six',
                          'mypy_extensions',
                          'typing >= 3.5.3; python_version < "3.5"'
                          ],
      )
