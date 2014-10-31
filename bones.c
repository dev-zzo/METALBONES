#include <Python.h>

#include "internals.h"

/* Externals from other files */
int init_DebuggerType(PyObject* m);

/* NT status exception */
PyObject *NtStatusError;

/* Module method definitions */
static PyMethodDef bones_methods[] = {
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif

PyMODINIT_FUNC
initbones(void) 
{
    PyObject* m;

    m = Py_InitModule3(
        "bones",
        bones_methods,
        "A simple Win32/Win64 debugger module.");

    NtStatusError = PyErr_NewException("bones.NtStatusError", NULL, NULL);
    Py_INCREF(NtStatusError);
    PyModule_AddObject(m, "NtStatusError", NtStatusError);

    init_DebuggerType(m);
}
