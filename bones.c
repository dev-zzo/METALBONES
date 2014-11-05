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

    rv = PyType_Ready(&PyBones_Debugger_Type);
    if (rv < 0) {
    }
    Py_INCREF(&PyBones_Debugger_Type);
    PyModule_AddObject(m, "Debugger", (PyObject *)&PyBones_Debugger_Type);

    rv = PyType_Ready(&PyBones_Thread_Type);
    if (rv < 0) {
    }
    Py_INCREF(&PyBones_Thread_Type);
    PyModule_AddObject(m, "Thread", (PyObject *)&PyBones_Thread_Type);

    rv = PyType_Ready(&PyBones_Process_Type);
    if (rv < 0) {
    }
    Py_INCREF(&PyBones_Process_Type);
    PyModule_AddObject(m, "Process", (PyObject *)&PyBones_Process_Type);

    PyBones_Context_Type.tp_new = PyType_GenericNew;
    rv = PyType_Ready(&PyBones_Context_Type);
    if (rv < 0) {
    }
    Py_INCREF(&PyBones_Context_Type);
    PyModule_AddObject(m, "Context", (PyObject *)&PyBones_Context_Type);

    DEBUG_PRINT("METALBONES core loaded.\n");
}
