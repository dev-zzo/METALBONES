#include <Python.h>
#include <Windows.h>

#include "ntdll.h"
#include "_bones.h"

typedef struct {
    PyObject_HEAD
    PyObject *processes; /* A dict mapping process id -> info object */
} PyBones_ProcessMonitorObject;


static void
procmon_dealloc(PyBones_ProcessMonitorObject* self)
{
    Py_XDECREF(self->processes);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
procmon_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyBones_ProcessMonitorObject *self;

    self = (PyBones_ProcessMonitorObject *)type->tp_alloc(type, 0);
    if (self) {
        self->processes = PyDict_New();
        if (!self->processes) {
            goto fail;
        }
    }

    return (PyObject *)self;

fail:
    Py_DECREF(self);
    return NULL;
}

PyDoc_STRVAR(init__doc__,
"__init__(self)\n\n\
Initialises the Process Monitor object.");

static int
procmon_init(PyBones_ProcessMonitorObject *self, PyObject *args, PyObject *kwds)
{
    return 0;
}

PyDoc_STRVAR(update__doc__,
"update(self)\n\n\
Update the counters.");

static PSYSTEM_PROCESS_INFORMATION
procmon_lookup(PSYSTEM_PROCESS_INFORMATION pBuffer, ULONG process_id)
{
    PSYSTEM_PROCESS_INFORMATION pCursor;

    pCursor = pBuffer;
    for (;;) {
        if (pCursor->UniqueProcessId == process_id) {
            return pCursor;
        }
        if (!pCursor->NextEntryOffset) {
            return NULL;
        }
        pCursor = (PSYSTEM_PROCESS_INFORMATION)((PBYTE)pCursor + pCursor->NextEntryOffset);
    }

    return NULL;
}

static PyObject *
procmon_update(PyBones_ProcessMonitorObject *self, PyObject *args)
{
    NTSTATUS status;
    ULONG psi_length = 0x1000;
    ULONG real_length;
    PSYSTEM_PROCESS_INFORMATION pBuffer, pCursor;
    PyObject *process_id, *context;
    Py_ssize_t pos = 0;

    for (pBuffer = NULL; ; psi_length *= 2) {
        pBuffer = (PSYSTEM_PROCESS_INFORMATION)HeapAlloc(GetProcessHeap(), 0, psi_length);
        status = NtQuerySystemInformation(
            SystemProcessInformation,
            pBuffer,
            psi_length,
            &real_length);
        if (NT_SUCCESS(status)) {
            break;
        }

        HeapFree(GetProcessHeap(), 0, pBuffer);
        if (status != STATUS_INFO_LENGTH_MISMATCH) {
            /* Bleh, something bad happened. */
            PyBones_RaiseNtStatusError(status);
            return NULL;
        }
    }

    while (PyDict_Next(self->processes, &pos, &process_id, &context)) {
        pCursor = procmon_lookup(pBuffer, PyInt_AsLong(process_id));
        if (pCursor) {
            PyObject *cb_result = NULL;

            cb_result = PyObject_CallMethod((PyObject *)self, "_on_update", "OOKK",
                process_id,
                context,
                pCursor->KernelTime.QuadPart,
                pCursor->UserTime.QuadPart);
        }
    }

    HeapFree(GetProcessHeap(), 0, pBuffer);
    Py_RETURN_NONE;
}

PyDoc_STRVAR(track_process__doc__,
"_track_process(self, process_id, context)\n\n\
Track the process ID.");

static PyObject *
procmon_track_process(PyBones_ProcessMonitorObject *self, PyObject *args)
{
    PyObject *process_id;
    PyObject *context;

    if (!PyArg_ParseTuple(args, "OO", &process_id, &context)) {
        return NULL;
    }

    if (PyDict_SetItem(self->processes, process_id, context) < 0) {
        return NULL;
    }

    Py_RETURN_NONE;
}

PyDoc_STRVAR(untrack_process__doc__,
"_untrack_process(self, process_id)\n\n\
meh.");

static PyObject *
procmon_untrack_process(PyBones_ProcessMonitorObject *self, PyObject *args)
{
    PyObject *process_id;

    if (!PyArg_ParseTuple(args, "O", &process_id)) {
        return NULL;
    }

    if (PyDict_DelItem(self->processes, process_id) < 0) {
        return NULL;
    }

    Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
    { "update", (PyCFunction)procmon_update, METH_VARARGS, update__doc__ },
    { "_track_process", (PyCFunction)procmon_track_process, METH_VARARGS, track_process__doc__ },
    { "_untrack_process", (PyCFunction)procmon_untrack_process, METH_VARARGS, untrack_process__doc__ },
    {NULL}  /* Sentinel */
};

PyDoc_STRVAR(type_doc,
"The debugger object.\n\
The main object one would make use of to debug stuff.\n\
NOTE: To access the event methods, subclass this.");

/* Debugger object type */
PyTypeObject PyBones_ProcessMonitor_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "_bones.ProcessMonitor",  /*tp_name*/
    sizeof(PyBones_ProcessMonitorObject),  /*tp_basicsize*/
    0,  /*tp_itemsize*/
    (destructor)procmon_dealloc,  /*tp_dealloc*/
    0,  /*tp_print*/
    0,  /*tp_getattr*/
    0,  /*tp_setattr*/
    0,  /*tp_compare*/
    0,  /*tp_repr*/
    0,  /*tp_as_number*/
    0,  /*tp_as_sequence*/
    0,  /*tp_as_mapping*/
    0,  /*tp_hash */
    0,  /*tp_call*/
    0,  /*tp_str*/
    0,  /*tp_getattro*/
    0,  /*tp_setattro*/
    0,  /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,  /*tp_flags*/
    type_doc,  /*tp_doc*/
    0,  /* tp_traverse */
    0,  /* tp_clear */
    0,  /* tp_richcompare */
    0,  /* tp_weaklistoffset */
    0,  /* tp_iter */
    0,  /* tp_iternext */
    methods,  /* tp_methods */
    0,  /* tp_members */
    0,  /* tp_getset */
    0,  /* tp_base */
    0,  /* tp_dict */
    0,  /* tp_descr_get */
    0,  /* tp_descr_set */
    0,  /* tp_dictoffset */
    (initproc)procmon_init,  /* tp_init */
    0,  /* tp_alloc */
    procmon_new,  /* tp_new */
};
