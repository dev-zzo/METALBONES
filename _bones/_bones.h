#ifndef __BONES_INCLUDED
#define __BONES_INCLUDED

extern PyObject *PyBones_NtStatusError;
extern PyObject *PyBones_Win32Error;

extern void
_PyBones_RaiseNtStatusError(const char *file, int line, unsigned int status);
extern void
_PyBones_RaiseWin32Error(const char *file, int line, unsigned int code);

#define PyBones_RaiseNtStatusError(s) \
    _PyBones_RaiseNtStatusError(__FILE__, __LINE__, (s))
#define PyBones_RaiseWin32Error(c) \
    _PyBones_RaiseWin32Error(__FILE__, __LINE__, (c))

extern PyTypeObject PyBones_Debugger_Type;
extern PyTypeObject PyBones_Thread_Type;
extern PyTypeObject PyBones_Process_Type;
extern PyTypeObject PyBones_EFlags_Type;
extern PyTypeObject PyBones_Context_Type;
extern PyTypeObject PyBones_Module_Type;

#endif // __BONES_INCLUDED
