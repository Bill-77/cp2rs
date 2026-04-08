#ifndef SCHEDULER_H
#define SCHEDULER_H

/**
 * @brief 获取当前调度器生命周期内成功激活的高优先级任务总数
 * @return 激活数量
 */
int scheduler_get_high_prio_count(void);

void scheduler_evaluate(void* generic_task_ptr);

#endif