/*
 * config.toml [input] -> environment, for the input settings.
 *
 * The keyboard bindings (src/overrides/input_kbm.cpp, from Drakengard 3's
 * port) and the pad library's switches (PAD_TRACE, PAD_NO_HOST, ... in
 * ps3recomp/libs/input/cellPad.c) are read from environment variables. This
 * puts the [input] section of config.toml in front of them: every key there
 * written in UPPER CASE becomes the environment variable of that name, unless
 * the environment already has it (so `KEY_R2=F tools/run.sh` still wins over
 * the file). Lower-case keys in [input] (elf_path, sfo_path) belong to the
 * lifter and are left alone.
 *
 * Only KEY_*, PAD_*, SARPBC_KBM_LOG and SARPBC_KEYBOARD are accepted; other
 * upper-case keys are reported and ignored (they could be PATH or LD_PRELOAD).
 *
 * Values: a "quoted string", or a bare word/number/true/false (true -> 1,
 * false -> 0). One key = value per line, # comments. That is all of TOML this
 * section uses.
 *
 * The file is the first of: $SARPBC_CONFIG; config.toml beside the
 * executable or one folder up (build/sarpbc -> the checkout's config.toml);
 * config.toml in the current folder. None found: built-in defaults.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
static void set_env(const char* k, const char* v)
{
    if (!getenv(k)) _putenv_s(k, v);
}
#else
#include <unistd.h>
static void set_env(const char* k, const char* v) { setenv(k, v, 0); }
#endif

namespace {

std::string exe_dir()
{
    char buf[4096];
#ifdef _WIN32
    DWORD n = GetModuleFileNameA(NULL, buf, sizeof buf);
    if (!n || n >= sizeof buf) return "";
#else
    ssize_t n = readlink("/proc/self/exe", buf, sizeof buf - 1);
    if (n <= 0) return "";
#endif
    buf[n] = 0;
    std::string s(buf);
    size_t cut = s.find_last_of("/\\");
    return cut == std::string::npos ? "" : s.substr(0, cut);
}

FILE* open_config(std::string& path)
{
    std::string cands[4];
    int n = 0;
    if (const char* e = getenv("SARPBC_CONFIG")) cands[n++] = e;
    const std::string d = exe_dir();
    if (!d.empty()) {
        cands[n++] = d + "/config.toml";
        cands[n++] = d + "/../config.toml";
    }
    cands[n++] = "config.toml";
    for (int i = 0; i < n; i++)
        if (FILE* f = fopen(cands[i].c_str(), "r")) {
            path = cands[i];
            return f;
        }
    return nullptr;
}

std::string trim(const std::string& s)
{
    size_t a = s.find_first_not_of(" \t\r\n"), b = s.find_last_not_of(" \t\r\n");
    return a == std::string::npos ? "" : s.substr(a, b - a + 1);
}

bool upper_key(const std::string& k)
{
    if (k.empty()) return false;
    for (char c : k)
        if (!((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_')) return false;
    return true;
}

/* The only variables this section may set: keyboard bindings (KEY_*), the pad
 * library's switches (PAD_*) and the two keyboard-driver switches. Anything else
 * in upper case, such as PATH or LD_PRELOAD, would otherwise be exported from a
 * config file to the whole process. */
bool supported_key(const std::string& k)
{
    return k.rfind("KEY_", 0) == 0 || k.rfind("PAD_", 0) == 0 ||
           k == "SARPBC_KBM_LOG" || k == "SARPBC_KEYBOARD";
}

}  // namespace

/* Once, before the first reader. Any thread; the readers call it first. */
extern "C" void sarpbc_input_config(void)
{
    static bool done = false;
    if (done) return;
    done = true;

    std::string path;
    FILE* f = open_config(path);
    if (!f) {
        printf("[input] no config.toml found: built-in controls\n");
        return;
    }
    char line[1024];
    bool in_input = false;
    int count = 0;
    while (fgets(line, sizeof line, f)) {
        std::string s = trim(line);
        if (s.empty() || s[0] == '#') continue;
        if (s[0] == '[') {
            in_input = s == "[input]";
            continue;
        }
        if (!in_input) continue;
        size_t eq = s.find('=');
        if (eq == std::string::npos) continue;
        std::string key = trim(s.substr(0, eq)), val = trim(s.substr(eq + 1));
        if (!upper_key(key)) continue;
        if (!supported_key(key)) {
            fprintf(stderr, "[input] %s: ignoring unsupported key %s (want KEY_*, PAD_*, SARPBC_KBM_LOG, SARPBC_KEYBOARD)\n",
                    path.c_str(), key.c_str());
            continue;
        }
        if (!val.empty() && val[0] == '"') {
            size_t close = val.find('"', 1);
            val = close == std::string::npos ? val.substr(1) : val.substr(1, close - 1);
        } else {
            size_t hash = val.find('#');
            if (hash != std::string::npos) val = trim(val.substr(0, hash));
            if (val == "true") val = "1";
            if (val == "false") val = "0";
        }
        set_env(key.c_str(), val.c_str());
        count++;
    }
    fclose(f);
    printf("[input] %s: %d control setting(s)\n", path.c_str(), count);
}
