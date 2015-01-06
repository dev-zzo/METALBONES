#include <Python.h>
#include <Windows.h>

#include "internal.h"

/* Base class for our exceptions */
PyObject *PyBones_BonesException;

/* Win32 system error code exception */
PyObject *PyBones_Win32Error;

/* NT status exception */
PyObject *PyBones_NtStatusError;

/* Module method definitions */
static PyMethodDef methods[] = {
    {NULL}  /* Sentinel */
};

int
init_Debugger(PyObject* m);
int
init_Process(PyObject* m);

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif

void
_PyBones_RaiseNtStatusError(const char *file, int line, unsigned int status)
{
    char buffer[256];

    sprintf(buffer, "%s:%d: Caught a NTSTATUS: %p", file, line, status);
    PyErr_SetString(PyBones_NtStatusError, buffer);
}

void
_PyBones_RaiseWin32Error(const char *file, int line, unsigned int code)
{
    char msg_buffer[128];
    char buffer[256];
    unsigned count;
    char *end;

    count = FormatMessageA(
        FORMAT_MESSAGE_FROM_SYSTEM|FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        code,
        0,
        msg_buffer,
        sizeof(msg_buffer),
        NULL);
    if (count) {
        end = msg_buffer + count - 1;
        while (*end == '\n' || *end == '\r') {
            end--;
        }
        *end = '\0';
    }
    else {
        sprintf(msg_buffer, "<Failed to retrieve the message>");
    }

    sprintf(buffer, "%s:%d: %s", file, line, msg_buffer);
    PyErr_SetString(PyBones_Win32Error, buffer);
}

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
init_bones(void) 
{
    PyObject* m;

    m = Py_InitModule3(
        "_bones",
        methods,
        "A simple Win32 debugger module.");

    PyBones_BonesException = PyErr_NewException("_bones.BonesException", NULL, NULL);
    Py_INCREF(PyBones_BonesException);
    PyModule_AddObject(m, "BonesException", PyBones_BonesException);

    PyBones_Win32Error = PyErr_NewException("_bones.Win32Error", PyBones_BonesException, NULL);
    Py_INCREF(PyBones_Win32Error);
    PyModule_AddObject(m, "Win32Error", PyBones_Win32Error);

    PyBones_NtStatusError = PyErr_NewException("_bones.NtStatusError", PyBones_BonesException, NULL);
    Py_INCREF(PyBones_NtStatusError);
    PyModule_AddObject(m, "NtStatusError", PyBones_NtStatusError);

    init_Debugger(m);
    init_Process(m);
    ready_add_type(m, "Thread", &PyBones_Thread_Type);
    ready_add_type(m, "EFlags", &PyBones_EFlags_Type);
    PyBones_Context_Type.tp_new = PyType_GenericNew;
    ready_add_type(m, "Context", &PyBones_Context_Type);
    ready_add_type(m, "Module", &PyBones_Module_Type);
    ready_add_type(m, "ExceptionInfo", &PyBones_ExceptionInfo_Type);
}
