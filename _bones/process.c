#include <Python.h>
#include <Windows.h>

#include "internal.h"
#include "ntdll.h"

/* Process object */

typedef struct {
    PyObject_HEAD

    UINT id; /* Unique process ID */
    HANDLE handle; /* Process handle */
    PVOID image_base; /* Base address of the process image */
    NTSTATUS exit_status; /* Filled when a process exits */

    PyObject *threads; /* A dict mapping thread id -> thread object */
    PyObject *modules; /* A dict mapping module base -> module object */

    PVOID peb_address; /* Address of the process' environment block */

} PyBones_ProcessObject;

/* Process type methods */

static int
process_traverse(PyBones_ProcessObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->threads);
    Py_VISIT(self->modules);
    return 0;
}

static int
process_clear(PyBones_ProcessObject *self)
{
    Py_CLEAR(self->threads);
    Py_CLEAR(self->modules);
    return 0;
}

static void
process_dealloc(PyBones_ProcessObject *self)
{
    process_clear(self);
    NtClose(self->handle);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
process_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyBones_ProcessObject *self;

    self = (PyBones_ProcessObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->threads = PyDict_New();
        if (!self->threads) {
            Py_DECREF(self);
            return NULL;
        }
        self->modules = PyDict_New();
        if (!self->modules) {
            Py_DECREF(self);
            return NULL;
        }
    }

    return (PyObject *)self;
}

static int
process_init(PyBones_ProcessObject *self, PyObject *args, PyObject *kwds)
{
    PyObject *process = NULL;
    NTSTATUS status;
    PROCESS_BASIC_INFORMATION pbi;

    /* id, handle, image_base */
    if (!PyArg_ParseTuple(args, "ikk", &self->id, &self->handle, &self->image_base)) {
        return -1;
    }

    status = NtQueryInformationProcess(
        self->handle,
        ProcessBasicInformation,
        &pbi,
        sizeof(pbi),
        NULL);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        Py_DECREF(self);
        return -1;
    }

    self->peb_address = pbi.PebBaseAddress;

    return 0;
}

static PyObject *
remove_kv(PyObject *dict, PyObject *key)
{
    PyObject *value;
    
    value = PyDict_GetItem(dict, key);
    if (value) {
        Py_INCREF(value);
        if (PyDict_DelItem(dict, key) < 0) {
            Py_DECREF(value);
            value = NULL;
        }
    }
    else if (!PyErr_Occurred()) {
        /* No such thread */
        Py_INCREF(Py_None);
        value = Py_None;
    }
    return value;
}

HANDLE
_PyBones_Process_GetHandle(PyObject *self)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    return _self->handle;
}

void *
_PyBones_Process_GetPebAddress(PyObject *self)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    return _self->peb_address;
}

PyObject *
PyBones_Process_ReadMemory(PyObject *self, void *address, unsigned size)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    NTSTATUS status;
    PyObject *buffer;
    unsigned read;

    buffer = PyString_FromStringAndSize(NULL, size);
    if (!buffer) {
        goto exit0;
    }

    status = NtReadVirtualMemory(
        _self->handle,
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

int
PyBones_Process_ReadMemoryPtr(PyObject *self, void *address, unsigned size, void* dest)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    NTSTATUS status;

    status = NtReadVirtualMemory(
        _self->handle,
        address,
        dest,
        size,
        NULL);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return -1;
    }

    return 0;
}

PyObject *
PyBones_Process_WriteMemory(PyObject *self, void *address, unsigned size, PyObject *buffer)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    NTSTATUS status;
    unsigned written;

    status = NtWriteVirtualMemory(
        _self->handle,
        address,
        PyString_AS_STRING(buffer),
        size,
        &written);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    Py_RETURN_NONE;
}

PyObject *
PyBones_Process_QueryMemory(PyObject *self, void *address)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    NTSTATUS status;
    MEMORY_BASIC_INFORMATION info;
    const char *state;
    const char *type;

    status = NtQueryVirtualMemory(
        _self->handle,
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

int
PyBones_Process_ProtectMemory(PyObject *self, void *address, unsigned size, unsigned protect, unsigned *oldprotect)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    NTSTATUS status;

    status = NtProtectVirtualMemory(
        _self->handle,
        &address,
        &size,
        protect,
        oldprotect);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return -1;
    }

    return 0;
}

PyObject *
PyBones_Process_GetSectionFileName(PyObject *self, void *address)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    NTSTATUS status;
    union {
        MEMORY_SECTION_NAME info;
        WCHAR __space[0x210];
    } buffer;

    status = NtQueryVirtualMemory(
        _self->handle,
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


PyDoc_STRVAR(terminate__doc__,
"terminate(self, exit_code)\n\n\
Start the termination of this process.");

static PyObject *
process_terminate(PyObject *self, PyObject *args)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    PyObject *result = NULL;
    NTSTATUS status;
    UINT exit_code = 0xDEADBEEF;

    if (!PyArg_ParseTuple(args, "I", &exit_code)) {
        return NULL;
    }

    status = NtTerminateProcess(_self->handle, exit_code);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

PyDoc_STRVAR(read_memory__doc__,
"read_memory(self, address, size) -> string\n\n\
Read the process' memory.");

static PyObject *
process_read_memory(PyObject *self, PyObject *args)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    PVOID address;
    unsigned size;

    if (!PyArg_ParseTuple(args, "kk", &address, &size)) {
        return NULL;
    }

    return PyBones_Process_ReadMemory(self, address, size);
}

PyDoc_STRVAR(write_memory__doc__,
"write_memory(self, address, size, data)\n\n\
Write the process' memory.");

static PyObject *
process_write_memory(PyObject *self, PyObject *args)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    PVOID address;
    unsigned size;
    PyObject *data;

    if (!PyArg_ParseTuple(args, "kkO", &address, &size, &data)) {
        return NULL;
    }

    if (!PyString_CheckExact(data)) {
        PyErr_SetString(PyExc_TypeError, "Expected data to be a string.");
        return NULL;
    }

    return PyBones_Process_WriteMemory(self, address, size, data);
}

PyDoc_STRVAR(query_memory__doc__,
"query_memory(self, address) -> \n\
  (base_address, size, alloc_protect, curr_protect, state, type)\n\n\
Query the process' VM at the given address.");

static PyObject *
process_query_memory(PyObject *self, PyObject *args)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    PVOID address;

    if (!PyArg_ParseTuple(args, "k", &address)) {
        return NULL;
    }

    return PyBones_Process_QueryMemory(self, address);
}

PyDoc_STRVAR(protect_memory__doc__,
"protect_memory(self, address, size, protect) -> long\n\n\
Manipulate memory protection flags.");

static PyObject *
process_protect_memory(PyObject *self, PyObject *args)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    PVOID address;
    unsigned size;
    unsigned protect;
    unsigned oldprotect;

    if (!PyArg_ParseTuple(args, "kkk", &address, &size, &protect)) {
        return NULL;
    }

    if (PyBones_Process_ProtectMemory(self, address, size, protect, &oldprotect) < 0) {
        return NULL;
    }

    return PyLong_FromUnsignedLong(oldprotect);
}

PyDoc_STRVAR(query_section_file_name__doc__,
"query_section_file_name(self, address) -> string\n\n\
Query the file name of a section at the given address.");

static PyObject *
process_query_section_file_name(PyObject *self, PyObject *args)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    PVOID address;

    if (!PyArg_ParseTuple(args, "k", &address)) {
        return NULL;
    }

    return PyBones_Process_GetSectionFileName(self, address);
}


static PyMethodDef methods[] = {
    { "terminate", (PyCFunction)process_terminate, METH_VARARGS, terminate__doc__ },
    { "read_memory", (PyCFunction)process_read_memory, METH_VARARGS, read_memory__doc__ },
    { "write_memory", (PyCFunction)process_write_memory, METH_VARARGS, write_memory__doc__ },
    { "query_memory", (PyCFunction)process_query_memory, METH_VARARGS, query_memory__doc__ },
    { "protect_memory", (PyCFunction)process_protect_memory, METH_VARARGS, protect_memory__doc__ },
    { "query_section_file_name", (PyCFunction)process_query_section_file_name, METH_VARARGS, query_section_file_name__doc__ },
    {NULL}  /* Sentinel */
};

/* Process object field accessors */

static PyObject *
process_get_id(PyBones_ProcessObject *self, void *closure)
{
    return PyInt_FromLong(self->id);
}

static PyObject *
process_get_image_base(PyBones_ProcessObject *self, void *closure)
{
    return PyLong_FromUnsignedLong((UINT_PTR)self->image_base);
}

static PyObject *
process_get_peb_address(PyBones_ProcessObject *self, void *closure)
{
    return PyLong_FromUnsignedLong((UINT_PTR)self->peb_address);
}

static PyObject *
process_get_exit_status(PyBones_ProcessObject *self, void *closure)
{
    return PyLong_FromUnsignedLong(self->exit_status);
}

static int
process_set_exit_status(PyBones_ProcessObject *self, PyObject *value, void *closure)
{
    if (!value) {
        PyErr_SetString(PyExc_TypeError, "The attribute cannot be deleted.");
        return -1;
    }

    if (PyInt_CheckExact(value)) {
        self->exit_status = (NTSTATUS)PyInt_AsLong(value);
        return 0;
    }
    if (PyLong_CheckExact(value)) {
        self->exit_status = (NTSTATUS)PyLong_AsUnsignedLong(value);
        return 0;
    }

    PyErr_SetString(PyExc_TypeError, "Expected an instance of int or long.");
    return -1;
}

static PyObject *
process_get_threads(PyBones_ProcessObject *self, void *closure)
{
    Py_INCREF(self->threads);
    return self->threads;
}

static PyObject *
process_get_modules(PyBones_ProcessObject *self, void *closure)
{
    Py_INCREF(self->modules);
    return self->modules;
}

static PyGetSetDef getseters[] = {
    /* name, get, set, doc, closure */
    { "id", (getter)process_get_id, NULL, "Unique process ID", NULL },
    { "image_base", (getter)process_get_image_base, NULL, "Process image base address", NULL },
    { "peb_address", (getter)process_get_peb_address, NULL, "Process Environment Block address", NULL },
    { "exit_status", (getter)process_get_exit_status, (setter)process_set_exit_status, "Exit status -- set when the process exits", NULL },
    { "threads", (getter)process_get_threads, NULL, "Threads running within the process", NULL },
    { "modules", (getter)process_get_modules, NULL, "Modules mapped within the process", NULL },
    {NULL}  /* Sentinel */
};

/* Process object type */

PyTypeObject PyBones_Process_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "_bones.Process",  /*tp_name*/
    sizeof(PyBones_ProcessObject),  /*tp_basicsize*/
    0,  /*tp_itemsize*/
    (destructor)process_dealloc,  /*tp_dealloc*/
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
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_BASETYPE,  /*tp_flags*/
    "Process object",  /*tp_doc*/
    (traverseproc)process_traverse,  /* tp_traverse */
    (inquiry)process_clear,  /* tp_clear */
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
    (initproc)process_init,  /* tp_init */
    0,  /* tp_alloc */
    process_new,  /* tp_new */
};

int
init_Process(PyObject* m)
{
    int rv;
    PyObject *tp_dict;

    tp_dict = PyDict_New();
    PyDict_SetItemString(tp_dict, "PAGE_NOACCESS",
        PyLong_FromUnsignedLong(0x00000001));
    PyDict_SetItemString(tp_dict, "PAGE_READONLY",
        PyLong_FromUnsignedLong(0x00000002));
    PyDict_SetItemString(tp_dict, "PAGE_READWRITE",
        PyLong_FromUnsignedLong(0x00000004));
    PyDict_SetItemString(tp_dict, "PAGE_WRITECOPY",
        PyLong_FromUnsignedLong(0x00000008));
    PyDict_SetItemString(tp_dict, "PAGE_EXECUTE",
        PyLong_FromUnsignedLong(0x00000010));
    PyDict_SetItemString(tp_dict, "PAGE_EXECUTE_READ",
        PyLong_FromUnsignedLong(0x00000020));
    PyDict_SetItemString(tp_dict, "PAGE_EXECUTE_READWRITE",
        PyLong_FromUnsignedLong(0x00000040));
    PyDict_SetItemString(tp_dict, "PAGE_EXECUTE_WRITECOPY",
        PyLong_FromUnsignedLong(0x00000080));
    PyDict_SetItemString(tp_dict, "PAGE_GUARD",
        PyLong_FromUnsignedLong(0x00000100));
    PyDict_SetItemString(tp_dict, "PAGE_NOCACHE",
        PyLong_FromUnsignedLong(0x00000200));
    PyDict_SetItemString(tp_dict, "PAGE_WRITECOMBINE",
        PyLong_FromUnsignedLong(0x00000400));
    PyBones_Process_Type.tp_dict = tp_dict;

    rv = PyType_Ready(&PyBones_Process_Type);
    if (rv < 0)
        return rv;

    Py_INCREF(&PyBones_Process_Type);
    return PyModule_AddObject(m, "Process", (PyObject *)&PyBones_Process_Type);
}
