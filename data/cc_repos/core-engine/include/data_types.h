#include "os_compiler.h"
#include <stdint.h>

struct EngineCtx;

/* Legacy hw context, needs refactoring */
typedef struct {
    uint32_t is_active : 1;
    uint32_t error_code : 7;
    uint32_t reserved : 24;
    
    union {
        uint64_t raw_addr;
        void* ptr_addr;
    } ALIGN_8 mmu_mapping;
} __attribute__((packed)) HwContext;

typedef void (*sched_callback_t)(struct EngineCtx* ctx, int status);