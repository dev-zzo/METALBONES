#include <Windows.h>
#include <tchar.h>

/* NULL pointer dereference: write. */
int tc_00001(void)
{
    char *p = NULL;
    *p = 0xDEADC0DE;
    return 0;
}

/* NULL pointer dereference: read. */
int tc_00002(void)
{
    char *p = NULL;
    return *p;
}

/* Stack smash with 0x41 */
int tc_00003(void)
{
    char buf[4];
    memset(buf, 0x41, 32);
    return buf[0];
}

int CALLBACK WinMain(
    HINSTANCE hInstance,
    HINSTANCE hPrevInstance,
    LPSTR lpCmdLine,
    int nCmdShow)
{
    int tc_number;

    tc_number = _ttoi(lpCmdLine);
    switch (tc_number) {
    case 1: return tc_00001();
    case 2: return tc_00002();
    case 3: return tc_00003();
    default:
        return 1;
    }
}
