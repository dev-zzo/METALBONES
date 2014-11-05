#include <Python.h>
#include <Windows.h>

#include "internal.h"
#include "dbgui.h"

int
_PyBones_Process_AddThread(
    PyObject *self,
    PyObject *thread_id,
    PyObject *thread);

PyObject *
_PyBones_Process_DelThread(
    PyObject *self,
    PyObject *thread_id);

void
_PyBones_Process_SetExitStatus(PyObject *self, UINT status);

void
_PyBones_Thread_SetExitStatus(PyObject *self, UINT status);

static PNTCREATEDEBUGOBJECT NtCreateDebugObject;
static PNTDEBUGACTIVEPROCESS NtDebugActiveProcess;
static PNTWAITFORDEBUGEVENT NtWaitForDebugEvent;
static PNTDEBUGCONTINUE NtDebugContinue;
static PNTREMOVEPROCESSDEBUG NtRemoveProcessDebug;

static int
init_ntdll_pointers(void)
{
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (!ntdll) {
        /* Print something? */
        DEBUG_PRINT("BONES: Failed to get a handle for ntdll!\n");
        return -1;
    }

    NtCreateDebugObject = (PNTCREATEDEBUGOBJECT)GetProcAddress(ntdll, "NtCreateDebugObject");
    if (!NtCreateDebugObject) {
        DEBUG_PRINT("BONES: Failed to get NtCreateDebugObject!\n");
        return -1;
    }
    NtDebugActiveProcess = (PNTDEBUGACTIVEPROCESS)GetProcAddress(ntdll, "NtDebugActiveProcess");
    if (!NtDebugActiveProcess) {
        DEBUG_PRINT("BONES: Failed to get NtDebugActiveProcess!\n");
        return -1;
    }
    NtWaitForDebugEvent = (PNTWAITFORDEBUGEVENT)GetProcAddress(ntdll, "NtWaitForDebugEvent");
    if (!NtWaitForDebugEvent) {
        DEBUG_PRINT("BONES: Failed to get NtWaitForDebugEvent!\n");
        return -1;
    }
    NtDebugContinue = (PNTDEBUGCONTINUE)GetProcAddress(ntdll, "NtDebugContinue");
    if (!NtDebugContinue) {
        DEBUG_PRINT("BONES: Failed to get NtDebugContinue!\n");
        return -1;
    }
    NtRemoveProcessDebug = (PNTREMOVEPROCESSDEBUG)GetProcAddress(ntdll, "NtRemoveProcessDebug");
    if (!NtRemoveProcessDebug) {
        DEBUG_PRINT("BONES: Failed to get NtRemoveProcessDebug!\n");
        return -1;
    }

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
    if (self->dbgui_object) {
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
    if (self != NULL) {
        self->dbgui_object = NULL;
        self->processes = PyDict_New();
        if (!self->processes) {
            Py_DECREF(self);
            return NULL;
        }
    }

    return (PyObject *)self;
}

PyDoc_STRVAR(init__doc__,
"__init__(self)\n\n\
Initialises the Debugger object.");

static int
init(PyBones_DebuggerObject *self, PyObject *args, PyObject *kwds)
{
    NTSTATUS status;
    OBJECT_ATTRIBUTES dummy;

    if (!NtCreateDebugObject && init_ntdll_pointers() < 0) {
        PyErr_SetObject(PyBones_Win32Error, PyInt_FromLong(GetLastError()));
        return -1;
    }

    /* Create a debug object */
    InitializeObjectAttributes(&dummy, NULL, 0, NULL, 0);
    status = NtCreateDebugObject(
        &self->dbgui_object,
        DEBUG_OBJECT_ALL_ACCESS,
        &dummy,
        TRUE);
    if (!NT_SUCCESS(status)) {
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
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
    STARTUPINFOA startup_info = { sizeof(STARTUPINFOA), 0, };
    PROCESS_INFORMATION process_info = { 0, };

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
    ResumeThread(process_info.hThread);
    if (!NT_SUCCESS(status)) {
        TerminateProcess(process_info.hProcess, -1);
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        goto exit1;
    }

    Py_INCREF(Py_None);
    result = Py_None;

exit1:
    /* We don't need these -- we'll get ones with debug events */
    CloseHandle(process_info.hThread);
    CloseHandle(process_info.hProcess);
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
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
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
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static int
continue_event(HANDLE dbgui_object, PCLIENT_ID client, NTSTATUS ack_status)
{
    NTSTATUS status;

    status = NtDebugContinue(dbgui_object, client, ack_status);
    if (!NT_SUCCESS(status)) {
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        return -1;
    }
    return 0;
}

static int
do_event_callback(PyObject *o, const char *method, PyObject *arg)
{
    int result = -1;
    PyObject *name;
    PyObject *cb_result;

    name = PyString_FromString(method);
    if (name) {
        cb_result = PyObject_CallMethodObjArgs(o, name, arg, NULL);
        Py_DECREF(name);
        if (cb_result) {
            Py_DECREF(cb_result);
            result = 0;
        }
        else {
            if (PyErr_Occurred()) {
                DEBUG_PRINT("BONES: exception thrown!\n");
                if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
                    PyErr_Clear();
                    result = 0;
                }
            }
        }
    }

    return result;
}

static int
handle_create_thread(
    PyBones_DebuggerObject *self,
    PyObject *thread_id,
    HANDLE handle,
    PyObject *process,
    PVOID start_address)
{
    int result = -1;
    PyObject *arglist;
    PyObject *thread;

    /* Create new thread object */
    arglist = Py_BuildValue("(OkOkk)", /* id, handle, process, start_address, teb_address */
        thread_id,
        handle,
        process,
        start_address,
        0);
    if (arglist) {
        thread = PyObject_CallObject((PyObject *)&PyBones_Thread_Type, arglist);
        Py_DECREF(arglist);
        if (thread) {
            _PyBones_Process_AddThread(process, thread_id, thread);

            /* Call the handler method */
            result = do_event_callback((PyObject *)self, "on_thread_create", thread);
            Py_DECREF(thread);
        }
    }
    return result;
}

static int
handle_state_change(PyBones_DebuggerObject *self, PDBGUI_WAIT_STATE_CHANGE info)
{
    DWORD pid = (DWORD)info->AppClientId.UniqueProcess;
    DWORD tid = (DWORD)info->AppClientId.UniqueThread;
    int result = -1;
    PyObject *arglist;
    PyObject *process_id = NULL, *process = NULL;
    PyObject *thread_id = NULL, *thread = NULL;

    process_id = PyInt_FromLong(pid);
    if (!process_id)
        goto exit0;
    thread_id = PyInt_FromLong(tid);
    if (!thread_id)
        goto exit1;

    switch (info->NewState) {
    case DbgIdle:
        /* No idea how to handle these. */
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgIdle.\n", pid, tid);
        result = continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgReplyPending:
        /* No idea how to handle these. */
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgReplyPending.\n", pid, tid);
        result = continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgCreateProcessStateChange:
        DEBUG_PRINT("BONES: [%d] Process created.\n", pid);
        /* Create new process object */
        arglist = Py_BuildValue("(Okk)",
            process_id,
            info->StateInfo.CreateProcessInfo.HandleToProcess,
            info->StateInfo.CreateProcessInfo.NewProcess.BaseOfImage);
        if (arglist) {
            process = PyObject_CallObject((PyObject *)&PyBones_Process_Type, arglist);
            Py_DECREF(arglist);
            if (process) {
                /* Add it to dict */
                PyDict_SetItem(self->processes, process_id, process);

                /* Call the handler method */
                result = do_event_callback((PyObject *)self, "on_process_create", process);
                if (result >= 0) {
                    result = handle_create_thread(
                        self,
                        thread_id,
                        info->StateInfo.CreateProcessInfo.HandleToThread,
                        process,
                        info->StateInfo.CreateProcessInfo.NewProcess.InitialThread.StartAddress);
                }

                Py_DECREF(process);
            }
        }
        continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgExitProcessStateChange:
        DEBUG_PRINT("BONES: [%d] Process exited.\n", pid);
        /* Borrowed. */
        process = PyDict_GetItem(self->processes, process_id);
        if (process) {
            _PyBones_Process_SetExitStatus(process, info->StateInfo.ExitProcess.ExitStatus);
            /* Call the handler method */
            result = do_event_callback((PyObject *)self, "on_process_exit", process);
            if (result >= 0) {
                /* Remove the process */
                PyDict_DelItem(self->processes, process_id);
            }
        }
        else {
            /* No such process? */
            DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
        }
        continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgCreateThreadStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Thread created.\n", pid, tid);
        /* Borrowed. */
        process = PyDict_GetItem(self->processes, process_id);
        if (process) {
            result = handle_create_thread(
                self,
                thread_id,
                info->StateInfo.CreateThread.HandleToThread,
                process,
                info->StateInfo.CreateThread.NewThread.StartAddress);
        }
        else {
            /* No such process? */
            DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
        }
        continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgExitThreadStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Thread exited.\n", pid, tid);
        /* Borrowed. */
        process = PyDict_GetItem(self->processes, process_id);
        if (process) {
            /* FIXME: _PyBones_Process_DelThread() IS BROKEN.
               It returns the same value whether an error occurred
               or there's no such thread. */
            thread = _PyBones_Process_DelThread(process, thread_id);
            if (thread) {
                _PyBones_Thread_SetExitStatus(thread, info->StateInfo.ExitThread.ExitStatus);
                /* Call the handler method */
                result = do_event_callback((PyObject *)self, "on_thread_exit", thread);
                Py_DECREF(thread);
            }
            else {
                DEBUG_PRINT("BONES: [%d/%d] No such thread in the process being debugged.\n", pid, tid);
            }
        }
        else {
            /* No such process? */
            DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
        }

        continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgExceptionStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgExceptionStateChange.\n", pid, tid);
        result = continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgBreakpointStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgBreakpointStateChange.\n", pid, tid);
        /* Borrowed. */
        process = PyDict_GetItem(self->processes, process_id);
        result = continue_event(self->dbgui_object, &info->AppClientId, DBG_EXCEPTION_HANDLED);
        break;

    case DbgSingleStepStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgSingleStepStateChange.\n", pid, tid);
        result = continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgLoadDllStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgLoadDllStateChange.\n", pid, tid);
        result = continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgUnloadDllStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgUnloadDllStateChange.\n", pid, tid);
        result = continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    default:
        DEBUG_PRINT("BONES: [%d/%d] Caught unknown event %d.\n", pid, tid, info->NewState);
        break;
    }

exit2:
    Py_DECREF(process_id);
exit1:
    Py_DECREF(thread_id);
exit0:
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
        Py_INCREF(Py_False);
        return Py_False;
    }

    if (!NT_SUCCESS(status)) {
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        return NULL;
    }

    if (handle_state_change(self, &info) < 0) {
        return NULL;
    }

    Py_INCREF(Py_True);
    return Py_True;
}

/* Debugger object method definitions */
static PyMethodDef methods[] = {
    { "spawn", (PyCFunction)spawn, METH_VARARGS, spawn__doc__ },
    { "attach", (PyCFunction)attach, METH_VARARGS, attach__doc__ },
    { "detach", (PyCFunction)detach, METH_VARARGS, detach__doc__ },
    { "wait_event", (PyCFunction)wait_event, METH_VARARGS, wait_event__doc__ },
    {NULL}  /* Sentinel */
};

/* Debugger object field accessors */

static PyObject *
get_processes(PyBones_DebuggerObject *self, void *closure)
{
    return PyDictProxy_New(self->processes);
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

