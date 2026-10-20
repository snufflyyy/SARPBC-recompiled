/*
 * Game-specific hooks the runner (main.cpp) answers to.
 *
 * Per-title behaviour lives in src/overrides/, keyed by guest address or NID;
 * see docs/ps3recomp-primer.md for the override mechanisms.
 */

extern "C" void ps3_load_prx_modules(void)
{
    /* Called once by main.cpp, after the lifted function table is registered and
     * before the game runs. A title that lifts a system PRX loads it here. This
     * one does not: the HLE library answers those modules. */
}
