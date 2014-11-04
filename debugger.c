#include <Python.h>
#include <Windows.h>

#include "internal.h"
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

static int
handle_cb_result(PyObject *cb_result)
{
    PyObject *exc;

    if (cb_result)
    {
        /* OK, this should be None */
        Py_DECREF(cb_result);
        return 0;
    }

    /* Failed -- no method? */
    exc = PyErr_Occurred();
    if (PyErr_GivenExceptionMatches(exc, PyExc_AttributeError))
    {
        PyErr_Clear();
        return 0;
    }
    return -1;
}

static int
handle_create_thread(PyBones_DebuggerObject *self, PyObject *thread_id, HANDLE handle, PyObject *process, PVOID start_address)
{
    PyObject *arglist;
    PyObject *cb_result;
    PyObject *thread;

    /* Create new thread object */
    arglist = Py_BuildValue("(OkOkk)", /* id, handle, process, start_address, teb_address */
        thread_id,
        handle,
        process,
        start_address,
        0);
    if (arglist)
    {
        thread = PyObject_CallObject((PyObject *)&PyBones_Thread_Type, arglist);
        Py_DECREF(arglist);
        if (thread)
        {
            PyObject *threads;
            /* Add it to dict */
            threads = PyObject_GetAttrString(process, "threads");
            if (threads)
            {
                PyDict_SetItem(threads, thread_id, thread);
                Py_DECREF(threads);
            }

            /* Call the handler method */
            cb_result = PyObject_CallMethod((PyObject *)self, "on_thread_create", "O", thread);
            handle_cb_result(cb_result);

            Py_DECREF(thread);
        }
    }
    return 0;
}

static PyObject *
handle_state_change(PyBones_DebuggerObject *self, PDBGUI_WAIT_STATE_CHANGE info)
{
    DWORD pid = (DWORD)info->AppClientId.UniqueProcess;
    DWORD tid = (DWORD)info->AppClientId.UniqueThread;
    PyObject *result = NULL;
    PyObject *arglist;
    PyObject *cb_result;
    PyObject *process_id = NULL, *process = NULL;
    PyObject *thread_id = NULL, *thread = NULL;

    process_id = PyInt_FromLong(pid);
    if (!process_id)
        goto exit0;
    thread_id = PyInt_FromLong(tid);
    if (!thread_id)
        goto exit1;

    switch (info->NewState)
    {
    case DbgIdle:
        /* No idea how to handle these. */
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgIdle.\n", pid, tid);
        break;

    case DbgReplyPending:
        /* No idea how to handle these. */
        DEBUG_PRINT("BONES: [%d/%d] Caught DbgReplyPending.\n", pid, tid);
        break;

    case DbgCreateProcessStateChange:
        DEBUG_PRINT("BONES: [%d] Process created.\n", pid);
        {
            /* Create new process object */
            arglist = Py_BuildValue("(Okk)",
                process_id,
                info->StateInfo.CreateProcessInfo.HandleToProcess,
                info->StateInfo.CreateProcessInfo.NewProcess.BaseOfImage);
            if (arglist)
            {
                process = PyObject_CallObject((PyObject *)&PyBones_Process_Type, arglist);
                Py_DECREF(arglist);
                if (process)
                {
                    /* Add it to dict */
                    PyDict_SetItem(self->processes, process_id, process);

                    /* Call the handler method */
                    cb_result = PyObject_CallMethod((PyObject *)self, "on_process_create", "O", process);
                    handle_cb_result(cb_result);

                    handle_create_thread(
                        self,
                        thread_id,
                        info->StateInfo.CreateProcessInfo.HandleToThread,
                        process,
                        info->StateInfo.CreateProcessInfo.NewProcess.InitialThread.StartAddress);

                    Py_DECREF(process);
                }
            }
        }
        break;

    case DbgExitProcessStateChange:
        DEBUG_PRINT("BONES: [%d] Process exited.\n", pid);
        {
            /* Borrowed. */
            process = PyDict_GetItem(self->processes, process_id);
            if (process)
            {
                /* Call the handler method */
                cb_result = PyObject_CallMethod((PyObject *)self, "on_process_exit",
                    "Ok",
                    process,
                    info->StateInfo.ExitProcess.ExitStatus);
                handle_cb_result(cb_result);

                /* Remove the process */
                PyDict_DelItem(self->processes, process_id);
            }
            else
            {
                /* No such process? */
                DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
            }
        }
        break;

    case DbgCreateThreadStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Thread created.\n", pid, tid);
        {
            /* Borrowed. */
            process = PyDict_GetItem(self->processes, process_id);
            if (process)
            {
                handle_create_thread(
                    self,
                    thread_id,
                    info->StateInfo.CreateThread.HandleToThread,
                    process,
                    info->StateInfo.CreateThread.NewThread.StartAddress);
            }
            else
            {
                /* No such process? */
                DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
            }
        }
        break;

    case DbgExitThreadStateChange:
        DEBUG_PRINT("BONES: [%d/%d] Thread exited.\n", pid, tid);
        {
            /* Borrowed. */
            process = PyDict_GetItem(self->processes, process_id);
            if (process)
            {
                PyObject *threads;
                /* Add it to dict */
                threads = PyObject_GetAttrString(process, "threads");
                if (threads)
                {
                    /* Borrowed. */
                    thread = PyDict_GetItem(threads, thread_id);
                    if (thread)
                    {
                        /* Call the handler method */
                        cb_result = PyObject_CallMethod((PyObject *)self, "on_thread_exit",
                            "Ok",
                            thread,
                            info->StateInfo.ExitThread.ExitStatus);
                        handle_cb_result(cb_result);

                        /* Remove the thread */
                        PyDict_DelItem(threads, thread_id);
                    }
                    else
                    {
                        DEBUG_PRINT("BONES: [%d/%d] No such thread in the process being debugged.\n", pid, tid);
                    }

                    Py_DECREF(threads);
                }
            }
            else
            {
                /* No such process? */
                DEBUG_PRINT("BONES: [%d/%d] No such process is being debugged.\n", pid, tid);
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

exit2:
    Py_DECREF(process_id);
exit1:
    Py_DECREF(thread_id);
exit0:
    return result;
}

static PyObject *
wait(PyBones_DebuggerObject *self, PyObject *args)
{
    DBGUI_WAIT_STATE_CHANGE info;
    unsigned int wait_time = UINT_MAX;
    LARGE_INTEGER timeout;
    PLARGE_INTEGER timeout_ptr = NULL;
    NTSTATUS status;

    if (!PyArg_ParseTuple(args, "|I", &wait_time))
    {
        return NULL;
    }

    if (wait_time < UINT_MAX)
    {
        timeout.QuadPart = UInt32x32To64(-10000, wait_time);
        timeout_ptr = &timeout;
    }

    do
    {
        status = NtWaitForDebugEvent(self->dbgui_object, TRUE, timeout_ptr, &info);
    } while (status == STATUS_ALERTED || status == STATUS_USER_APC);

    if (status == STATUS_TIMEOUT)
    {
        Py_INCREF(Py_None);
        return Py_None;
    }

    if (!NT_SUCCESS(status))
    {
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        return NULL;
    }

    return handle_state_change(self, &info);
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
    return PyDictProxy_New(self->processes);
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

