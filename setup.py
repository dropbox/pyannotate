#!/usr/bin/env python

from setuptools import setup

setup(name='addtypes',
      version='1.0.0',
      description="AddTypes: Auto-generate PEP-484 annotations",
      author='Dropbox',
      author_email='guido@dropbox.com',
      license='Apache 2.0',
      platforms=['POSIX'],
      packages=['addtypes_runtime', 'addtypes_tools', 'addtypes_tools.annotations', 'addtypes_tools.fixes'],
      entry_points={'console_scripts': ['addtypes=addtypes_tools.annotations.__main__:main']},
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Software Development',
          ],
      install_requires = ['six',
                          'mypy_extensions',
                          ],
      extras_require = {
          ':python_version < "3.5"': 'typing >= 3.5.3',
      },
      )
