// A stand-in for the engine, for testing oz_frequencies.so without the game.
//
// It carries the same eight frequencies and looks them up the same way,
// `table[index & 7]`, and prints what twelve indices map to. Unpatched, index 9
// wraps to table[1] = 89.500; patched with the default grid it is 136.450.
//
// One variant per way a compiler may have built the real lookup:
//   VARIANT_member     a member-shaped function, index is the second argument (esi)
//   VARIANT_free       a free function, index is the first argument (edi)
//   VARIANT_inlined    no function at all: the lookup is inlined into its caller,
//                      which the library must refuse to touch and must say so
//   VARIANT_registers  the member shape, called from assembly with every register a
//                      callee may clobber loaded with a marker: a caller that knows
//                      the lookup is three instructions long may keep its own values
//                      in them, so a replacement has to hand all of them back
//
// The executable has to be named DayZServer: the library patches by that name.

#include <stdio.h>

static const float table[8] = {
    87.8f, 89.5f, 91.3f, 91.9f, 94.6f, 96.6f, 99.7f, 102.5f
};

#if defined(VARIANT_member) || defined(VARIANT_registers)

__attribute__((noinline, noclone))
float frequency_by_index(void* self, int index)
{
    (void)self;
    return table[index & 7];
}
#define LOOKUP(i) frequency_by_index((void*)0, (i))

#elif defined(VARIANT_free)

__attribute__((noinline, noclone))
float frequency_by_index(int index)
{
    return table[index & 7];
}
#define LOOKUP(i) frequency_by_index(i)

#elif defined(VARIANT_inlined)

#define LOOKUP(i) (table[(i) & 7])

#else
#error "define VARIANT_member, VARIANT_free, VARIANT_inlined or VARIANT_registers"
#endif

#if defined(VARIANT_registers)

// void probe(unsigned long gp[9], unsigned long xmm[15], float* result, int index)
//
// gp:  rax rcx rdx rsi rdi r8 r9 r10 r11 as they are after the call
// xmm: the low halves of xmm1..xmm15 after the call
// rsi cannot carry a marker -- it carries the index -- so what is checked there
// is that the index itself comes back, which the unpatched lookup does not do.
__asm__(
    ".text\n"
    ".globl probe\n"
    ".type probe, @function\n"
    "probe:\n"
    "    push %rbx\n"
    "    push %r12\n"
    "    push %r13\n"
    "    mov %rdi, %rbx\n"
    "    mov %rsi, %r12\n"
    "    mov %rdx, %r13\n"
    "    mov %ecx, %esi\n"
    "    mov $0x0101010101010101, %rax\n    movq %rax, %xmm1\n"
    "    mov $0x0202020202020202, %rax\n    movq %rax, %xmm2\n"
    "    mov $0x0303030303030303, %rax\n    movq %rax, %xmm3\n"
    "    mov $0x0404040404040404, %rax\n    movq %rax, %xmm4\n"
    "    mov $0x0505050505050505, %rax\n    movq %rax, %xmm5\n"
    "    mov $0x0606060606060606, %rax\n    movq %rax, %xmm6\n"
    "    mov $0x0707070707070707, %rax\n    movq %rax, %xmm7\n"
    "    mov $0x0808080808080808, %rax\n    movq %rax, %xmm8\n"
    "    mov $0x0909090909090909, %rax\n    movq %rax, %xmm9\n"
    "    mov $0x0A0A0A0A0A0A0A0A, %rax\n    movq %rax, %xmm10\n"
    "    mov $0x0B0B0B0B0B0B0B0B, %rax\n    movq %rax, %xmm11\n"
    "    mov $0x0C0C0C0C0C0C0C0C, %rax\n    movq %rax, %xmm12\n"
    "    mov $0x0D0D0D0D0D0D0D0D, %rax\n    movq %rax, %xmm13\n"
    "    mov $0x0E0E0E0E0E0E0E0E, %rax\n    movq %rax, %xmm14\n"
    "    mov $0x0F0F0F0F0F0F0F0F, %rax\n    movq %rax, %xmm15\n"
    "    mov $0x1111111111111111, %rax\n"
    "    mov $0x2222222222222222, %rcx\n"
    "    mov $0x3333333333333333, %rdx\n"
    "    mov $0x5555555555555555, %rdi\n"
    "    mov $0x6666666666666666, %r8\n"
    "    mov $0x7777777777777777, %r9\n"
    "    mov $0x8888888888888888, %r10\n"
    "    mov $0x9999999999999999, %r11\n"
    "    call frequency_by_index\n"
    "    mov %rax,   0(%rbx)\n"
    "    mov %rcx,   8(%rbx)\n"
    "    mov %rdx,  16(%rbx)\n"
    "    mov %rsi,  24(%rbx)\n"
    "    mov %rdi,  32(%rbx)\n"
    "    mov %r8,   40(%rbx)\n"
    "    mov %r9,   48(%rbx)\n"
    "    mov %r10,  56(%rbx)\n"
    "    mov %r11,  64(%rbx)\n"
    "    movq %xmm1,    0(%r12)\n"
    "    movq %xmm2,    8(%r12)\n"
    "    movq %xmm3,   16(%r12)\n"
    "    movq %xmm4,   24(%r12)\n"
    "    movq %xmm5,   32(%r12)\n"
    "    movq %xmm6,   40(%r12)\n"
    "    movq %xmm7,   48(%r12)\n"
    "    movq %xmm8,   56(%r12)\n"
    "    movq %xmm9,   64(%r12)\n"
    "    movq %xmm10,  72(%r12)\n"
    "    movq %xmm11,  80(%r12)\n"
    "    movq %xmm12,  88(%r12)\n"
    "    movq %xmm13,  96(%r12)\n"
    "    movq %xmm14, 104(%r12)\n"
    "    movq %xmm15, 112(%r12)\n"
    "    movss %xmm0, (%r13)\n"
    "    pop %r13\n"
    "    pop %r12\n"
    "    pop %rbx\n"
    "    ret\n"
    ".size probe, . - probe\n"
);

void probe(unsigned long gp[9], unsigned long xmm[15], float* result, int index);

static int kept_registers(int index, float* result)
{
    static const unsigned long want[9] = {
        0x1111111111111111ul, 0x2222222222222222ul, 0x3333333333333333ul, 0 /* rsi: the index */,
        0x5555555555555555ul, 0x6666666666666666ul, 0x7777777777777777ul,
        0x8888888888888888ul, 0x9999999999999999ul,
    };
    unsigned long gp[9], xmm[15];
    probe(gp, xmm, result, index);

    int kept = 0;
    for (int i = 0; i < 9; i++)
        kept += gp[i] == (i == 3 ? (unsigned long)index : want[i]);
    for (int i = 0; i < 15; i++)
        kept += xmm[i] == 0x0101010101010101ul * (unsigned long)(i + 1);
    return kept;
}

#endif

int main(int argc, char** argv)
{
    (void)argv;
    // `argc - argc` keeps the indices out of the compiler's sight, so nothing
    // here is folded into constants at build time.
    volatile int first = argc - argc;

#if defined(VARIANT_registers)
    float result = 0;
    int kept = kept_registers(first + 9, &result);
    printf("9 %.3f\n", (double)result);
    printf("registers kept: %d of 24\n", kept);
#else
    for (int i = first; i < first + 12; i++)
        printf("%d %.3f\n", i, (double)LOOKUP(i));
#endif
    return 0;
}
