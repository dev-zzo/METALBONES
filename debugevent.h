#ifndef __DEBUGEVENT_INCLUDED
#define __DEBUGEVENT_INCLUDED

/* Debug event object, base for more specific ones */
typedef struct {
    PyObject_HEAD

    /* Type-specific fields go here. */
    UINT process_id;
    UINT thread_id;

} DebugEvent;


#endif // __DEBUGEVENT_INCLUDED
