#include <Python.h>
#include <Windows.h>

#include "ntdll.h"
#include "_bones.h"

/* Base class for our exceptions */
PyObject *PyBones_BonesException;

/* Win32 system error code exception */
PyObject *PyBones_Win32Error;

/* NT status exception */
PyObject *PyBones_NtStatusError;

int
init_Debugger(PyObject* m);

int
_PyBones_Context_Get(PyObject *self, HANDLE Thread);

int
_PyBones_Context_Set(PyObject *self, HANDLE Thread);

int
PyBones_Context_Check(PyObject *o);


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

/*** Process routines ***/

PyDoc_STRVAR(process_get_peb__doc__,
"process_get_peb(hprocess)\n\n\
Get the PEB address.");

static PyObject *
process_get_peb(PyObject *self, PyObject *args)
{
    HANDLE handle;
    NTSTATUS status;
    PROCESS_BASIC_INFORMATION pbi;

    if (!PyArg_ParseTuple(args, "k", &handle)) {
        return NULL;
    }

    status = NtQueryInformationProcess(
        handle,
        ProcessBasicInformation,
        &pbi,
        sizeof(pbi),
        NULL);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    return PyLong_FromVoidPtr(pbi.PebBaseAddress);
}

PyDoc_STRVAR(process_terminate__doc__,
"process_terminate(hprocess, exit_code)\n\n\
Start the termination of this process.");

static PyObject *
process_terminate(PyObject *self, PyObject *args)
{
    HANDLE handle;
    NTSTATUS status;
    UINT exit_code = 0xDEADBEEF;

    if (!PyArg_ParseTuple(args, "k|I", &handle, &exit_code)) {
        return NULL;
    }

    status = NtTerminateProcess(handle, exit_code);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    Py_RETURN_NONE;
}

/*** Thread routines ***/

PyDoc_STRVAR(thread_get_teb__doc__,
"thread_get_teb(hthread)\n\n\
Get the TEB address.");

static PyObject *
thread_get_teb(PyObject *self, PyObject *args)
{
    HANDLE handle;
    NTSTATUS status;
    THREAD_BASIC_INFORMATION tbi;

    if (!PyArg_ParseTuple(args, "k", &handle)) {
        return NULL;
    }

    status = NtQueryInformationThread(
        handle,
        ThreadBasicInformation,
        &tbi,
        sizeof(tbi),
        NULL);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    return PyLong_FromVoidPtr(tbi.TebBaseAddress);
}

PyDoc_STRVAR(thread_get_context__doc__,
"thread_get_context(hthread)\n\n\
Get the thread's context.");

static PyObject *
thread_get_context(PyObject *self, PyObject *args)
{
    HANDLE handle;
    PyObject *context;

    if (!PyArg_ParseTuple(args, "k", &handle)) {
        return NULL;
    }

    context = PyObject_CallObject((PyObject *)&PyBones_Context_Type, NULL);
    if (context) {
        if (_PyBones_Context_Get(context, handle) < 0) {
            Py_DECREF(context);
            context = NULL;
        }
    }

    return context;
}

PyDoc_STRVAR(thread_set_context__doc__,
"thread_set_context(hthread, context)\n\n\
Set the thread's context.");

static PyObject *
thread_set_context(PyObject *self, PyObject *args)
{
    HANDLE handle;
    PyObject *context;

    if (!PyArg_ParseTuple(args, "kO", &handle, &context)) {
        return NULL;
    }

    if (!PyBones_Context_Check(context)) {
        PyErr_SetString(PyExc_TypeError, "Expected an instance of Context.");
        return NULL;
    }

    if (_PyBones_Context_Set(context, handle) < 0) {
        return NULL;
    }

    Py_RETURN_NONE;
}

PyDoc_STRVAR(thread_set_single_step__doc__,
"thread_set_single_step(hthread)\n\n\
Enable single-stepping this thread.\n\
Is active ONLY UNTIL THE NEXT SINGLE STEP EVENT.");

static PyObject *
thread_set_single_step(PyObject *self, PyObject *args)
{
    HANDLE handle;
    NTSTATUS status;
    CONTEXT ctx;

    if (!PyArg_ParseTuple(args, "k", &handle)) {
        return NULL;
    }

    ctx.ContextFlags = CONTEXT_CONTROL;
    status = NtGetContextThread(handle, &ctx);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }
    ctx.EFlags |= 0x100U;
    status = NtSetContextThread(handle, &ctx);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    Py_RETURN_NONE;
}

/*** Virtual memory routines ***/

PyDoc_STRVAR(vmem_read__doc__,
"vmem_read(hprocess, address, size) -> string\n\n\
Read the process' memory.");

static PyObject *
vmem_read(PyObject *self, PyObject *args)
{
    HANDLE handle;
    NTSTATUS status;
    PVOID address;
    Py_uintptr_t size;
    PyObject *buffer;
    ULONG read;

    if (!PyArg_ParseTuple(args, "kkk", &handle, &address, &size)) {
        goto exit0;
    }

    buffer = PyString_FromStringAndSize(NULL, size);
    if (!buffer) {
        goto exit0;
    }

    status = NtReadVirtualMemory(
        handle,
        address,
        PyString_AS_STRING(buffer),
        size,
        &read);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        goto exit1;
    }

    if (read != size) {
        if (_PyString_Resize(&buffer, read) < 0) {
            goto exit1;
        }
    }

    return buffer;

exit1:
    Py_DECREF(buffer);
exit0:
    return NULL;
}

PyDoc_STRVAR(vmem_write__doc__,
"vmem_write(hprocess, address, buffer)\n\n\
Write the process' memory.");

static PyObject *
vmem_write(PyObject *self, PyObject *args)
{
    HANDLE handle;
    NTSTATUS status;
    PVOID address;
    PyObject *buffer;
    ULONG written;

    if (!PyArg_ParseTuple(args, "kkO", &handle, &address, &buffer)) {
        return NULL;
    }

    if (!PyString_CheckExact(buffer)) {
        PyErr_SetString(PyExc_TypeError, "Expected data to be a string.");
        return NULL;
    }

    status = NtWriteVirtualMemory(
        handle,
        address,
        PyString_AS_STRING(buffer),
        PyString_Size(buffer),
        &written);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    /* TODO: Verify all data has been written */

    Py_RETURN_NONE;
}

PyDoc_STRVAR(vmem_query__doc__,
"vmem_query(hprocess, address) -> \n\
  (base_address, size, alloc_protect, curr_protect, state, type)\n\n\
Query the process' VM at the given address.");

static PyObject *
vmem_query(PyObject *self, PyObject *args)
{
    HANDLE handle;
    NTSTATUS status;
    PVOID address;
    MEMORY_BASIC_INFORMATION info;
    const char *state;
    const char *type;

    if (!PyArg_ParseTuple(args, "kk", &handle, &address)) {
        return NULL;
    }

    status = NtQueryVirtualMemory(
        handle,
        address,
        MemoryBasicInformation,
        &info,
        sizeof(info),
        NULL);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
    }

    switch (info.State) {
    case MEM_RESERVE: state = "reserved"; break;
    case MEM_COMMIT: state = "commit"; break;
    case MEM_FREE: state = "free"; break;
    }

    switch (info.Type) {
    case MEM_PRIVATE: type = "private"; break;
    case MEM_MAPPED: type = "mapped"; break;
    case SEC_IMAGE: type = "image"; break;
    }

    return Py_BuildValue("(kkkkss)",
        info.AllocationBase,
        info.RegionSize,
        info.AllocationProtect,
        info.Protect,
        state,
        type);
}

PyDoc_STRVAR(vmem_protect__doc__,
"vmem_protect(hprocess, address, size, protect) -> long\n\n\
Manipulate memory protection flags.");

static PyObject *
vmem_protect(PyObject *self, PyObject *args)
{
    HANDLE handle;
    NTSTATUS status;
    PVOID address;
    SIZE_T size;
    ULONG protect;
    ULONG oldprotect;

    if (!PyArg_ParseTuple(args, "kkkk", &handle, &address, &size, &protect)) {
        return NULL;
    }

    status = NtProtectVirtualMemory(
        handle,
        &address,
        &size,
        protect,
        &oldprotect);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    return PyLong_FromUnsignedLong(oldprotect);
}

PyDoc_STRVAR(vmem_query_section_name__doc__,
"vmem_query_section_name(hprocess, address) -> string\n\n\
Query the file name of a section at the given address.");

static PyObject *
vmem_query_section_name(PyObject *self, PyObject *args)
{
    HANDLE handle;
    NTSTATUS status;
    PVOID address;
    union {
        MEMORY_SECTION_NAME info;
        WCHAR __space[0x210];
    } buffer;

    if (!PyArg_ParseTuple(args, "kk", &handle, &address)) {
        return NULL;
    }

    status = NtQueryVirtualMemory(
        handle,
        address,
        MemorySectionName,
        &buffer,
        sizeof(buffer),
        NULL);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    return PyUnicode_FromUnicode(
        buffer.info.SectionFileName.Buffer,
        buffer.info.SectionFileName.Length / sizeof(WCHAR));
}

/*** Module housekeeping routines ***/

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

/* Module method definitions */
static PyMethodDef methods[] = {
    { "process_get_peb", (PyCFunction)process_get_peb, METH_VARARGS, process_get_peb__doc__ },
    { "process_terminate", (PyCFunction)process_terminate, METH_VARARGS, process_terminate__doc__ },

    { "thread_get_teb", (PyCFunction)thread_get_teb, METH_VARARGS, thread_get_teb__doc__ },
    { "thread_get_context", (PyCFunction)thread_get_context, METH_VARARGS, thread_get_context__doc__ },
    { "thread_set_context", (PyCFunction)thread_set_context, METH_VARARGS, thread_set_context__doc__ },
    { "thread_set_single_step", (PyCFunction)thread_set_single_step, METH_VARARGS, thread_set_single_step__doc__ },

    { "vmem_read", (PyCFunction)vmem_read, METH_VARARGS, vmem_read__doc__ },
    { "vmem_write", (PyCFunction)vmem_write, METH_VARARGS, vmem_write__doc__ },
    { "vmem_query", (PyCFunction)vmem_query, METH_VARARGS, vmem_query__doc__ },
    { "vmem_protect", (PyCFunction)vmem_protect, METH_VARARGS, vmem_protect__doc__ },
    { "vmem_query_section_name", (PyCFunction)vmem_query_section_name, METH_VARARGS, vmem_query_section_name__doc__ },

    {NULL}  /* Sentinel */
};

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
    ready_add_type(m, "EFlags", &PyBones_EFlags_Type);
    PyBones_Context_Type.tp_new = PyType_GenericNew;
    ready_add_type(m, "Context", &PyBones_Context_Type);

    ready_add_type(m, "ProcessMonitor", &PyBones_ProcessMonitor_Type);
}
