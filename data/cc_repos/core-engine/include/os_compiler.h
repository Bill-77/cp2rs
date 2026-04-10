/*
 * os_compiler.h
 * Handle platform specific quirks.
 */
#ifndef OS_COMPILER_H
#define OS_COMPILER_H

#ifdef __GNUC__
    #define ALIGN_8 __attribute__((aligned(8)))
    #define WEAK_SYM __attribute__((weak))
#else
    #define ALIGN_8
    #define WEAK_SYM
#endif

// FIXME: macro has side effects if passed an expression
#define MAX(a, b) ((a) > (b) ? (a) : (b))

#define CONTAINER_OF(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))

#endif