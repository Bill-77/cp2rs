#include <stdio.h>
#include "models/task.h"
#include "core/scheduler.h"

int main() {
    Task t1, t2;
    task_init(&t1, 101, 3);
    task_init(&t2, 102, 8);

    scheduler_evaluate(&t1);
    scheduler_evaluate(&t2);

    printf("High Priority Tasks: %d\n", scheduler_get_high_prio_count());
    return 0;
}