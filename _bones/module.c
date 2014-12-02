#include <Python.h>
#include <Windows.h>

#include "internal.h"
#include "winternals.h"

typedef struct {
    PyObject_HEAD
    PVOID base_address; /* Base address of the module */
    PyObject *process; /* The process where this module is mapped to */
    PyObject *name; /* Human-friendly name of the module, if one exists */
    PyObject *path; /* Full path to the module */
} PyBones_ModuleObject;

static int
traverse(PyBones_ModuleObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->process);
    return 0;
}

static int
clear(PyBones_ModuleObject *self)
{
    Py_CLEAR(self->process);
    Py_CLEAR(self->name);
    Py_CLEAR(self->path);
    return 0;
}

static void
dealloc(PyBones_ModuleObject *self)
{
    clear(self);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyBones_ModuleObject *self;

    self = (PyBones_ModuleObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        /* Init fields */
        Py_INCREF(Py_None);
        self->process = Py_None;
    }

    return (PyObject *)self;
}

static int
init(PyBones_ModuleObject *self, PyObject *args, PyObject *kwds)
{
    PyObject *tmp;
    PyObject *process = NULL;

    /* base_address, process */
    if (!PyArg_ParseTuple(args, "kO",
        &self->base_address,
        &process)) {
        return -1;
    }

    if (process) {
        tmp = self->process;
        Py_INCREF(process);
        self->process = process;
        Py_XDECREF(tmp);
    }

    return 0;
}

static PyObject *
get_base_address(PyBones_ModuleObject *self, void *closure)
{
    return PyLong_FromUnsignedLong((UINT_PTR)self->base_address);
}

static PyObject *
get_process(PyBones_ModuleObject *self, void *closure)
{
    PyObject *p = self->process;
    Py_INCREF(p);
    return p;
}

static PyObject *
get_entry_point(PyBones_ModuleObject *self, void *closure)
{
    unsigned lfa_new;
    IMAGE_NT_HEADERS32 headers;

    if (PyBones_Process_ReadMemoryPtr(self->process, (char *)self->base_address + 0x3C, sizeof(lfa_new), &lfa_new) < 0) {
        return NULL;
    }

    if (PyBones_Process_ReadMemoryPtr(self->process, (char *)self->base_address + lfa_new, sizeof(headers), &headers) < 0) {
        return NULL;
    }

    return PyLong_FromUnsignedLong((unsigned long)((char *)self->base_address + headers.OptionalHeader.AddressOfEntryPoint));
}

static PyGetSetDef getseters[] = {
    /* name, get, set, doc, closure */
    { "base_address", (getter)get_base_address, NULL, "Module base address", NULL },
    { "process", (getter)get_process, NULL, "Owning process", NULL },
    { "entry_point", (getter)get_entry_point, NULL, "Module entry point address", NULL },
    {NULL}  /* Sentinel */
};

PyTypeObject PyBones_Module_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "_bones.Module",  /*tp_name*/
    sizeof(PyBones_ModuleObject),  /*tp_basicsize*/
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
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_BASETYPE,  /*tp_flags*/
    "Module object",  /*tp_doc*/
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
