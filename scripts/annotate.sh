#!/bin/sh

if [ ! -f type_info.json ]; then
    echo "There's no type_info.json file!  To create one:"
    echo "  1) ./run-box.py --collect-types"
    echo "  2) Select [tray] > [wheel] > Debug > Runtime Type information > Start collection"
    echo "  3) Do some stuff that exercises the client"
    echo "  4) Select [tray] > [wheel] > Debug > Runtime Type information > Dump types and pause collection"
    echo "Then run this script again, with the files you want to annotate as arguments."
    exit 1
fi

: ${SERVER=../server}
MAIN=$SERVER/dropbox/annotations/__main__.py

if [ ! -d $SERVER -o ! -f $MAIN ]; then
    echo "Expected a server repo at $SERVER"
    exit 1
fi

python -m pip install -q virtualenv

VENV=ci/venv-annotate
PYTHON=$VENV/bin/python

if [ ! -d $VENV -o ! -f $PYTHON ]; then
    python -m virtualenv $VENV
fi

$PYTHON -m pip -q install 'typing>=3.6.2' 'typing_extensions>=3.6.2' 'mypy_extensions>=0.3.0'

export PYTHONPATH=$SERVER

$PYTHON $MAIN -p -q "$@"
