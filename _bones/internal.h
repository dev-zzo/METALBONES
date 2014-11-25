#ifndef __INTERNAL_INCLUDED
#define __INTERNAL_INCLUDED

/* http://legacy.python.org/dev/peps/pep-0007/ */

#include "_bones.h"

#if 1
#define DEBUG_PRINT PySys_WriteStderr
#else
#define DEBUG_PRINT
#endif


void *
_PyBones_Process_GetPebAddress(PyObject *self);

int
PyBones_Process_ReadMemoryPtr(PyObject *self, void *address, unsigned size, void* dest);

PyObject *
PyBones_Process_GetSectionFileNamePtr(PyObject *self, void *address);


void *
_PyBones_Thread_GetTebAddress(PyObject *self);


PyObject *
_PyBones_ExceptionInfo_Translate(void *record);

#endif // __INTERNAL_INCLUDED
