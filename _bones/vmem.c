#include <Python.h>
#include <Windows.h>

#include "ntdll.h"
#include "internal.h"

PyDoc_STRVAR(vmem_read__doc__,
"vmem_read(hprocess, address, size) -> string\n\n\
Read the process' memory.");

static PyObject *
vmem_read(PyObject *self, PyObject *args)
{
    HANDLE process;
    NTSTATUS status;
    PVOID address;
    Py_uintptr_t size;
    PyObject *buffer;
    ULONG read;

    if (!PyArg_ParseTuple(args, "kkk", &process, &address, &size)) {
        goto exit0;
    }

    buffer = PyString_FromStringAndSize(NULL, size);
    if (!buffer) {
        goto exit0;
    }

    status = NtReadVirtualMemory(
        process,
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
    HANDLE process;
    NTSTATUS status;
    PVOID address;
    PyObject *buffer;
    ULONG written;

    if (!PyArg_ParseTuple(args, "kkO", &process, &address, &buffer)) {
        return NULL;
    }

    if (!PyString_CheckExact(buffer)) {
        PyErr_SetString(PyExc_TypeError, "Expected data to be a string.");
        return NULL;
    }

    status = NtWriteVirtualMemory(
        process,
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
    HANDLE process;
    NTSTATUS status;
    PVOID address;
    MEMORY_BASIC_INFORMATION info;
    const char *state;
    const char *type;

    if (!PyArg_ParseTuple(args, "kk", &process, &address)) {
        return NULL;
    }

    status = NtQueryVirtualMemory(
        process,
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
    HANDLE process;
    NTSTATUS status;
    PVOID address;
    SIZE_T size;
    ULONG protect;
    ULONG oldprotect;

    if (!PyArg_ParseTuple(args, "kkkk", &process, &address, &size, &protect)) {
        return NULL;
    }

    status = NtProtectVirtualMemory(
        process,
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

static PyMethodDef methods[] = {
    { "vmem_read", (PyCFunction)vmem_read, METH_VARARGS|METH_STATIC, vmem_read__doc__ },
    { "vmem_write", (PyCFunction)vmem_write, METH_VARARGS|METH_STATIC, vmem_write__doc__ },
    { "vmem_query", (PyCFunction)vmem_query, METH_VARARGS|METH_STATIC, vmem_query__doc__ },
    { "vmem_protect", (PyCFunction)vmem_protect, METH_VARARGS|METH_STATIC, vmem_protect__doc__ },
    {NULL}  /* Sentinel */
};

int
init_VMem(PyObject* m)
{
    PyMethodDef *ml;

    ml = methods;
    while (ml->ml_meth) {
        PyObject *f;

        f = PyCFunction_New(ml, NULL);
        PyModule_AddObject(m, ml->ml_name, f);
        ++ml;
    }

    return 0;
}

