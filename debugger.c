#include <Python.h>
#include <Windows.h>

#include "dbgui.h"
#include "internals.h"

static PZWCREATEDEBUGOBJECT ZwCreateDebugObject;
static PNTDEBUGACTIVEPROCESS NtDebugActiveProcess;
static PNTWAITFORDEBUGEVENT NtWaitForDebugEvent;
static PNTDEBUGCONTINUE NtDebugContinue;
static PNTREMOVEPROCESSDEBUG NtRemoveProcessDebug;

/* Debugger object */
typedef struct {
    PyObject_HEAD

    /* Type-specific fields go here. */
    HANDLE dbgui_object;

} Debugger;

/* Debugger object methods */

static void
Debugger_dealloc(Debugger* self)
{
    if (self->dbgui_object)
    {
        CloseHandle(self->dbgui_object);
        self->dbgui_object = NULL;
    }

    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
Debugger_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Debugger *self;

    self = (Debugger *)type->tp_alloc(type, 0);
    if (self != NULL)
    {
        self->dbgui_object = NULL;
    }

    return (PyObject *)self;
}

static int
Debugger_init(Debugger *self, PyObject *args, PyObject *kwds)
{
    NTSTATUS status;
    OBJECT_ATTRIBUTES dummy;

    /* Create a debug object */
    InitializeObjectAttributes(&dummy, NULL, 0, NULL, 0);
    status = ZwCreateDebugObject(&self->dbgui_object, DEBUG_OBJECT_ALL_ACCESS, &dummy, 1UL);
    if (!NT_SUCCESS(status))
    {
        PyErr_SetObject(NtStatusError, PyLong_FromUnsignedLong(status));
        return -1;
    }

    return 0;
}

static int
Debugger_attach(Debugger *self, PyObject *args)
{
    HANDLE process;
    NTSTATUS status;

    if (!PyArg_ParseTuple(args, "k", &process))
    {
        return -1;
    }

    status = NtDebugActiveProcess(process, self->dbgui_object);
    if (!NT_SUCCESS(status))
    {
        PyErr_SetObject(NtStatusError, PyLong_FromUnsignedLong(status));
        return -1;
    }

    return 0;
}

static int
Debugger_detach(Debugger *self, PyObject *args)
{
    HANDLE process;
    NTSTATUS status;

    if (!PyArg_ParseTuple(args, "k", &process))
    {
        return -1;
    }

    status = NtRemoveProcessDebug(process, self->dbgui_object);
    if (!NT_SUCCESS(status))
    {
        PyErr_SetObject(NtStatusError, PyLong_FromUnsignedLong(status));
        return -1;
    }

    return 0;
}

static PyObject *
Debugger_wait(Debugger *self, PyObject *args)
{
    DBGUI_WAIT_STATE_CHANGE info;
    LARGE_INTEGER timeout;
    NTSTATUS status;

    if (!PyArg_ParseTuple(args, "|K", &timeout.QuadPart))
    {
        return NULL;
    }

    status = NtWaitForDebugEvent(self->dbgui_object, TRUE, &timeout, &info);
    if (!NT_SUCCESS(status))
    {
        PyErr_SetObject(NtStatusError, PyLong_FromUnsignedLong(status));
        return NULL;
    }

    switch (info.NewState)
    {
    case DbgIdle:
    case DbgReplyPending:
        /* No idea how to handle these. */
        break;

    case DbgCreateThreadStateChange:
    case DbgCreateProcessStateChange:
    case DbgExitThreadStateChange:
    case DbgExitProcessStateChange:
    case DbgExceptionStateChange:
    case DbgBreakpointStateChange:
    case DbgSingleStepStateChange:
    case DbgLoadDllStateChange:
    case DbgUnloadDllStateChange:
        break;
    }
}

/* Debugger object method definitions */
static PyMethodDef Debugger_methods[] = {
    { "attach", (PyCFunction)Debugger_attach, METH_VARARGS, "Attach to a specified process" },
    { "detach", (PyCFunction)Debugger_detach, METH_VARARGS, "Detach from a specified process" },
    {NULL}  /* Sentinel */
};

/* Debugger object type */
static PyTypeObject DebuggerType = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "bones.Debugger",  /*tp_name*/
    sizeof(Debugger),  /*tp_basicsize*/
    0,  /*tp_itemsize*/
    (destructor)Debugger_dealloc,  /*tp_dealloc*/
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
    "Debugger object",  /*tp_doc*/
    0,  /* tp_traverse */
    0,  /* tp_clear */
    0,  /* tp_richcompare */
    0,  /* tp_weaklistoffset */
    0,  /* tp_iter */
    0,  /* tp_iternext */
    Debugger_methods,  /* tp_methods */
    0,  /* tp_members */
    0,  /* tp_getset */
    0,  /* tp_base */
    0,  /* tp_dict */
    0,  /* tp_descr_get */
    0,  /* tp_descr_set */
    0,  /* tp_dictoffset */
    (initproc)Debugger_init,  /* tp_init */
    0,  /* tp_alloc */
    Debugger_new,  /* tp_new */
};

/* Grab the function pointers */
static int
init_ntdll_pointers(void)
{
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (!ntdll)
    {
        /* Print something? */
        return -1;
    }

    ZwCreateDebugObject = (PZWCREATEDEBUGOBJECT)GetProcAddress(ntdll, "ZwCreateDebugObject");
    NtDebugActiveProcess = (PNTDEBUGACTIVEPROCESS)GetProcAddress(ntdll, "NtDebugActiveProcess");
    NtWaitForDebugEvent = (PNTWAITFORDEBUGEVENT)GetProcAddress(ntdll, "NtWaitForDebugEvent");
    NtDebugContinue = (PNTDEBUGCONTINUE)GetProcAddress(ntdll, "NtDebugContinue");
    NtRemoveProcessDebug = (PNTREMOVEPROCESSDEBUG)GetProcAddress(ntdll, "NtRemoveProcessDebug");

    return 0;
}

/* Init function to hook up this type into the module. */
int
init_DebuggerType(PyObject* m)
{
    int rv = 0;

    rv = init_ntdll_pointers();
    if (rv < 0)
    {
        return rv;
    }

    DebuggerType.tp_new = PyType_GenericNew;
    rv = PyType_Ready(&DebuggerType);
    if (rv < 0)
    {
        return rv;
    }

    Py_INCREF(&DebuggerType);
    PyModule_AddObject(m, "Debugger", (PyObject *)&DebuggerType);

    return rv;
}
