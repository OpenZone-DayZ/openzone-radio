// Finding and redirecting the engine's frequency lookup.
//
// Nothing here is an address. The one function that turns a tuned index into a
// frequency is located by its own machine code every time the server starts, so
// a game update moves it without breaking anything -- and if the shape it looks
// for is gone, it says so instead of patching whatever happens to be there.
//
// This branch is 1.30's: a 50-byte leaf reducing the index modulo 9 over a
// nine-entry table, plus a copy of it inlined into the transmitter initialiser.
// The 18-byte leaf of 1.29 and earlier lives on the main branch. Each known
// shape is described once, in patch.cpp; this header only names what was found.

#pragma once

#include <windows.h>
#include <stddef.h>

struct PatchTargets
{
    const char*    shape;            // which known shape the leaf matched
    unsigned char* func;             // entry of the leaf that reads the table
    size_t         funcLen;          // bytes the leaf occupies
    unsigned char* table;            // the floats it reads, in .data
    int            tableCount;       // how many the game ships there: 8 on 1.29, 9 on 1.30
    bool           tableIsVanilla;   // do those floats match what that build ships
    unsigned char* inlineAt;         // an inlined copy of the lookup that reads the same table, or null
    size_t         inlineLen;        // bytes that copy occupies
};

// Locate the lookup in `module`. On failure, `why` says what was and was not
// found -- the difference between "no such code" and "found it twice" matters
// when deciding whether a game update broke this.
bool FindFrequencyCode(HMODULE module, PatchTargets* out, char* why, size_t whyLen);

// Overwrite the located function with an absolute jump to `replacement`.
// Absolute rather than relative: our DLL can land further than 2 GB from the
// executable, which a rel32 cannot reach.
bool RedirectFunction(unsigned char* func, void* replacement, char* why, size_t whyLen);

// Replace the inlined copy (when the build has one) with a call to
// `replacement`, so the transmitter initialiser reads the same grid as every
// later tuning. Only valid when `out->inlineAt` is set.
bool PatchInlinedLookup(const PatchTargets* targets, void* replacement, char* why, size_t whyLen);
