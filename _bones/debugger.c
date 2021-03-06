#include <Python.h>
#include <Windows.h>

#include "ntdll.h"
#include "_bones.h"

typedef struct {
    PyObject_HEAD
    HANDLE dbgui_object; /* NT debugger object handle */
} PyBones_DebuggerObject;


static void
debugger_dealloc(PyBones_DebuggerObject* self)
{
    if (self->dbgui_object) {
        NtClose(self->dbgui_object);
        self->dbgui_object = NULL;
    }
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
debugger_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyBones_DebuggerObject *self;

    self = (PyBones_DebuggerObject *)type->tp_alloc(type, 0);

    return (PyObject *)self;
}

PyDoc_STRVAR(init__doc__,
"__init__(self)\n\n\
Initialises the Debugger object.");

static int
debugger_init(PyBones_DebuggerObject *self, PyObject *args, PyObject *kwds)
{
    NTSTATUS status;
    OBJECT_ATTRIBUTES dummy;

    /* Create a debug object */
    InitializeObjectAttributes(&dummy, NULL, 0, NULL, 0);
    status = NtCreateDebugObject(
        &self->dbgui_object,
        DEBUG_OBJECT_ALL_ACCESS,
        &dummy,
        TRUE);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return -1;
    }

    return 0;
}

PyDoc_STRVAR(spawn__doc__,
"spawn(self, cmdline)\n\n\
Spawns and attaches the Debugger object to the process.");

static PyObject *
debugger_spawn(PyBones_DebuggerObject *self, PyObject *args)
{
    PyObject *result = NULL;
    char *cmdline = NULL;
    BOOL cp_result;
    NTSTATUS status;
    STARTUPINFOA startup_info = { sizeof(STARTUPINFOA), };
    PROCESS_INFORMATION process_info;

    if (!PyArg_ParseTuple(args, "s", &cmdline)) {
        goto exit0;
    }

    cp_result = CreateProcessA(
        NULL, /* lpApplicationName */
        cmdline, /* lpCommandLine */
        NULL, /* lpProcessAttributes */
        NULL, /* lpThreadAttributes */
        FALSE, /* bInheritHandles */
        CREATE_SUSPENDED|CREATE_DEFAULT_ERROR_MODE|CREATE_NEW_CONSOLE, /* dwCreationFlags */
        NULL, /* lpEnvironment */
        NULL, /* lpCurrentDirectory */
        &startup_info, /* */
        &process_info);
    if (!cp_result) {
        PyBones_RaiseWin32Error(GetLastError());
        goto exit0;
    }

    status = NtDebugActiveProcess(process_info.hProcess, self->dbgui_object);
    if (!NT_SUCCESS(status)) {
        NtTerminateProcess(process_info.hProcess, -1);
        PyBones_RaiseNtStatusError(status);
        goto exit1;
    }

    Py_INCREF(Py_None);
    result = Py_None;

exit1:
    /* We don't need these -- we'll get ones with debug events */
    NtClose(process_info.hThread);
    NtClose(process_info.hProcess);
exit0:
    return result;
}

PyDoc_STRVAR(attach__doc__,
"attach(self, process_handle)\n\n\
Attaches the Debugger object to a process.");

static PyObject *
debugger_attach(PyBones_DebuggerObject *self, PyObject *args)
{
    HANDLE process;
    NTSTATUS status;

    if (!PyArg_ParseTuple(args, "k", &process)) {
        return NULL;
    }

    status = NtDebugActiveProcess(process, self->dbgui_object);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    Py_RETURN_NONE;
}

PyDoc_STRVAR(detach__doc__,
"detach(self, process)\n\n\
Detaches the Debugger object from the given process.");

static PyObject *
debugger_detach(PyBones_DebuggerObject *self, PyObject *args)
{
    HANDLE process;
    NTSTATUS status;

    if (!PyArg_ParseTuple(args, "k", &process)) {
        return NULL;
    }

    status = NtRemoveProcessDebug(process, self->dbgui_object);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    Py_RETURN_NONE;
}


static PyObject *
debugger_translate_exception(PEXCEPTION_RECORD record)
{
    PyObject *info;
    PyObject *args;
    PyObject *nested_info;
    Py_ssize_t num_args;
    Py_ssize_t pos;

    if (record->ExceptionRecord) {
        nested_info = debugger_translate_exception(record->ExceptionRecord);
        if (!nested_info) {
            return NULL;
        }
    }
    else {
        Py_INCREF(Py_None);
        nested_info = Py_None;
    }

    num_args = record->NumberParameters; /* or EXCEPTION_MAXIMUM_PARAMETERS? */
    args = PyTuple_New(num_args);
    if (!args) {
        goto error1;
    }
    for (pos = 0; pos < num_args; ++pos) {
        PyObject *arg;

        arg = PyLong_FromUnsignedLong(record->ExceptionInformation[pos]);
        if (!arg) {
            goto error2;
        }
        PyTuple_SET_ITEM(args, pos, arg);
    }

    info = PyTuple_New(5);
    if (!info) {
        goto error2;
    }

    PyTuple_SET_ITEM(info, 0, PyLong_FromUnsignedLong(record->ExceptionCode));
    PyTuple_SET_ITEM(info, 1, PyLong_FromVoidPtr(record->ExceptionAddress));
    PyTuple_SET_ITEM(info, 2, PyLong_FromUnsignedLong(record->ExceptionFlags));
    PyTuple_SET_ITEM(info, 3, args);
    PyTuple_SET_ITEM(info, 4, nested_info);

    return (PyObject *)info;

error2:
    Py_DECREF(args);
error1:
    Py_DECREF(nested_info);
    return NULL;
}

static int
handle_state_change(PyBones_DebuggerObject *self, PDBGUI_WAIT_STATE_CHANGE info)
{
    DWORD pid = (DWORD)info->AppClientId.UniqueProcess;
    DWORD tid = (DWORD)info->AppClientId.UniqueThread;
    int result = -1;
    NTSTATUS status;
    PyObject *cb_result = NULL;

    switch (info->NewState) {
    case DbgCreateProcessStateChange:
        /* Due to whatever reason, the initial thread's start address
           is not populated (i.e. is zero). Hack around and get it. */
        if (!info->StateInfo.CreateProcessInfo.NewProcess.InitialThread.StartAddress) {
            PVOID StartAddress;

            status = NtQueryInformationThread(
                info->StateInfo.CreateProcessInfo.HandleToThread,
                ThreadQuerySetWin32StartAddress,
                &StartAddress,
                sizeof(StartAddress),
                NULL);
            if (NT_SUCCESS(status)) {
                info->StateInfo.CreateProcessInfo.NewProcess.InitialThread.StartAddress = StartAddress;
            }
        }

        cb_result = PyObject_CallMethod((PyObject *)self, "_on_process_create", "ikikkk",
            info->AppClientId.UniqueProcess,
            info->StateInfo.CreateProcessInfo.HandleToProcess,
            info->AppClientId.UniqueThread,
            info->StateInfo.CreateProcessInfo.HandleToThread,
            info->StateInfo.CreateProcessInfo.NewProcess.BaseOfImage,
            info->StateInfo.CreateProcessInfo.NewProcess.InitialThread.StartAddress);
        break;

    case DbgExitProcessStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_process_exit", "ik",
            info->AppClientId.UniqueProcess,
            info->StateInfo.ExitProcess.ExitStatus);
        break;

    case DbgCreateThreadStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_thread_create", "iikk",
            info->AppClientId.UniqueProcess,
            info->AppClientId.UniqueThread,
            info->StateInfo.CreateThread.HandleToThread,
            info->StateInfo.CreateThread.NewThread.StartAddress);
        break;

    case DbgExitThreadStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_thread_exit", "iik",
            info->AppClientId.UniqueProcess,
            info->AppClientId.UniqueThread,
            info->StateInfo.ExitProcess.ExitStatus);
        break;

    case DbgExceptionStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_exception", "iiNN",
            info->AppClientId.UniqueProcess,
            info->AppClientId.UniqueThread,
            debugger_translate_exception(&info->StateInfo.Exception.ExceptionRecord),
            PyBool_FromLong(info->StateInfo.Exception.FirstChance));
        break;

    case DbgBreakpointStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_breakpoint", "ii",
            info->AppClientId.UniqueProcess,
            info->AppClientId.UniqueThread);
        break;

    case DbgSingleStepStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_single_step", "ii",
            info->AppClientId.UniqueProcess,
            info->AppClientId.UniqueThread);
        break;

    case DbgLoadDllStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_module_load", "ik",
            info->AppClientId.UniqueProcess,
            info->StateInfo.LoadDll.BaseOfDll);
        break;

    case DbgUnloadDllStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_module_unload", "ik",
            info->AppClientId.UniqueProcess,
            info->StateInfo.UnloadDll.BaseOfDll);
        break;

    case DbgIdle:
    case DbgReplyPending:
    default:
        PyErr_SetString(PyExc_ValueError, "unknown debug event type caught");
        break;
    }

    if (cb_result) {
        NTSTATUS continue_status = -1;

        if (PyInt_CheckExact(cb_result)) {
            continue_status = PyInt_AS_LONG(cb_result);
        }
        else if (PyLong_CheckExact(cb_result)) {
            continue_status = PyLong_AsUnsignedLong(cb_result);
        }
        else {
            /* Raise a TypeError */
            PyErr_SetString(PyExc_TypeError, "expected an instance of int or long");
        }
        Py_DECREF(cb_result);

        if (continue_status != -1) {
            status = NtDebugContinue(self->dbgui_object, &info->AppClientId, continue_status);
            if (!NT_SUCCESS(status)) {
                PyBones_RaiseNtStatusError(status);
            }
            else {
                result = 0;
            }
        }
    }

    return result;
}

PyDoc_STRVAR(wait_event__doc__,
"wait_event(self, timeout = None) -> bool\n\n\
Wait for a debugging event for a specified timeout in ms.\n\
If no event occurs, returns False, else True.");

static PyObject *
debugger_wait_event(PyBones_DebuggerObject *self, PyObject *args)
{
    DBGUI_WAIT_STATE_CHANGE info;
    unsigned int wait_time = UINT_MAX;
    LARGE_INTEGER timeout;
    PLARGE_INTEGER timeout_ptr = NULL;
    NTSTATUS status;

    if (!PyArg_ParseTuple(args, "|I", &wait_time)) {
        return NULL;
    }

    if (wait_time < UINT_MAX) {
        /* A negative value specifies an interval relative 
           to the current time, in 100-nanosecond units. */
        timeout.QuadPart = wait_time * -10000LL;
        timeout_ptr = &timeout;
    }

    do
        status = NtWaitForDebugEvent(self->dbgui_object, TRUE, timeout_ptr, &info);
    while (status == STATUS_ALERTED || status == STATUS_USER_APC);

    if (status == STATUS_TIMEOUT) {
        Py_RETURN_FALSE;
    }

    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    if (handle_state_change(self, &info) < 0) {
        return NULL;
    }

    Py_RETURN_TRUE;
}

static PyMethodDef methods[] = {
    { "spawn", (PyCFunction)debugger_spawn, METH_VARARGS, spawn__doc__ },
    { "attach", (PyCFunction)debugger_attach, METH_VARARGS, attach__doc__ },
    { "detach", (PyCFunction)debugger_detach, METH_VARARGS, detach__doc__ },
    { "wait_event", (PyCFunction)debugger_wait_event, METH_VARARGS, wait_event__doc__ },
    {NULL}  /* Sentinel */
};

PyDoc_STRVAR(type_doc,
"The debugger object.\n\
The main object one would make use of to debug stuff.\n\
NOTE: To access the event methods, subclass this.");

/* Debugger object type */
PyTypeObject PyBones_Debugger_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "_bones.Debugger",  /*tp_name*/
    sizeof(PyBones_DebuggerObject),  /*tp_basicsize*/
    0,  /*tp_itemsize*/
    (destructor)debugger_dealloc,  /*tp_dealloc*/
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
    (initproc)debugger_init,  /* tp_init */
    0,  /* tp_alloc */
    debugger_new,  /* tp_new */
};

int
init_Debugger(PyObject* m)
{
    int rv;
    PyObject *tp_dict;

    tp_dict = PyDict_New();
    PyDict_SetItemString(tp_dict, "DBG_EXCEPTION_HANDLED",
        PyLong_FromUnsignedLong(0x00010001));
    PyDict_SetItemString(tp_dict, "DBG_CONTINUE",
        PyLong_FromUnsignedLong(0x00010002));
    PyDict_SetItemString(tp_dict, "DBG_EXCEPTION_NOT_HANDLED",
        PyLong_FromUnsignedLong(0x80010001));
    PyDict_SetItemString(tp_dict, "DBG_TERMINATE_THREAD",
        PyLong_FromUnsignedLong(0x40010003));
    PyDict_SetItemString(tp_dict, "DBG_TERMINATE_PROCESS",
        PyLong_FromUnsignedLong(0x40010004));
    PyBones_Debugger_Type.tp_dict = tp_dict;

    rv = PyType_Ready(&PyBones_Debugger_Type);
    if (rv < 0)
        return rv;

    Py_INCREF(&PyBones_Debugger_Type);
    return PyModule_AddObject(m, "Debugger", (PyObject *)&PyBones_Debugger_Type);
}
