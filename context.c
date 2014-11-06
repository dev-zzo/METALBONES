#include <Python.h>
#include <Windows.h>

#include "internal.h"

#define REG_LONG32  (1<<31)
#define REG_LONGDBL (1<<30)
#define OFFSET_MASK 0x000FFFFF

typedef struct {
    PyObject_HEAD

    CONTEXT ctx;
} PyBones_ContextObject;

int
_PyBones_Context_Get(PyBones_ContextObject *self, HANDLE thread)
{
    self->ctx.ContextFlags = CONTEXT_ALL;
    if (!GetThreadContext(thread, &self->ctx)) {
        PyErr_SetObject(PyBones_Win32Error, PyInt_FromLong(GetLastError()));
        return -1;
    }
    return 0;
}

int
_PyBones_Context_Set(PyBones_ContextObject *self, HANDLE thread)
{
    if (!SetThreadContext(thread, &self->ctx)) {
        PyErr_SetObject(PyBones_Win32Error, PyInt_FromLong(GetLastError()));
        return -1;
    }
    return 0;
}

int
PyBones_Context_Check(PyObject *o)
{
    return Py_TYPE(o) == &PyBones_Context_Type;
}

static PyObject *
to_str(PyBones_ContextObject *self)
{
    PCONTEXT c = &self->ctx;
    char buffer[512];

    sprintf(buffer,
        "eax=%08x ebx=%08x ecx=%08x edx=%08x esi=%08x edi=%08x\n"
        "eip=%08x esp=%08x ebp=%08x efl=%08x %s\n"
        "cs=%04x  ss=%04x  ds=%04x es=%04x  fs=%04x  gs=%04x",
        c->Eax, c->Ebx, c->Ecx, c->Edx, c->Esi, c->Edi,
        c->Eip, c->Esp, c->Ebp, c->EFlags, "FLAGS",
        c->SegCs, c->SegSs, c->SegDs, c->SegEs, c->SegFs, c->SegGs);
    return PyString_FromString(buffer);
}

static PyObject *
get_reg(PyBones_ContextObject *self, int id)
{
    int offset = id & OFFSET_MASK;

    if (id & REG_LONG32) {
        return PyLong_FromUnsignedLong(*(unsigned long *)((char *)&self->ctx + offset));
    }

    if (id & REG_LONGDBL) {
    }

    return NULL;
}

static int
set_reg(PyBones_ContextObject *self, PyObject *value, int id)
{
    int offset = id & OFFSET_MASK;

    if (!value) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete this attribute.");
        return -1;
    }

    if (id & REG_LONG32) {
        if (!PyInt_Check(value) && !PyLong_Check(value)) {
            PyErr_SetString(PyExc_TypeError, "Expected an instance of int or long.");
            return NULL;
        }
    }
    if (id & REG_LONGDBL) {
        if (!PyFloat_Check(value)) {
            PyErr_SetString(PyExc_TypeError, "Expected an instance of float.");
            return NULL;
        }
    }

}

static PyGetSetDef getseters[] = {
    /* name, get, set, doc, closure */
    { "dr0", (getter)get_reg, (setter)set_reg, "DR0", REG_LONG32 | offsetof(CONTEXT, Dr0) },
    { "dr1", (getter)get_reg, (setter)set_reg, "DR1", REG_LONG32 | offsetof(CONTEXT, Dr1) },
    { "dr2", (getter)get_reg, (setter)set_reg, "DR2", REG_LONG32 | offsetof(CONTEXT, Dr2) },
    { "dr3", (getter)get_reg, (setter)set_reg, "DR3", REG_LONG32 | offsetof(CONTEXT, Dr3) },
    { "dr6", (getter)get_reg, (setter)set_reg, "DR6", REG_LONG32 | offsetof(CONTEXT, Dr6) },
    { "dr7", (getter)get_reg, (setter)set_reg, "DR7", REG_LONG32 | offsetof(CONTEXT, Dr7) },

    { "gs", (getter)get_reg, (setter)set_reg, "GS", REG_LONG32 | offsetof(CONTEXT, SegGs) },
    { "fs", (getter)get_reg, (setter)set_reg, "FS", REG_LONG32 | offsetof(CONTEXT, SegFs) },
    { "es", (getter)get_reg, (setter)set_reg, "ES", REG_LONG32 | offsetof(CONTEXT, SegEs) },
    { "ds", (getter)get_reg, (setter)set_reg, "DS", REG_LONG32 | offsetof(CONTEXT, SegDs) },
    { "cs", (getter)get_reg, (setter)set_reg, "CS", REG_LONG32 | offsetof(CONTEXT, SegCs) },
    { "ss", (getter)get_reg, (setter)set_reg, "SS", REG_LONG32 | offsetof(CONTEXT, SegSs) },

    { "edi", (getter)get_reg, (setter)set_reg, "EDI", REG_LONG32 | offsetof(CONTEXT, Edi) },
    { "esi", (getter)get_reg, (setter)set_reg, "ESI", REG_LONG32 | offsetof(CONTEXT, Esi) },
    { "ebx", (getter)get_reg, (setter)set_reg, "EBX", REG_LONG32 | offsetof(CONTEXT, Ebx) },
    { "ecx", (getter)get_reg, (setter)set_reg, "ECX", REG_LONG32 | offsetof(CONTEXT, Ecx) },
    { "edx", (getter)get_reg, (setter)set_reg, "EDX", REG_LONG32 | offsetof(CONTEXT, Edx) },
    { "eax", (getter)get_reg, (setter)set_reg, "EAX", REG_LONG32 | offsetof(CONTEXT, Eax) },

    { "ebp", (getter)get_reg, (setter)set_reg, "EBP", REG_LONG32 | offsetof(CONTEXT, Ebp) },
    { "esp", (getter)get_reg, (setter)set_reg, "ESP", REG_LONG32 | offsetof(CONTEXT, Esp) },
    { "eip", (getter)get_reg, (setter)set_reg, "EIP", REG_LONG32 | offsetof(CONTEXT, Eip) },
    { "eflags", (getter)get_reg, (setter)set_reg, "EFlags", REG_LONG32 | offsetof(CONTEXT, EFlags) },

    {NULL}  /* Sentinel */
};

PyTypeObject PyBones_Context_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "bones.Context",  /*tp_name*/
    sizeof(PyBones_ContextObject),  /*tp_basicsize*/
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
    (reprfunc)to_str,  /*tp_str*/
    0,  /*tp_getattro*/
    0,  /*tp_setattro*/
    0,  /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,  /*tp_flags*/
    "Thread context object",  /*tp_doc*/
    0,  /* tp_traverse */
    0,  /* tp_clear */
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
    0,  /* tp_init */
    0,  /* tp_alloc */
    0,  /* tp_new */
};
