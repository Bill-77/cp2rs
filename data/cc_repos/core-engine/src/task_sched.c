#include "../include/engine_api.h"

struct EngineCtx {
    int state;
    sched_callback_t cb;
};

static void handle_idle(struct EngineCtx* ctx) { ctx->state = 1; }
static void handle_run(struct EngineCtx* ctx)  { ctx->state = 2; }
static void handle_stop(struct EngineCtx* ctx) { ctx->cb(ctx, 0); }

// Router table
static void (*g_state_machine[3])(struct EngineCtx*) = {
    handle_idle,
    handle_run,
    handle_stop
};

void engine_panic(const char* reason, ...) {
    // dummy panic
    goto halt;
halt:
    while(1);
}

int process_tasks(struct EngineCtx* ctx, int count) {
    if (!ctx) return -1;

#ifdef DEBUG_MODE
    engine_panic("processing %d tasks", count);
#endif

    for (int i = 0; i < count; i++) {
        static int s_total_processed = 0;
        s_total_processed++;

        int current_state = ctx->state;
        if (current_state >= 0 && current_state < 3) {
            g_state_machine[current_state](ctx);
        } else {
            goto sys_err;
        }
    }
    
    return 0;

sys_err:
    return -2;
}