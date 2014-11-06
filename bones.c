#include <Python.h>

#include "internal.h"

/* Win32 system error code exception */
PyObject *PyBones_Win32Error;

/* NT status exception */
PyObject *PyBones_NtStatusError;

/* Module method definitions */
static PyMethodDef methods[] = {
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif

static int
ready_add_type(PyObject* m, const char *name, PyTypeObject *t)
{
    int rv;

    rv = PyType_Ready(t);
    if (rv < 0)
        return rv;

    Py_INCREF(t);
    return PyModule_AddObject(m, name, (PyObject *)t);
}

PyMODINIT_FUNC
initbones(void) 
{
    PyObject* m;
    int rv;

    m = Py_InitModule3(
        "bones",
        methods,
        "A simple Win32 debugger module.");

    PyBones_Win32Error = PyErr_NewException("bones.Win32Error", NULL, NULL);
    Py_INCREF(PyBones_Win32Error);
    PyModule_AddObject(m, "Win32Error", PyBones_Win32Error);

    PyBones_NtStatusError = PyErr_NewException("bones.NtStatusError", NULL, NULL);
    Py_INCREF(PyBones_NtStatusError);
    PyModule_AddObject(m, "NtStatusError", PyBones_NtStatusError);

    ready_add_type(m, "Debugger", &PyBones_Debugger_Type);
    ready_add_type(m, "Thread", &PyBones_Thread_Type);
    ready_add_type(m, "Process", &PyBones_Process_Type);
    PyBones_Context_Type.tp_new = PyType_GenericNew;
    ready_add_type(m, "Context", &PyBones_Context_Type);
    ready_add_type(m, "Module", &PyBones_Module_Type);

    DEBUG_PRINT("METALBONES core loaded.\n");
}
