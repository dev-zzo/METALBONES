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
    ResumeThread(process_info.hThread);
    if (!NT_SUCCESS(status)) {
        DEBUG_PRINT("BONES: Attaching to the started process has failed.\n");
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
            PyObject *exc;

            exc = PyErr_Occurred();
            if (exc) {
                DEBUG_PRINT("BONES: exception thrown!\n");
#if 0
                __asm int 3;
#endif
                /* Verify somehow this is specifically our exception. */
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
    arglist = Py_BuildValue("(OkOk)", /* id, handle, process, start_address */
        thread_id,
        handle,
        process,
        start_address);
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
handle_load_module(
    PyBones_DebuggerObject *self,
    PyObject *base_addr,
    PyObject *process)
{
    int result = -1;
    PyObject *arglist;
    PyObject *module;

    arglist = Py_BuildValue("(OO)",
        base_addr,
        process);
    if (arglist) {
        module = PyObject_CallObject((PyObject *)&PyBones_Module_Type, arglist);
        Py_DECREF(arglist);
        if (module) {
            _PyBones_Process_AddModule(process, base_addr, module);
            result = do_event_callback((PyObject *)self, "on_module_load", module);
            Py_DECREF(module);
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
    PyObject *process_id = NULL, *thread_id = NULL;
    PyObject *process, *thread, *module;

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
        /* DEBUG_PRINT("BONES: [%d] Process created.\n", pid); */
        arglist = Py_BuildValue("(Okk)",
            process_id,
            info->StateInfo.CreateProcessInfo.HandleToProcess,
            info->StateInfo.CreateProcessInfo.NewProcess.BaseOfImage);
        if (arglist) {
            process = PyObject_CallObject((PyObject *)&PyBones_Process_Type, arglist);
            Py_DECREF(arglist);
            if (process) {
                PyDict_SetItem(self->processes, process_id, process);
                result = do_event_callback((PyObject *)self, "on_process_create", process);
                if (result >= 0) {
                    PyObject *base_addr;

                    base_addr = PyLong_FromUnsignedLong((UINT_PTR)info->StateInfo.CreateProcessInfo.NewProcess.BaseOfImage);
                    if (base_addr) {
                        result = handle_load_module(
                            self,
                            base_addr,
                            process);
                        Py_DECREF(base_addr);

                        if (result >= 0) {
                            result = handle_create_thread(
                                self,
                                thread_id,
                                info->StateInfo.CreateProcessInfo.HandleToThread,
                                process,
                                info->StateInfo.CreateProcessInfo.NewProcess.InitialThread.StartAddress);
                        }
                    }
                }

                Py_DECREF(process);
            }
        }
        continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgExitProcessStateChange:
        /* DEBUG_PRINT("BONES: [%d] Process exited.\n", pid); */
        /* Borrowed. */
        process = PyDict_GetItem(self->processes, process_id);
        if (process) {
            _PyBones_Process_SetExitStatus(process, info->StateInfo.ExitProcess.ExitStatus);
            result = do_event_callback((PyObject *)self, "on_process_exit", process);
            if (result >= 0) {
                PyDict_DelItem(self->processes, process_id);
            }
        }
        else {
            DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
        }
        continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgCreateThreadStateChange:
        /* DEBUG_PRINT("BONES: [%d/%d] Thread created.\n", pid, tid); */
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
            DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
        }
        continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgExitThreadStateChange:
        /* DEBUG_PRINT("BONES: [%d/%d] Thread exited.\n", pid, tid); */
        /* Borrowed. */
        process = PyDict_GetItem(self->processes, process_id);
        if (process) {
            thread = _PyBones_Process_DelThread(process, thread_id);
            if (thread) {
                if (thread != Py_None) {
                    _PyBones_Thread_SetExitStatus(thread, info->StateInfo.ExitThread.ExitStatus);
                    result = do_event_callback((PyObject *)self, "on_thread_exit", thread);
                    Py_DECREF(thread);
                }
                else {
                    DEBUG_PRINT("BONES: [%d/%d] No such thread in the process being debugged.\n", pid, tid);
                }
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
        /* DEBUG_PRINT("BONES: [%d/%d] Caught DbgLoadDllStateChange.\n", pid, tid); */
        /* Borrowed. */
        process = PyDict_GetItem(self->processes, process_id);
        if (process) {
            PyObject *base_addr;

            base_addr = PyLong_FromUnsignedLong((UINT_PTR)info->StateInfo.LoadDll.BaseOfDll);
            if (base_addr) {
                result = handle_load_module(
                    self,
                    base_addr,
                    process);
                Py_DECREF(base_addr);
            }
        }
        else {
            /* No such process? */
            DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
        }
        continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
        break;

    case DbgUnloadDllStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgUnloadDllStateChange.\n", pid, tid);
        /* Borrowed. */
        process = PyDict_GetItem(self->processes, process_id);
        if (process) {
            PyObject *base_addr;

            base_addr = PyLong_FromUnsignedLong((UINT_PTR)info->StateInfo.UnloadDll.BaseOfDll);
            if (base_addr) {
                module = _PyBones_Process_DelModule(process, base_addr);
                if (module) {
                    if (module != Py_None) {
                        result = do_event_callback((PyObject *)self, "on_module_unload", module);
                        Py_DECREF(module);
                    }
                    else {
                        /* No such module. */
                    }
                }
                Py_DECREF(base_addr);
            }
        }
        else {
            /* No such process? */
            DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
        }
        continue_event(self->dbgui_object, &info->AppClientId, DBG_CONTINUE);
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

