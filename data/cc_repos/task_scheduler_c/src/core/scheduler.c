#include "scheduler.h"
#include "../models/task.h"

/* 使用 static 将状态变量私有化，限制在当前编译单元可见 */
static int s_high_prio_count = 0;

int scheduler_get_high_prio_count(void) {
    return s_high_prio_count;
}

void scheduler_evaluate(void* generic_task_ptr) {
    if (!generic_task_ptr) return;
    
    Task* t = (Task*)generic_task_ptr;
    if (t->priority > 5) {
        t->is_active = true;
        s_high_prio_count++;
    }
}