#include <Python.h>
#include <Windows.h>

#include "internal.h"
#include "debugevent.h"

/* ------------------------------------------------------------------------- */

static int
DebugEvent_init(DebugEvent *self, PyObject *args, PyObject *kwds)
{
    return 0;
}

static PyObject *
DebugEvent_get_process_id(DebugEvent *self, void *closure)
{
    return PyLong_FromUnsignedLong(self->process_id);
}

static PyObject *
DebugEvent_get_thread_id(DebugEvent *self, void *closure)
{
    return PyLong_FromUnsignedLong(self->thread_id);
}

static PyGetSetDef DebugEvent_getseters[] =
{
    {
        "process_id", (getter)DebugEvent_get_process_id, NULL,
        "Process ID of the client that generated the event",
        NULL
    },
    {
        "thread_id", (getter)DebugEvent_get_thread_id, NULL,
        "Thread ID of the client that generated the event",
        NULL
    },
    {NULL}  /* Sentinel */
};

PyTypeObject DebugEventType = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "bones.DebugEvent",  /*tp_name*/
    sizeof(DebugEvent),  /*tp_basicsize*/
    0,  /*tp_itemsize*/
    0,  /*tp_dealloc*/
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
    "Debug event",  /*tp_doc*/
};

/* ------------------------------------------------------------------------- */

/* Init function to hook up these types into the module. */
int
init_DebuggerEventType(PyObject* m)
{
    int rv;

    DebugEventType.tp_new = PyType_GenericNew;
    rv = PyType_Ready(&DebugEventType);
    if (rv < 0)
    {
        return rv;
    }

    Py_INCREF(&DebugEventType);
    PyModule_AddObject(m, "DebugEvent", (PyObject *) &DebugEventType);

    return rv;
}
