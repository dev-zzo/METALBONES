#include <Python.h>
#include <Windows.h>

#include "bones.h"

/* Thread object */

typedef struct {
    PyObject_HEAD

    UINT id; /* Unique thread ID */
    PyObject * process; /* Owning process */
    PVOID start_address; /* Where the thread starts */
    PVOID teb_address; /* Address of the thread's environment block */

} PyBones_ThreadObject;

/* Thread type methods */

static int
traverse(PyBones_ThreadObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->process);
    return 0;
}

static int
clear(PyBones_ThreadObject *self)
{
    Py_CLEAR(self->process);
    return 0;
}

static void
dealloc(PyBones_ThreadObject *self)
{
    clear(self);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyBones_ThreadObject *self;

    self = (PyBones_ThreadObject *)type->tp_alloc(type, 0);
    if (self != NULL)
    {
        /* Init fields */
        self->id = 0;
        Py_INCREF(Py_None);
        self->process = Py_None;
        self->start_address = 0;
        self->teb_address = 0;
    }

    return (PyObject *)self;
}

static int
init(PyBones_ThreadObject *self, PyObject *args, PyObject *kwds)
{
    PyObject *process = NULL;

    /* id, process, start_address, teb_address */
    if (!PyArg_ParseTuple(args, "iOkk", &self->id, &process, &self->start_address, &self->teb_address))
    {
        return -1;
    }

    if (process)
    {
        PyObject *tmp = self->process;
        Py_INCREF(process);
        self->process = process;
        Py_XDECREF(tmp);
    }

    return 0;
}

/* Thread object field accessors */

static PyObject *
get_id(PyBones_ThreadObject *self, void *closure)
{
    return PyInt_FromLong(self->id);
}

static PyObject *
get_process(PyBones_ThreadObject *self, void *closure)
{
    PyObject *p = self->process;
    Py_INCREF(p);
    return p;
}

static PyObject *
get_start_address(PyBones_ThreadObject *self, void *closure)
{
    return PyLong_FromUnsignedLong((UINT_PTR)self->start_address);
}

static PyObject *
get_teb_address(PyBones_ThreadObject *self, void *closure)
{
    return PyLong_FromUnsignedLong((UINT_PTR)self->teb_address);
}

static PyGetSetDef getseters[] =
{
    /* name, get, set, doc, closure */
    { "id", (getter)get_id, NULL, "Unique thread ID", NULL },
    { "process", (getter)get_process, NULL, "Owning process", NULL },
    { "start_address", (getter)get_start_address, NULL, "Thread starting address", NULL },
    { "teb_address", (getter)get_teb_address, NULL, "Address of thread's enviroment block", NULL },
    {NULL}  /* Sentinel */
};

/* Thread object type */

PyTypeObject PyBones_Thread_Type =
{
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "bones.Thread",  /*tp_name*/
    sizeof(PyBones_ThreadObject),  /*tp_basicsize*/
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
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC,  /*tp_flags*/
    "Thread object",  /*tp_doc*/
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