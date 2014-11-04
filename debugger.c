#include <Python.h>
#include <Windows.h>

#include "bones.h"
#include "dbgui.h"

static PZWCREATEDEBUGOBJECT ZwCreateDebugObject;
static PNTDEBUGACTIVEPROCESS NtDebugActiveProcess;
static PNTWAITFORDEBUGEVENT NtWaitForDebugEvent;
static PNTDEBUGCONTINUE NtDebugContinue;
static PNTREMOVEPROCESSDEBUG NtRemoveProcessDebug;

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


/* Debugger object */

typedef struct {
    PyObject_HEAD

    HANDLE dbgui_object; /* NT debugger object handle */

    PyObject *processes; /* A dict mapping process id -> process object */

} PyBones_DebuggerObject;

/* Debugger type methods */

static void
dealloc(PyBones_DebuggerObject* self)
{
    if (self->dbgui_object)
    {
        CloseHandle(self->dbgui_object);
        self->dbgui_object = NULL;
    }

    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyBones_DebuggerObject *self;

    self = (PyBones_DebuggerObject *)type->tp_alloc(type, 0);
    if (self != NULL)
    {
        self->dbgui_object = NULL;
        self->processes = PyDict_New();
        if (!self->processes)
        {
            Py_DECREF(self);
            return NULL;
        }
    }

    return (PyObject *)self;
}

static int
init(PyBones_DebuggerObject *self, PyObject *args, PyObject *kwds)
{
    NTSTATUS status;
    OBJECT_ATTRIBUTES dummy;

    /* Create a debug object */
    InitializeObjectAttributes(&dummy, NULL, 0, NULL, 0);
    status = ZwCreateDebugObject(&self->dbgui_object, DEBUG_OBJECT_ALL_ACCESS, &dummy, 1UL);
    if (!NT_SUCCESS(status))
    {
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        return -1;
    }

    return 0;
}

static int
attach(PyBones_DebuggerObject *self, PyObject *args)
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
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        return -1;
    }

    return 0;
}

static int
detach(PyBones_DebuggerObject *self, PyObject *args)
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
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        return -1;
    }

    return 0;
}

static PyObject *
wait(PyBones_DebuggerObject *self, PyObject *args)
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
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        return NULL;
    }

    switch (info.NewState)
    {
    case DbgIdle:
    case DbgReplyPending:
        /* No idea how to handle these. */
        break;

    case DbgCreateThreadStateChange:
        break;

    case DbgCreateProcessStateChange:
        {
            PyObject *arglist;
            PyObject *process;
            PyObject *process_id;

            process_id = PyInt_FromLong(info.AppClientId.UniqueProcess);
            arglist = PyTuple_Pack(2,
                process_id,
                PyLong_FromUnsignedLong((UINT_PTR)info.StateInfo.CreateProcessInfo.NewProcess.BaseOfImage));
            process = PyObject_CallObject(&PyBones_Process_Type, arglist);
            Py_DECREF(arglist);
            if (!process)
            {
                /* TBD */
                break;
            }

            if (PyDict_SetItem(self->processes, process_id, process) < 0)
            {
                /* TBD */
                break;
            }
        }
        break;

    case DbgExitThreadStateChange:
        break;

    case DbgExitProcessStateChange:
        {
            PyObject *process_id;
            PyObject *process;

            process_id = PyInt_FromLong(info.AppClientId.UniqueProcess);
            process = PyDict_GetItem(self->processes, process_id);
            if (process)
            {
                PyObject *method_name;
                PyObject *result;

                /* Call the handler method */
                method_name = PyString_FromString("on_process_exit");
                result = PyObject_CallMethodObjArgs(self, method_name, process, NULL);
                if (result)
                {
                    /* OK */
                    Py_DECREF(result);
                }
                else
                {
                    PyObject *exc;
                    /* Failed -- no method? */
                    exc = PyErr_Occurred();
                    if (PyErr_GivenExceptionMatches(exc, &PyExc_AttributeError))
                    {
                        PyErr_Clear();
                    }
                    else
                    {
                        /* Pass the exception to the interpreter */
                    }
                }
                Py_DECREF(method_name);

                /* Remove the process */
                if (PyDict_DelItem(self->processes, process_id) < 0)
                {
                    /* TBD */
                }
            }
            else
            {
                /* No such process? */
            }
        }
        break;

    case DbgExceptionStateChange:
        break;

    case DbgBreakpointStateChange:
        break;

    case DbgSingleStepStateChange:
        break;

    case DbgLoadDllStateChange:
        break;

    case DbgUnloadDllStateChange:
        break;
    }
}

/* Debugger object method definitions */
static PyMethodDef methods[] = {
    { "attach", (PyCFunction)attach, METH_VARARGS, "Attach to a specified process" },
    { "detach", (PyCFunction)detach, METH_VARARGS, "Detach from a specified process" },
    {NULL}  /* Sentinel */
};

/* Debugger object field accessors */

static PyObject *
get_processes(PyBones_DebuggerObject *self, void *closure)
{
    PyObject *p = self->processes;
    Py_INCREF(p);
    return p;
}

static PyGetSetDef getseters[] =
{
    /* name, get, set, doc, closure */
    { "processes", (getter)get_processes, NULL, "Processes being debugged", NULL },
    {NULL}  /* Sentinel */
};

/* Debugger object type */
PyTypeObject PyBones_Debugger_Type =
{
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "bones.Debugger",  /*tp_name*/
    sizeof(PyBones_DebuggerObject),  /*tp_basicsize*/
    0,  /*tp_itemsize*/
    (destructor)dealloc,  /*tp_dealloc*/
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
    methods,  /* tp_methods */
    0,  /* tp_members */
    getseters,  /* tp_getset */
    0,  /* tp_base */
    0,  /* tp_dict */
    0,  /* tp_descr_get */
    0,  /* tp_descr_set */
    0,  /* tp_dictoffset */
    (initproc)init,  /* tp_init */
    0,  /* tp_alloc */
    new,  /* tp_new */
};

