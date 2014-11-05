#include <Python.h>
#include <Windows.h>

#include "internal.h"

/* Process object */

typedef struct {
    PyObject_HEAD

    UINT id; /* Unique process ID */
    HANDLE handle; /* Process handle */
    PVOID image_base; /* Base address of the process image */
    NTSTATUS exit_status; /* Filled when a process exits */

    PyObject *threads; /* A dict mapping thread id -> thread object */

} PyBones_ProcessObject;

/* Process type methods */

static int
traverse(PyBones_ProcessObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->threads);
    return 0;
}

static int
clear(PyBones_ProcessObject *self)
{
    Py_CLEAR(self->threads);
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
        /* Init fields */
        self->id = 0;
        self->handle = NULL;
        self->image_base = NULL;
        self->exit_status = 0;
        self->threads = PyDict_New();
        if (!self->threads) {
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

    /* id, handle, image_base */
    if (!PyArg_ParseTuple(args, "ikk", &self->id, &self->handle, &self->image_base)) {
        return -1;
    }

    return 0;
}

int
_PyBones_Process_AddThread(PyBones_ProcessObject *self, PyObject *thread_id, PyObject *thread)
{
    return PyDict_SetItem(self->threads, thread_id, thread);
}

PyObject *
_PyBones_Process_DelThread(PyBones_ProcessObject *self, PyObject *thread_id)
{
    PyObject *thread;
    
    thread = PyDict_GetItem(self->threads, thread_id);
    if (thread) {
        Py_INCREF(thread);
        PyDict_DelItem(self->threads, thread_id);
    }
    return thread;
}

/* Process object field accessors */

void
_PyBones_Process_SetExitStatus(PyBones_ProcessObject *self, UINT status)
{
    self->exit_status = status;
}

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

static PyObject *
get_threads(PyBones_ProcessObject *self, void *closure)
{
    return PyDictProxy_New(self->threads);
}

static PyGetSetDef getseters[] = {
    /* name, get, set, doc, closure */
    { "id", (getter)get_id, NULL, "Unique process ID", NULL },
    { "image_base", (getter)get_image_base, NULL, "Process image base address", NULL },
    { "exit_status", (getter)get_exit_status, NULL, "Exit status -- set when the process exits", NULL },
    { "threads", (getter)get_threads, NULL, "Threads running within the process", NULL },
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
    0,  /* tp_methods */
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

