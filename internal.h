#ifndef __INTERNAL_INCLUDED
#define __INTERNAL_INCLUDED

/* http://legacy.python.org/dev/peps/pep-0007/ */

#include "bones.h"

#if 1
#define DEBUG_PRINT PySys_WriteStderr
#else
#define DEBUG_PRINT
#endif

int
_PyBones_Process_AddThread(PyObject *self, PyObject *thread_id, PyObject *thread);

int
_PyBones_Process_AddModule(PyObject *self, PyObject *base_address, PyObject *module);

PyObject *
_PyBones_Process_DelThread(PyObject *self, PyObject *thread_id);

PyObject *
_PyBones_Process_DelModule(PyObject *self, PyObject *base_address);

void
_PyBones_Process_SetExitStatus(PyObject *self, unsigned int status);

void *
_PyBones_Process_GetPebAddress(PyObject *self);

int
PyBones_Process_ReadMemoryPtr(PyObject *self, void *address, unsigned size, void *buffer);

PyObject *
PyBones_Process_GetSectionFileNamePtr(PyObject *self, void *address);


void *
_PyBones_Thread_GetTebAddress(PyObject *self);

void
_PyBones_Thread_SetExitStatus(PyObject *self, unsigned int status);


#endif // __INTERNAL_INCLUDED
