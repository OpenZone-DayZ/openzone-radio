#include "patch.h"

#include <stdio.h>
#include <string.h>

// ------------------------------------------------------------------ the shapes
//
// Every DayZ build up to 1.29 compiled the lookup as one leaf:
//
//   8B C2                 mov   eax, edx            ; edx = tuned index
//   48 8D 0D rel32        lea   rcx, [rip + table]
//   83 E0 07              and   eax, 7              ; the entire eight-channel limit
//   F3 0F 10 04 81        movss xmm0, [rcx + rax*4]
//   C3                    ret
//
// 1.30 (Experimental 1.30.164014, measured 2026-10-11) ships NINE channels --
// 80.0 MHz in front of the old eight -- and reduces the index modulo 9 with a
// magic multiply instead of masking it:
//
//   48 63 CA              movsxd rcx, edx
//   48 B8 imm64           mov    rax, 0xE38E38E38E38E38F   ; 1/9
//   48 F7 E1              mul    rcx
//   48 C1 EA 03           shr    rdx, 3
//   48 8D 04 D2           lea    rax, [rdx + rdx*8]
//   48 2B C8              sub    rcx, rax                  ; index - 9*(index/9)
//   85 C9                 test   ecx, ecx
//   8D 41 09              lea    eax, [rcx + 9]
//   0F 49 C1              cmovns eax, ecx                  ; a negative remainder wraps
//   48 8D 0D rel32        lea    rcx, [rip + table]
//   48 98                 cdqe
//   F3 0F 10 04 81        movss  xmm0, [rcx + rax*4]
//   C3                    ret
//
// The calling convention did not change: the index arrives in edx, the result
// leaves in xmm0, and eight callers reach the leaf through `call`. The ninth
// caller of 1.29 -- the transmitter initialiser, which stores the frequency
// into the object -- has the same arithmetic INLINED on 1.30, reading the index
// from the object:
//
//   48 63 4F 18           movsxd rcx, [rdi + 0x18]
//   ... the same multiply, subtract and wrap, in a slightly different order ...
//   48 98                 cdqe
//   48 8D 0D rel32        lea    rcx, [rip + table]
//   F3 0F 10 04 81        movss  xmm0, [rcx + rax*4]
//                         (then: movss [rdi + 0x1C], xmm0)
//
// Each shape is matched on everything except the rel32 and confirmed by
// following that rel32 and looking at what it points at.

struct Shape
{
    const char*          name;
    const unsigned char* bytes;
    const char*          mask;         // 'x' must match, '?' is wildcarded
    size_t               len;
    size_t               relAt;        // offset of the lea's rel32
    size_t               relEnd;       // offset just past the lea: what the rel32 is relative to
    const float*         vanilla;      // the table that build ships at the lea's target
    int                  vanillaCount;
    bool                 isLeaf;       // a function to redirect at its entry
    const unsigned char* callPrefix;   // inlined copy only: how to load the index into edx
    size_t               callPrefixLen;
};

static const float kVanilla8[8] = {
    87.8f, 89.5f, 91.3f, 91.9f, 94.6f, 96.6f, 99.7f, 102.5f
};
static const float kVanilla9[9] = {
    80.0f, 87.8f, 89.5f, 91.3f, 91.9f, 94.6f, 96.6f, 99.7f, 102.5f
};

static const unsigned char kLeaf129[] = {
    0x8B, 0xC2,
    0x48, 0x8D, 0x0D, 0x00, 0x00, 0x00, 0x00,
    0x83, 0xE0, 0x07,
    0xF3, 0x0F, 0x10, 0x04, 0x81,
    0xC3,
};
static const char kLeaf129Mask[] = "xx" "xxx????" "xxx" "xxxxx" "x";

static const unsigned char kLeaf130[] = {
    0x48, 0x63, 0xCA,
    0x48, 0xB8, 0x8F, 0xE3, 0x38, 0x8E, 0xE3, 0x38, 0x8E, 0xE3,
    0x48, 0xF7, 0xE1,
    0x48, 0xC1, 0xEA, 0x03,
    0x48, 0x8D, 0x04, 0xD2,
    0x48, 0x2B, 0xC8,
    0x85, 0xC9,
    0x8D, 0x41, 0x09,
    0x0F, 0x49, 0xC1,
    0x48, 0x8D, 0x0D, 0x00, 0x00, 0x00, 0x00,
    0x48, 0x98,
    0xF3, 0x0F, 0x10, 0x04, 0x81,
    0xC3,
};
static const char kLeaf130Mask[] =
    "xxx" "xxxxxxxxxx" "xxx" "xxxx" "xxxx" "xxx" "xx" "xxx" "xxx" "xxx????" "xx" "xxxxx" "x";

static const unsigned char kInline130[] = {
    0x48, 0x63, 0x4F, 0x18,
    0x48, 0xB8, 0x8F, 0xE3, 0x38, 0x8E, 0xE3, 0x38, 0x8E, 0xE3,
    0x48, 0xF7, 0xE1,
    0x48, 0xC1, 0xEA, 0x03,
    0x48, 0x8D, 0x04, 0xD2,
    0x48, 0x2B, 0xC8,
    0x8D, 0x41, 0x09,
    0x85, 0xC9,
    0x0F, 0x49, 0xC1,
    0x48, 0x98,
    0x48, 0x8D, 0x0D, 0x00, 0x00, 0x00, 0x00,
    0xF3, 0x0F, 0x10, 0x04, 0x81,
};
static const char kInline130Mask[] =
    "xxxx" "xxxxxxxxxx" "xxx" "xxxx" "xxxx" "xxx" "xxx" "xx" "xxx" "xx" "xxx????" "xxxxx";

// mov edx, dword ptr [rdi + 0x18] -- the index the inlined copy reads.
static const unsigned char kInline130Prefix[] = { 0x8B, 0x57, 0x18 };

static const Shape kShapes[] = {
    { "1.29 leaf",         kLeaf129,   kLeaf129Mask,   sizeof(kLeaf129),   5,  9,  kVanilla8, 8, true,  0, 0 },
    { "1.30 leaf",         kLeaf130,   kLeaf130Mask,   sizeof(kLeaf130),   38, 42, kVanilla9, 9, true,  0, 0 },
    { "1.30 inlined copy", kInline130, kInline130Mask, sizeof(kInline130), 41, 45, kVanilla9, 9, false,
      kInline130Prefix, sizeof(kInline130Prefix) },
};
static const int kShapeCount = static_cast<int>(sizeof(kShapes) / sizeof(kShapes[0]));

const size_t kPatchLen = 12;   // mov rax, imm64 (10) + jmp rax (2)


static bool MatchesShape(const unsigned char* p, const Shape& s)
{
    for (size_t i = 0; i < s.len; ++i)
    {
        if (s.mask[i] == 'x' && p[i] != s.bytes[i])
            return false;
    }
    return true;
}

static unsigned char* TableOf(unsigned char* at, const Shape& s)
{
    int rel = *reinterpret_cast<int*>(at + s.relAt);
    return at + s.relEnd + rel;
}


bool FindFrequencyCode(HMODULE module, PatchTargets* out, char* why, size_t whyLen)
{
    unsigned char* base = reinterpret_cast<unsigned char*>(module);
    IMAGE_DOS_HEADER* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE)
    {
        _snprintf_s(why, whyLen, _TRUNCATE, "module has no DOS header");
        return false;
    }

    IMAGE_NT_HEADERS64* nt = reinterpret_cast<IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE)
    {
        _snprintf_s(why, whyLen, _TRUNCATE, "module has no PE header");
        return false;
    }

    IMAGE_SECTION_HEADER* sec = IMAGE_FIRST_SECTION(nt);
    const int nsec = nt->FileHeader.NumberOfSections;

    // Up to four hits per shape are remembered; more than one is a refusal
    // anyway, the rest only shapes the message.
    unsigned char* hits[kShapeCount][4] = {};
    int hitCount[kShapeCount] = {};
    int scanned = 0;

    for (int i = 0; i < nsec; ++i)
    {
        if (!(sec[i].Characteristics & IMAGE_SCN_MEM_EXECUTE))
            continue;

        ++scanned;
        unsigned char* start = base + sec[i].VirtualAddress;
        // VirtualSize can exceed the mapped raw data on the last section; the
        // engine's .text is fully backed, but stay inside it regardless.
        size_t size = sec[i].Misc.VirtualSize;

        for (size_t off = 0; off < size; ++off)
        {
            for (int k = 0; k < kShapeCount; ++k)
            {
                const Shape& s = kShapes[k];
                if (off + s.len > size || !MatchesShape(start + off, s))
                    continue;
                if (hitCount[k] < 4)
                    hits[k][hitCount[k]] = start + off;
                ++hitCount[k];
            }
        }
    }

    if (scanned == 0)
    {
        _snprintf_s(why, whyLen, _TRUNCATE, "no executable section to scan");
        return false;
    }

    // Exactly one leaf shape, exactly once.
    int leafShape = -1;
    int leafShapes = 0;
    for (int k = 0; k < kShapeCount; ++k)
    {
        if (!kShapes[k].isLeaf || hitCount[k] == 0)
            continue;
        ++leafShapes;
        leafShape = k;
    }
    if (leafShapes == 0)
    {
        _snprintf_s(why, whyLen, _TRUNCATE,
                    "the frequency lookup's code shape is not present in %d executable "
                    "section(s) (%d known shapes tried) -- the game changed how it "
                    "compiles, nothing was patched",
                    scanned, kShapeCount);
        return false;
    }
    if (leafShapes > 1)
    {
        _snprintf_s(why, whyLen, _TRUNCATE,
                    "%d different lookup shapes are present at once; refusing to guess "
                    "which is the live one", leafShapes);
        return false;
    }
    const Shape& leaf = kShapes[leafShape];
    if (hitCount[leafShape] > 1)
    {
        // Ambiguity is a refusal, not a coin flip: patching the wrong one of two
        // identical-looking leaves would be silent and very hard to trace.
        _snprintf_s(why, whyLen, _TRUNCATE,
                    "the code shape (%s) matched %d times; refusing to guess which is the "
                    "frequency lookup", leaf.name, hitCount[leafShape]);
        return false;
    }

    unsigned char* func = hits[leafShape][0];
    unsigned char* table = TableOf(func, leaf);

    // Confirm the target is inside the image, so a wild displacement cannot make
    // us report success about a random address.
    unsigned char* imageEnd = base + nt->OptionalHeader.SizeOfImage;
    const size_t tableBytes = static_cast<size_t>(leaf.vanillaCount) * sizeof(float);
    if (table < base || table + tableBytes > imageEnd)
    {
        _snprintf_s(why, whyLen, _TRUNCATE,
                    "the lookup's table pointer lands outside the module image");
        return false;
    }

    bool vanilla = (memcmp(table, leaf.vanilla, tableBytes) == 0);

    out->shape = leaf.name;
    out->func = func;
    out->funcLen = leaf.len;
    out->table = table;
    out->tableCount = leaf.vanillaCount;
    out->tableIsVanilla = vanilla;
    out->inlineAt = 0;
    out->inlineLen = 0;

    // An inlined copy is taken only when it is unique and reads the SAME table;
    // anything else is reported and left alone, because the leaf alone already
    // covers every tuning and a wrong mid-function patch would be fatal.
    char inlineNote[160] = "";
    for (int k = 0; k < kShapeCount; ++k)
    {
        if (kShapes[k].isLeaf || hitCount[k] == 0)
            continue;
        const Shape& s = kShapes[k];
        if (hitCount[k] > 1)
        {
            _snprintf_s(inlineNote, sizeof(inlineNote), _TRUNCATE,
                        "; %s matched %d times, left alone", s.name, hitCount[k]);
            continue;
        }
        unsigned char* copy = hits[k][0];
        if (TableOf(copy, s) != table)
        {
            _snprintf_s(inlineNote, sizeof(inlineNote), _TRUNCATE,
                        "; %s at +0x%llX reads another table, left alone", s.name,
                        static_cast<unsigned long long>(copy - base));
            continue;
        }
        out->inlineAt = copy;
        out->inlineLen = s.len;
        _snprintf_s(inlineNote, sizeof(inlineNote), _TRUNCATE,
                    "; %s at +0x%llX reads the same table", s.name,
                    static_cast<unsigned long long>(copy - base));
    }

    static const char* kNumbers[] = { "eight", "nine" };
    const char* number = (leaf.vanillaCount == 8) ? kNumbers[0] : kNumbers[1];
    _snprintf_s(why, whyLen, _TRUNCATE,
                "lookup at +0x%llX (%s, %zu bytes), table at +0x%llX, table is %sthe known "
                "vanilla %s%s",
                static_cast<unsigned long long>(func - base), leaf.name, leaf.len,
                static_cast<unsigned long long>(table - base),
                vanilla ? "" : "NOT ", number, inlineNote);
    return true;
}


static bool WriteCode(unsigned char* at, const unsigned char* bytes, size_t len,
                      char* why, size_t whyLen)
{
    DWORD old = 0;
    if (!VirtualProtect(at, len, PAGE_EXECUTE_READWRITE, &old))
    {
        _snprintf_s(why, whyLen, _TRUNCATE,
                    "VirtualProtect failed with %lu", GetLastError());
        return false;
    }

    memcpy(at, bytes, len);

    DWORD ignored = 0;
    VirtualProtect(at, len, old, &ignored);
    FlushInstructionCache(GetCurrentProcess(), at, len);
    return true;
}


bool RedirectFunction(unsigned char* func, void* replacement, char* why, size_t whyLen)
{
    // mov rax, imm64 ; jmp rax  -- 12 bytes into the 18 (or 50) the original occupies.
    unsigned char stub[kPatchLen];
    stub[0] = 0x48;
    stub[1] = 0xB8;
    memcpy(stub + 2, &replacement, sizeof(void*));
    stub[10] = 0xFF;
    stub[11] = 0xE0;

    if (!WriteCode(func, stub, kPatchLen, why, whyLen))
        return false;

    _snprintf_s(why, whyLen, _TRUNCATE, "redirected %zu bytes", kPatchLen);
    return true;
}


bool PatchInlinedLookup(const PatchTargets* targets, void* replacement, char* why, size_t whyLen)
{
    if (!targets->inlineAt)
    {
        _snprintf_s(why, whyLen, _TRUNCATE, "no inlined copy to patch");
        return false;
    }

    const Shape* shape = 0;
    for (int k = 0; k < kShapeCount; ++k)
    {
        if (!kShapes[k].isLeaf && kShapes[k].len == targets->inlineLen)
            shape = &kShapes[k];
    }
    if (!shape || !shape->callPrefix)
    {
        _snprintf_s(why, whyLen, _TRUNCATE, "the inlined copy's shape carries no call prefix");
        return false;
    }

    // <load edx from the object> ; mov rax, imm64 ; call rax ; nop ...
    //
    // The original block clobbers rax, rcx and rdx itself and sits right after
    // a call the function already makes, so every volatile register is dead,
    // the stack is aligned for a call and the shadow space is the caller's own.
    // What the block left in xmm0 -- the frequency -- is exactly what the call
    // returns, and the instruction after the block stores xmm0 unchanged.
    unsigned char stub[64];
    size_t n = 0;
    memcpy(stub + n, shape->callPrefix, shape->callPrefixLen);
    n += shape->callPrefixLen;
    stub[n++] = 0x48;
    stub[n++] = 0xB8;
    memcpy(stub + n, &replacement, sizeof(void*));
    n += sizeof(void*);
    stub[n++] = 0xFF;
    stub[n++] = 0xD0;
    if (n > targets->inlineLen || targets->inlineLen > sizeof(stub))
    {
        _snprintf_s(why, whyLen, _TRUNCATE, "the inlined copy is too short for the call stub");
        return false;
    }
    while (n < targets->inlineLen)
        stub[n++] = 0x90;

    if (!WriteCode(targets->inlineAt, stub, targets->inlineLen, why, whyLen))
        return false;

    _snprintf_s(why, whyLen, _TRUNCATE, "inlined copy: replaced %zu bytes with a call",
                targets->inlineLen);
    return true;
}
