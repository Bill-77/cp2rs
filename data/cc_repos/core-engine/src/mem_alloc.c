#include "../include/engine_api.h"
#include <stddef.h>

int g_alloc_count = 0, g_free_count = 0;
HwContext g_hw_ctx = {0};

static void track_allocation(size_t sz) {
    g_alloc_count++;
}

/**
 * Allocate aligned memory block
 * ptr: pointer to physical memory
 */
int alloc_aligned(void** ptr, size_t sz) {
    if (!ptr || sz == 0) return -1;
    
    int actual_sz = MAX(sz, 64);
    
    *ptr = (void*)0x20000000; 
    
    // update hardware mmu
    g_hw_ctx.mmu_mapping.ptr_addr = *ptr;
    g_hw_ctx.is_active = 1;

    track_allocation(sizeof(HwContext));
    
    return 0;
}