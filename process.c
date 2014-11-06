#include <Python.h>
#include <Windows.h>

#include "internal.h"
#include "winternals.h"

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
traverse(PyBones_ProcessObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->threads);
    Py_VISIT(self->modules);
    return 0;
}

static int
clear(PyBones_ProcessObject *self)
{
    Py_CLEAR(self->threads);
    Py_CLEAR(self->modules);
    return 0;
}

static void
dealloc(PyBones_ProcessObject *self)
{
    clear(self);
    CloseHandle(self->handle);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
new(PyTypeObject *type, PyObject *args, PyObject *kwds)
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
init(PyBones_ProcessObject *self, PyObject *args, PyObject *kwds)
{
    PyObject *process = NULL;
    NTSTATUS status;
    PROCESS_BASIC_INFORMATION pbi;

    /* id, handle, image_base */
    if (!PyArg_ParseTuple(args, "ikk", &self->id, &self->handle, &self->image_base)) {
        return -1;
    }

    status = ZwQueryInformationProcess(
        self->handle,
        ProcessBasicInformation,
        &pbi,
        sizeof(pbi),
        NULL);
    if (!NT_SUCCESS(status)) {
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        Py_DECREF(self);
        return -1;
    }

    self->peb_address = pbi.PebBaseAddress;
    DEBUG_PRINT("BONES: peb = %08x\n", self->peb_address);

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

int
_PyBones_Process_AddThread(PyObject *self, PyObject *thread_id, PyObject *thread)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    return PyDict_SetItem(_self->threads, thread_id, thread);
}

int
_PyBones_Process_AddModule(PyObject *self, PyObject *base_address, PyObject *module)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    return PyDict_SetItem(_self->modules, base_address, module);
}

PyObject *
_PyBones_Process_DelThread(PyObject *self, PyObject *thread_id)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    return remove_kv(_self->threads, thread_id);
}

PyObject *
_PyBones_Process_DelModule(PyObject *self, PyObject *base_address)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    return remove_kv(_self->modules, base_address);
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

int
PyBones_Process_ReadMemoryPtr(PyObject *self, void *address, unsigned size, void *buffer)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    NTSTATUS status;
    int read = -1;

    status = NtReadVirtualMemory(
        _self->handle,
        address,
        buffer,
        size,
        &read);
    if (!NT_SUCCESS(status)) {
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
    }
    return read;
}

PyObject *
PyBones_Process_GetSectionFileNamePtr(PyObject *self, void *address)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    NTSTATUS status;
    union {
        MEMORY_SECTION_NAME info;
        WCHAR __space[0x210];
    } buffer;

    status = ZwQueryVirtualMemory(
        _self->handle,
        address,
        MemorySectionName,
        &buffer,
        sizeof(buffer),
        NULL);
    if (!NT_SUCCESS(status)) {
        PyErr_SetObject(PyBones_NtStatusError, PyLong_FromUnsignedLong(status));
        return NULL;
    }

    return PyUnicode_FromUnicode(
        buffer.info.SectionFileName.Buffer,
        buffer.info.SectionFileName.Length / sizeof(WCHAR));
}


PyDoc_STRVAR(terminate__doc__,
"terminate(self, exit_code)\n\n\
Start the termination of this process.");

PyObject *
PyBones_Process_Terminate(PyObject *self, PyObject *args)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    PyObject *result = NULL;
    UINT exit_code = 0xDEADBEEF;

    if (!PyArg_ParseTuple(args, "I", &exit_code)) {
        return NULL;
    }

    if (!TerminateProcess(_self->handle, exit_code)) {
        PyErr_SetObject(PyBones_Win32Error, PyInt_FromLong(GetLastError()));
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef methods[] = {
    { "terminate", (PyCFunction)PyBones_Process_Terminate, METH_VARARGS, terminate__doc__ },
    {NULL}  /* Sentinel */
};

/* Process object field accessors */

static PyObject *
get_id(PyBones_ProcessObject *self, void *closure)
{
    return PyInt_FromLong(self->id);
}

static PyObject *
get_image_base(PyBones_ProcessObject *self, void *closure)
{
    return PyLong_FromUnsignedLong((UINT_PTR)self->image_base);
}

static PyObject *
get_exit_status(PyBones_ProcessObject *self, void *closure)
{
    return PyLong_FromUnsignedLong(self->exit_status);
}

void
_PyBones_Process_SetExitStatus(PyObject *self, unsigned int status)
{
    PyBones_ProcessObject *_self = (PyBones_ProcessObject *)self;
    _self->exit_status = status;
}

static PyObject *
get_threads(PyBones_ProcessObject *self, void *closure)
{
    return PyDictProxy_New(self->threads);
}

static PyObject *
get_modules(PyBones_ProcessObject *self, void *closure)
{
    return PyDictProxy_New(self->modules);
}

static PyGetSetDef getseters[] = {
    /* name, get, set, doc, closure */
    { "id", (getter)get_id, NULL, "Unique process ID", NULL },
    { "image_base", (getter)get_image_base, NULL, "Process image base address", NULL },
    { "exit_status", (getter)get_exit_status, NULL, "Exit status -- set when the process exits", NULL },
    { "threads", (getter)get_threads, NULL, "Threads running within the process", NULL },
    { "modules", (getter)get_modules, NULL, "Modules mapped within the process", NULL },
    {NULL}  /* Sentinel */
};

/* Process object type */

PyTypeObject PyBones_Process_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "bones.Process",  /*tp_name*/
    sizeof(PyBones_ProcessObject),  /*tp_basicsize*/
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
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,  /*tp_flags*/
    "Process object",  /*tp_doc*/
    (traverseproc)traverse,  /* tp_traverse */
    (inquiry)clear,  /* tp_clear */
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

