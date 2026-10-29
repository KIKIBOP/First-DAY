#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>
#include <stdio.h>

/* Native messaging bridge: fixed bundled interpreter/script, no shell or page-provided commands. */
int wmain(void) {
    wchar_t root[32768], python[32768], script[32768], command[32768];
    DWORD n = GetModuleFileNameW(NULL, root, 32768);
    if (!n || n >= 32768) return 2;
    wchar_t *last = wcsrchr(root, L'\\');
    if (!last) return 2;
    *last = L'\0';
    if (swprintf(python, 32768, L"%ls\\runtime\\python.exe", root) < 0 ||
        swprintf(script, 32768, L"%ls\\native-host\\main.py", root) < 0 ||
        swprintf(command, 32768, L"\"%ls\" -I \"%ls\"", python, script) < 0) return 2;
    STARTUPINFOW si = {0};
    PROCESS_INFORMATION pi = {0};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    SetHandleInformation(si.hStdInput, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
    SetHandleInformation(si.hStdOutput, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
    SetHandleInformation(si.hStdError, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
    if (!CreateProcessW(python, command, NULL, NULL, TRUE, CREATE_NO_WINDOW,
                        NULL, root, &si, &pi)) {
        fprintf(stderr, "MediaCollector runtime launch failed: %lu\n", GetLastError());
        return 3;
    }
    CloseHandle(pi.hThread);
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    return (int)code;
}
