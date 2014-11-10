#ifndef __BONES_INCLUDED
#define __BONES_INCLUDED

extern PyObject *PyBones_NtStatusError;
extern PyObject *PyBones_Win32Error;

extern void
_PyBones_RaiseNtStatusError(const char *file, int line, unsigned int status);

#define PyBones_RaiseNtStatusError(s) \
    _PyBones_RaiseNtStatusError(__FILE__, __LINE__, (s))

extern PyTypeObject PyBones_Debugger_Type;
extern PyTypeObject PyBones_Thread_Type;
extern PyTypeObject PyBones_Process_Type;
extern PyTypeObject PyBones_EFlags_Type;
extern PyTypeObject PyBones_Context_Type;
extern PyTypeObject PyBones_Module_Type;

extern PyTypeObject PyBones_ExceptionInfo_Type;
extern PyTypeObject PyBones_AccessViolationInfo_Type;

#endif // __BONES_INCLUDED
