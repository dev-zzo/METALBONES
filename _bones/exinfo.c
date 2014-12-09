#include <Python.h>
#include <Windows.h>

#include "internal.h"

typedef struct {
    PyObject_HEAD

    UINT code; /* Exception code */
    int noncontinuable; /* Whether the exception is continuable. */
    PVOID address;
    PyObject *args; /* A tuple of arguments, if any */
    PyObject *nested; /* Nested exception, if any */
} PyBones_ExceptionInfoObject;

static void
exinfo_dealloc(PyBones_ExceptionInfoObject *self)
{
    Py_XDECREF(self->args);
    Py_XDECREF(self->nested);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
exinfo_to_str(PyBones_ExceptionInfoObject *self)
{
    char buffer[128];
    PyObject *result;

    sprintf(buffer, "Exception %08x at %08x", self->code, self->address);
    result = PyString_FromString(buffer);
    if (!result) {
        return NULL;
    }

    if (self->nested && self->nested != Py_None) {
        PyObject *nested_str;

        nested_str = PyObject_Str(self->nested);
        if (!nested_str) {
            Py_DECREF(result);
            return NULL;
        }

        PyString_ConcatAndDel(&result, PyString_FromString("\n"));
        PyString_ConcatAndDel(&result, nested_str);
    }

    return result;
}

static PyObject *
get_code(PyBones_ExceptionInfoObject *self, void *closure)
{
    return PyLong_FromUnsignedLong(self->code);
}

static PyObject *
get_address(PyBones_ExceptionInfoObject *self, void *closure)
{
    return PyLong_FromUnsignedLong((UINT_PTR)self->address);
}

static PyObject *
get_noncontinuable(PyBones_ExceptionInfoObject *self, void *closure)
{
    return PyBool_FromLong(self->noncontinuable);
}

static PyObject *
get_args(PyBones_ExceptionInfoObject *self, void *closure)
{
    PyObject *p = self->args;
    Py_INCREF(p);
    return p;
}

static PyObject *
get_nested(PyBones_ExceptionInfoObject *self, void *closure)
{
    PyObject *p = self->nested;
    Py_INCREF(p);
    return p;
}

static PyGetSetDef exinfo_getseters[] = {
    /* name, get, set, doc, closure */
    { "code", (getter)get_code, NULL, "Exception code", NULL },
    { "address", (getter)get_address, NULL, "Address of the offending instruction", NULL },
    { "noncontinuable", (getter)get_noncontinuable, NULL, "Whether the exception is fatal", NULL },
    { "args", (getter)get_args, NULL, "A tuple of exception arguments", NULL },
    { "nested", (getter)get_nested, NULL, "Nested exception, if any", NULL },
    {NULL}  /* Sentinel */
};

PyTypeObject PyBones_ExceptionInfo_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "_bones.ExceptionInfo",  /*tp_name*/
    sizeof(PyBones_ExceptionInfoObject),  /*tp_basicsize*/
    0,  /*tp_itemsize*/
    (destructor)exinfo_dealloc,  /*tp_dealloc*/
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
    (reprfunc)exinfo_to_str,  /*tp_str*/
    0,  /*tp_getattro*/
    0,  /*tp_setattro*/
    0,  /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,  /*tp_flags*/
    "ExceptionInfo object",  /*tp_doc*/
    0,  /* tp_traverse */
    0,  /* tp_clear */
    0,  /* tp_richcompare */
    0,  /* tp_weaklistoffset */
    0,  /* tp_iter */
    0,  /* tp_iternext */
    0,  /* tp_methods */
    0,  /* tp_members */
    exinfo_getseters,  /* tp_getset */
    0,  /* tp_base */
    0,  /* tp_dict */
    0,  /* tp_descr_get */
    0,  /* tp_descr_set */
    0,  /* tp_dictoffset */
    0,  /* tp_init */
    0,  /* tp_alloc */
    0,  /* tp_new */
};

PyObject *
_PyBones_ExceptionInfo_Translate(void *data)
{
    PEXCEPTION_RECORD record = (PEXCEPTION_RECORD)data;
    PyBones_ExceptionInfoObject *info;
    PyObject *nested_info;
    Py_ssize_t num_args;
    Py_ssize_t pos;

    if (record->ExceptionRecord) {
        nested_info = _PyBones_ExceptionInfo_Translate(record->ExceptionRecord);
        if (!nested_info)
            return NULL;
    }
    else {
        Py_INCREF(Py_None);
        nested_info = Py_None;
    }

    info = (PyBones_ExceptionInfoObject *)PyBones_ExceptionInfo_Type.tp_alloc(&PyBones_ExceptionInfo_Type, 0);
    if (!info) {
        Py_DECREF(nested_info);
        return NULL;
    }

    info->code = record->ExceptionCode;
    info->address = record->ExceptionAddress;
    info->noncontinuable = !!record->ExceptionFlags;
    info->nested = nested_info;
    num_args = record->NumberParameters; /* or EXCEPTION_MAXIMUM_PARAMETERS? */
    info->args = PyTuple_New(num_args);
    if (!info->args) {
        Py_DECREF(info);
        return NULL;
    }

    for (pos = 0; pos < num_args; ++pos) {
        PyTuple_SET_ITEM(info->args, pos, PyLong_FromUnsignedLong(record->ExceptionInformation[pos]));
    }

    return (PyObject *)info;
}
