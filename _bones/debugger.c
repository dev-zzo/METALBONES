#include <Python.h>
#include <Windows.h>

#include "internal.h"
#include "winternals.h"


typedef struct {
    PyObject_HEAD
    HANDLE dbgui_object; /* NT debugger object handle */
    PyObject *processes; /* A dict mapping process id -> process object */
} PyBones_DebuggerObject;


static void
dealloc(PyBones_DebuggerObject* self)
{
    if (self->dbgui_object) {
        NtClose(self->dbgui_object);
        self->dbgui_object = NULL;
    }
    Py_XDECREF(self->processes);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyBones_DebuggerObject *self;

    self = (PyBones_DebuggerObject *)type->tp_alloc(type, 0);
    if (self) {
        self->processes = PyDict_New();
        if (!self->processes)
            goto fail;
    }

    return (PyObject *)self;

fail:
    Py_DECREF(self);
    return NULL;
}

PyDoc_STRVAR(init__doc__,
"__init__(self)\n\n\
Initialises the Debugger object.");

static int
init(PyBones_DebuggerObject *self, PyObject *args, PyObject *kwds)
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
spawn(PyBones_DebuggerObject *self, PyObject *args)
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
        PyErr_SetObject(PyBones_Win32Error, PyInt_FromLong(GetLastError()));
        goto exit0;
    }

    status = NtDebugActiveProcess(process_info.hProcess, self->dbgui_object);
    NtResumeThread(process_info.hThread, NULL);
    if (!NT_SUCCESS(status)) {
        DEBUG_PRINT("BONES: Attaching to the started process has failed.\n");
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
attach(PyBones_DebuggerObject *self, PyObject *args)
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

    Py_INCREF(Py_None);
    return Py_None;
}

PyDoc_STRVAR(detach__doc__,
"detach(self, process)\n\n\
Detaches the Debugger object from the given process.");

static PyObject *
detach(PyBones_DebuggerObject *self, PyObject *args)
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

    Py_INCREF(Py_None);
    return Py_None;
}

static int
handle_state_change(PyBones_DebuggerObject *self, PDBGUI_WAIT_STATE_CHANGE info)
{
    DWORD pid = (DWORD)info->AppClientId.UniqueProcess;
    DWORD tid = (DWORD)info->AppClientId.UniqueThread;
    int result = -1;
    NTSTATUS status;
    NTSTATUS continue_status = DBG_CONTINUE;
    PyObject *cb_result = NULL;

    switch (info->NewState) {
    case DbgIdle:
        /* No idea how to handle these. */
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgIdle.\n", pid, tid);
        break;

    case DbgReplyPending:
        /* No idea how to handle these. */
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgReplyPending.\n", pid, tid);
        break;

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

        cb_result = PyObject_CallMethod((PyObject *)self, "_on_process_create", "kkkkkk",
            info->AppClientId.UniqueProcess,
            info->StateInfo.CreateProcessInfo.HandleToProcess,
            info->AppClientId.UniqueThread,
            info->StateInfo.CreateProcessInfo.HandleToThread,
            info->StateInfo.CreateProcessInfo.NewProcess.BaseOfImage,
            info->StateInfo.CreateProcessInfo.NewProcess.InitialThread.StartAddress);
        break;

    case DbgExitProcessStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_process_exit", "kk",
            info->AppClientId.UniqueProcess,
            info->StateInfo.ExitProcess.ExitStatus);
        break;

    case DbgCreateThreadStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_thread_create", "kkkk",
            info->AppClientId.UniqueProcess,
            info->AppClientId.UniqueThread,
            info->StateInfo.CreateThread.HandleToThread,
            info->StateInfo.CreateThread.NewThread.StartAddress);
        break;

    case DbgExitThreadStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_thread_exit", "kkk",
            info->AppClientId.UniqueProcess,
            info->AppClientId.UniqueThread,
            info->StateInfo.ExitProcess.ExitStatus);
        break;

    case DbgExceptionStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_exception", "kkNN",
            info->AppClientId.UniqueProcess,
            info->AppClientId.UniqueThread,
            _PyBones_ExceptionInfo_Translate(&info->StateInfo.Exception.ExceptionRecord),
            PyBool_FromLong(info->StateInfo.Exception.FirstChance));
        /* FIXME: this is the only event where passing DBG_CONTINUE is wrong? */
        break;

    case DbgBreakpointStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgBreakpointStateChange.\n", pid, tid);
        result = 0;
        continue_status = DBG_EXCEPTION_HANDLED;
        break;

    case DbgSingleStepStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgSingleStepStateChange.\n", pid, tid);
        result = 0;
        break;

    case DbgLoadDllStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_module_load", "kk",
            info->AppClientId.UniqueProcess,
            info->StateInfo.LoadDll.BaseOfDll);
        break;

    case DbgUnloadDllStateChange:
        cb_result = PyObject_CallMethod((PyObject *)self, "_on_module_unload", "kk",
            info->AppClientId.UniqueProcess,
            info->StateInfo.UnloadDll.BaseOfDll);
        break;

    default:
        DEBUG_PRINT("BONES: [%d/%d] Caught unknown event %d.\n", pid, tid, info->NewState);
        break;
    }

    if (cb_result) {
        Py_DECREF(cb_result);
        result = 0;
    }

    status = NtDebugContinue(self->dbgui_object, &info->AppClientId, continue_status);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        result = -1;
    }

    return result;
}

PyDoc_STRVAR(wait_event__doc__,
"wait_event(self, timeout = None) -> bool\n\n\
Wait for a debugging event for a specified timeout in ms.\n\
If no event occurs, returns False, else True.");

static PyObject *
wait_event(PyBones_DebuggerObject *self, PyObject *args)
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
    { "spawn", (PyCFunction)spawn, METH_VARARGS, spawn__doc__ },
    { "attach", (PyCFunction)attach, METH_VARARGS, attach__doc__ },
    { "detach", (PyCFunction)detach, METH_VARARGS, detach__doc__ },
    { "wait_event", (PyCFunction)wait_event, METH_VARARGS, wait_event__doc__ },
    {NULL}  /* Sentinel */
};

static PyObject *
get_processes(PyBones_DebuggerObject *self, void *closure)
{
    Py_INCREF(self->processes);
    return self->processes;
}

static PyGetSetDef getseters[] = {
    /* name, get, set, doc, closure */
    { "processes", (getter)get_processes, NULL, "Processes being debugged", NULL },
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
    type_doc,  /*tp_doc*/
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

