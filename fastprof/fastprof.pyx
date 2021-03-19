from cpython.ref cimport PyObject

import sys
import threading

what_names = ["call", "exception", "line", "return", "c_call", "c_exception", "c_return"]

cdef extern from "frameobject.h":
    struct _frame:
        # The only frame attribute we need
        PyObject *f_code

cdef extern from "pystate.h":
    ctypedef int Py_tracefunc(object self, _frame* frame, int what, object arg)

cdef extern from "ceval.h":
    void PyEval_SetProfile(Py_tracefunc func, object arg)

callback = None
counters = {}  # A counter per code object

cdef int c_callback(self, _frame* frame, int what, arg):
    # We only care about 'call' and 'return'.
    if what != 0 and what != 3:
        return 0
    # Set/update the counter for this code object.
    code = <object>(frame.f_code)
    cdef int n = 0
    # TODO: Is this thread-safe? (I.e. does Cython release the GIL?)
    if code in counters:
        n = counters[code]
    counters[code] = n + 1
    # Call callback for first 5 calls and then every millionth call.
    if n < 5 or n%1000000 == 0:
        # Due to race conditions, callback may be None here.
        cb = callback
        if cb is not None:
            cb(<object>frame, what_names[what], arg)
    return 0

def threading_bootstrap(*args):
    # In order to set the sampling callback in a thread, we register
    # this function as the threading profile hook.  The first time the
    # hook is called it deregisters itself and sets the sampling
    # callback.  See setprofile() in threading.py in the stdlib.
    sys.setprofile(None)
    PyEval_SetProfile(c_callback, None)

def enable(cb):
    assert cb is not None, "Call disable() to disable profiling"
    global callback
    callback = cb
    PyEval_SetProfile(c_callback, None)
    threading.setprofile(threading_bootstrap)

def disable():
    global callback
    callback = None
    sys.setprofile(None)
    threading.setprofile(None)

def get_counter():
    return sum(counters.values())

def reset_counter():
    counters.clear()
