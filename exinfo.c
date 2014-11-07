#include <Python.h>
#include <Windows.h>

#include "internal.h"
#include "winternals.h"

typedef struct {
    PyObject_HEAD

    UINT code; /* Exception code */
    int noncontinuable; /* Whether the exception is continuable. */
    PVOID address;
    PyObject * nested; /* Nested exception, if any */
} PyBones_ExceptionInfoObject;


static void
exinfo_dealloc(PyBones_ExceptionInfoObject *self)
{
    Py_XDECREF(self->nested);
    self->ob_type->tp_free((PyObject*)self);
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
    0,  /*tp_str*/
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


typedef struct {
    PyBones_ExceptionInfoObject ei;

    int access_type; /* 0 = read, 1 = write, 8 = dep */
    PVOID data_address; /* Faulty access address */
} PyBones_AccessViolationInfoObject;

static PyObject *
get_access_type(PyBones_AccessViolationInfoObject *self, void *closure)
{
    switch (self->access_type) {
    case 0:
        return PyString_FromString("read");
    case 1:
        return PyString_FromString("write");
    case 8:
        return PyString_FromString("dep");
    default:
        /* Raise an exception? */
        return PyString_FromString("UNKNOWN");
    }
}

static PyObject *
get_data_address(PyBones_AccessViolationInfoObject *self, void *closure)
{
    return PyLong_FromUnsignedLong((UINT_PTR)self->data_address);
}

static PyGetSetDef avinfo_getseters[] = {
    /* name, get, set, doc, closure */
    { "access_type", (getter)get_access_type, NULL, "Access type: 'read', 'write', 'dep'", NULL },
    { "data_address", (getter)get_data_address, NULL, "Accessing this address caused the AV", NULL },
    {NULL}  /* Sentinel */
};

PyTypeObject PyBones_AccessViolationInfo_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "_bones.AccessViolationInfo",  /*tp_name*/
    sizeof(PyBones_AccessViolationInfoObject),  /*tp_basicsize*/
    0,  /*tp_itemsize*/
    0,  /*tp_dealloc*/
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
    Py_TPFLAGS_DEFAULT,  /*tp_flags*/
    "AccessViolationInfo object",  /*tp_doc*/
    0,  /* tp_traverse */
    0,  /* tp_clear */
    0,  /* tp_richcompare */
    0,  /* tp_weaklistoffset */
    0,  /* tp_iter */
    0,  /* tp_iternext */
    0,  /* tp_methods */
    0,  /* tp_members */
    avinfo_getseters,  /* tp_getset */
    &PyBones_ExceptionInfo_Type,  /* tp_base */
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

    if (record->ExceptionRecord) {
        nested_info = _PyBones_ExceptionInfo_Translate(record->ExceptionRecord);
        if (!nested_info)
            return NULL;
    }
    else {
        Py_INCREF(Py_None);
        nested_info = Py_None;
    }

    if (record->ExceptionCode == STATUS_ACCESS_VIOLATION) {
        info = (PyBones_ExceptionInfoObject *)PyBones_AccessViolationInfo_Type.tp_alloc(&PyBones_AccessViolationInfo_Type, 0);
    }
    else {
        info = (PyBones_ExceptionInfoObject *)PyBones_ExceptionInfo_Type.tp_alloc(&PyBones_ExceptionInfo_Type, 0);
    }
    if (!info) {
        Py_DECREF(nested_info);
        return NULL;
    }

    info->code = record->ExceptionCode;
    info->address = record->ExceptionAddress;
    info->noncontinuable = !!record->ExceptionFlags;
    info->nested = nested_info;

    if (record->ExceptionCode == STATUS_ACCESS_VIOLATION) {
        PyBones_AccessViolationInfoObject *avinfo = (PyBones_AccessViolationInfoObject *)info;
        avinfo->access_type = record->ExceptionInformation[0];
        avinfo->data_address = (PVOID)record->ExceptionInformation[1];
    }

    return (PyObject *)info;
}
