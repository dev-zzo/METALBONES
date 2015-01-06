#include <Python.h>
#include <Windows.h>

#include "internal.h"
#include "ntdll.h"

typedef struct {
    PyObject_HEAD

    union {
        DWORD All;
        struct {
            DWORD CF : 1; /* Carry flag */
            DWORD : 1;
            DWORD PF : 1; /* Parity flag */
            DWORD : 1;
            DWORD AF : 1; /* Adjust flag */
            DWORD : 1;
            DWORD ZF : 1; /* Zero flag */
            DWORD SF : 1; /* Sign flag */

            DWORD TF : 1; /* Trap flag */
            DWORD IF : 1; /* Interrupt enable flag */
            DWORD DF : 1; /* Direction flag */
            DWORD OF : 1; /* Overflow flag */
            /* More here, but we don't care about those */
        };
    };
} PyBones_EFlagsObject;

static PyObject *
eflags_get_flag(PyBones_EFlagsObject *self, int bitpos)
{
    DWORD mask = 1 << bitpos;
    return PyBool_FromLong(!!(self->All & mask));
}

static int
eflags_set_flag(PyBones_EFlagsObject *self, PyObject *value, int bitpos)
{
    if (!PyBool_Check(value))
        return -1;

    if (value == Py_True) {
        self->All |= 1 << bitpos;
    }
    else {
        self->All &= ~(1 << bitpos);
    }
    return 0;
}

static void
eflags_sprintf(PyBones_EFlagsObject *self, char *buffer)
{
    sprintf(buffer, "%c %c %c %c %c %c %c %c",
        self->OF ? 'O' : 'o',
        self->DF ? 'D' : 'd',
        self->TF ? 'T' : 't',
        self->SF ? 'S' : 's',
        self->ZF ? 'Z' : 'z',
        self->AF ? 'A' : 'a',
        self->PF ? 'P' : 'p',
        self->CF ? 'C' : 'c');
}

static PyObject *
eflags_to_str(PyBones_EFlagsObject *self)
{
    char buffer[20];
    eflags_sprintf(self, buffer);
    return PyString_FromString(buffer);
}

static PyGetSetDef eflags_getseters[] = {
    /* name, get, set, doc, closure */
    { "cf", (getter)eflags_get_flag, (setter)eflags_set_flag, "Carry flag", (void *)0 },
    { "pf", (getter)eflags_get_flag, (setter)eflags_set_flag, "Parity flag", (void *)2 },
    { "af", (getter)eflags_get_flag, (setter)eflags_set_flag, "Adjust flag", (void *)4 },
    { "zf", (getter)eflags_get_flag, (setter)eflags_set_flag, "Zero flag", (void *)6 },
    { "sf", (getter)eflags_get_flag, (setter)eflags_set_flag, "Sign flag", (void *)7 },
    { "tf", (getter)eflags_get_flag, (setter)eflags_set_flag, "Trap flag", (void *)8 },
    { "df", (getter)eflags_get_flag, (setter)eflags_set_flag, "Direction flag", (void *)10 },
    { "of", (getter)eflags_get_flag, (setter)eflags_set_flag, "Overflow flag", (void *)11 },
    {NULL}  /* Sentinel */
};

PyTypeObject PyBones_EFlags_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "_bones.EFlags",  /*tp_name*/
    sizeof(PyBones_EFlagsObject),  /*tp_basicsize*/
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
    (reprfunc)eflags_to_str,  /*tp_str*/
    0,  /*tp_getattro*/
    0,  /*tp_setattro*/
    0,  /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,  /*tp_flags*/
    "X86 CPU EFlags",  /*tp_doc*/
    0,  /* tp_traverse */
    0,  /* tp_clear */
    0,  /* tp_richcompare */
    0,  /* tp_weaklistoffset */
    0,  /* tp_iter */
    0,  /* tp_iternext */
    0,  /* tp_methods */
    0,  /* tp_members */
    eflags_getseters,  /* tp_getset */
};


#define REG_LONG32  (1<<31)
#define REG_LONGDBL (1<<30)
#define OFFSET_MASK 0x000FFFFF

typedef struct {
    PyObject_HEAD

    CONTEXT ctx;
    PyBones_EFlagsObject *eflags;
} PyBones_ContextObject;

int
_PyBones_Context_Get(PyObject *self, HANDLE thread)
{
    PyBones_ContextObject *_self = (PyBones_ContextObject *)self;
    NTSTATUS status;

    _self->ctx.ContextFlags = CONTEXT_ALL;
    status = NtGetContextThread(thread, &_self->ctx);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return -1;
    }

    Py_XDECREF(_self->eflags);
    _self->eflags = (PyBones_EFlagsObject *)PyBones_EFlags_Type.tp_alloc(&PyBones_EFlags_Type, 0);
    _self->eflags->All = _self->ctx.EFlags;

    return 0;
}

int
_PyBones_Context_Set(PyObject *self, HANDLE thread)
{
    PyBones_ContextObject *_self = (PyBones_ContextObject *)self;
    NTSTATUS status;

    _self->ctx.EFlags = _self->eflags->All;

    _self->ctx.ContextFlags = CONTEXT_ALL;
    status = NtSetContextThread(thread, &_self->ctx);
    if (!NT_SUCCESS(status)) {
        PyBones_RaiseNtStatusError(status);
        return -1;
    }
    return 0;
}

int
PyBones_Context_Check(PyObject *o)
{
    return Py_TYPE(o) == &PyBones_Context_Type;
}

static void
context_dealloc(PyBones_ContextObject *self)
{
    Py_DECREF(self->eflags);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
context_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyBones_ContextObject *self;

    self = (PyBones_ContextObject *)type->tp_alloc(type, 0);
    if (self) {
        self->eflags = (PyBones_EFlagsObject *)PyBones_EFlags_Type.tp_alloc(&PyBones_EFlags_Type, 0);
        if (!self->eflags) {
            Py_DECREF(self);
            return NULL;
        }
    }

    return (PyObject *)self;
}

static PyObject *
context_str(PyBones_ContextObject *self)
{
    PCONTEXT c = &self->ctx;
    char eflags_str[20];
    char buffer[256];

    eflags_sprintf(self->eflags, eflags_str);
    /* Unfortunately, PyString_FromFormat() isn't as useful. */
    sprintf(buffer,
        "eax=%08x ebx=%08x ecx=%08x edx=%08x esi=%08x edi=%08x\n"
        "eip=%08x esp=%08x ebp=%08x efl=%08x %s\n"
        "cs=%04x  ss=%04x  ds=%04x es=%04x  fs=%04x  gs=%04x",
        c->Eax, c->Ebx, c->Ecx, c->Edx, c->Esi, c->Edi,
        c->Eip, c->Esp, c->Ebp, self->eflags->All, eflags_str,
        c->SegCs, c->SegSs, c->SegDs, c->SegEs, c->SegFs, c->SegGs);
    return PyString_FromString(buffer);
}

static PyObject *
context_get_reg(PyBones_ContextObject *self, int id)
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
context_set_reg(PyBones_ContextObject *self, PyObject *value, int id)
{
    int offset = id & OFFSET_MASK;

    if (!value) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete this attribute.");
        return -1;
    }

    if (id & REG_LONG32) {
        if (PyInt_CheckExact(value)) {
            *(long *)((char *)&self->ctx + offset) = PyInt_AS_LONG(value);
            return 0;
        }
        if (PyLong_CheckExact(value)) {
            *(unsigned long *)((char *)&self->ctx + offset) = PyLong_AsUnsignedLong(value);
            return 0;
        }
        PyErr_SetString(PyExc_TypeError, "Expected an instance of int or long.");
    }
    else if (id & REG_LONGDBL) {
        if (!PyFloat_CheckExact(value)) {
            return 0;
        }
        PyErr_SetString(PyExc_TypeError, "Expected an instance of float.");
    }
    return -1;
}

static PyObject *
context_get_eflags(PyBones_ContextObject *self, void *closure)
{
    Py_INCREF(self->eflags);
    return (PyObject *)self->eflags;
}

static PyGetSetDef context_getseters[] = {
    /* name, get, set, doc, closure */
    { "dr0", (getter)context_get_reg, (setter)context_set_reg, "DR0", (void *)(REG_LONG32 | offsetof(CONTEXT, Dr0)) },
    { "dr1", (getter)context_get_reg, (setter)context_set_reg, "DR1", (void *)(REG_LONG32 | offsetof(CONTEXT, Dr1)) },
    { "dr2", (getter)context_get_reg, (setter)context_set_reg, "DR2", (void *)(REG_LONG32 | offsetof(CONTEXT, Dr2)) },
    { "dr3", (getter)context_get_reg, (setter)context_set_reg, "DR3", (void *)(REG_LONG32 | offsetof(CONTEXT, Dr3)) },
    { "dr6", (getter)context_get_reg, (setter)context_set_reg, "DR6", (void *)(REG_LONG32 | offsetof(CONTEXT, Dr6)) },
    { "dr7", (getter)context_get_reg, (setter)context_set_reg, "DR7", (void *)(REG_LONG32 | offsetof(CONTEXT, Dr7)) },

    { "gs", (getter)context_get_reg, (setter)context_set_reg, "GS", (void *)(REG_LONG32 | offsetof(CONTEXT, SegGs)) },
    { "fs", (getter)context_get_reg, (setter)context_set_reg, "FS", (void *)(REG_LONG32 | offsetof(CONTEXT, SegFs)) },
    { "es", (getter)context_get_reg, (setter)context_set_reg, "ES", (void *)(REG_LONG32 | offsetof(CONTEXT, SegEs)) },
    { "ds", (getter)context_get_reg, (setter)context_set_reg, "DS", (void *)(REG_LONG32 | offsetof(CONTEXT, SegDs)) },
    { "cs", (getter)context_get_reg, (setter)context_set_reg, "CS", (void *)(REG_LONG32 | offsetof(CONTEXT, SegCs)) },
    { "ss", (getter)context_get_reg, (setter)context_set_reg, "SS", (void *)(REG_LONG32 | offsetof(CONTEXT, SegSs)) },

    { "edi", (getter)context_get_reg, (setter)context_set_reg, "EDI", (void *)(REG_LONG32 | offsetof(CONTEXT, Edi)) },
    { "esi", (getter)context_get_reg, (setter)context_set_reg, "ESI", (void *)(REG_LONG32 | offsetof(CONTEXT, Esi)) },
    { "ebx", (getter)context_get_reg, (setter)context_set_reg, "EBX", (void *)(REG_LONG32 | offsetof(CONTEXT, Ebx)) },
    { "ecx", (getter)context_get_reg, (setter)context_set_reg, "ECX", (void *)(REG_LONG32 | offsetof(CONTEXT, Ecx)) },
    { "edx", (getter)context_get_reg, (setter)context_set_reg, "EDX", (void *)(REG_LONG32 | offsetof(CONTEXT, Edx)) },
    { "eax", (getter)context_get_reg, (setter)context_set_reg, "EAX", (void *)(REG_LONG32 | offsetof(CONTEXT, Eax)) },

    { "ebp", (getter)context_get_reg, (setter)context_set_reg, "EBP", (void *)(REG_LONG32 | offsetof(CONTEXT, Ebp)) },
    { "esp", (getter)context_get_reg, (setter)context_set_reg, "ESP", (void *)(REG_LONG32 | offsetof(CONTEXT, Esp)) },
    { "eip", (getter)context_get_reg, (setter)context_set_reg, "EIP", (void *)(REG_LONG32 | offsetof(CONTEXT, Eip)) },
    { "eflags", (getter)context_get_eflags, NULL, "EFlags", NULL },

    {NULL}  /* Sentinel */
};

PyTypeObject PyBones_Context_Type = {
    PyObject_HEAD_INIT(NULL)
    0,  /*ob_size*/
    "_bones.Context",  /*tp_name*/
    sizeof(PyBones_ContextObject),  /*tp_basicsize*/
    0,  /*tp_itemsize*/
    (destructor)context_dealloc,  /*tp_dealloc*/
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
    (reprfunc)context_str,  /*tp_str*/
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
    context_getseters,  /* tp_getset */
    0,  /* tp_base */
    0,  /* tp_dict */
    0,  /* tp_descr_get */
    0,  /* tp_descr_set */
    0,  /* tp_dictoffset */
    0,  /* tp_init */
    0,  /* tp_alloc */
    context_new,  /* tp_new */
};
