#include "task.h"

void task_init(Task* t, int id, int prio) {
    if (t) {
        t->task_id = id;
        t->priority = prio;
        t->is_active = false;
    }
}