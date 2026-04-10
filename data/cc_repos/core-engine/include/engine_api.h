#ifndef ENGINE_API_H
#define ENGINE_API_H

#include "data_types.h"

extern HwContext g_hw_ctx;

WEAK_SYM int engine_init(void* config);
void engine_panic(const char* reason, ...);

#endif