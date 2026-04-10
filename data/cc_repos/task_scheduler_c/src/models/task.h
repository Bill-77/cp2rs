#ifndef TASK_H
#define TASK_H

#include <stdbool.h>

/**
 * @brief 基础任务节点实体
 * 包含在分布式网络中流转所需的元数据
 */
typedef struct {
    int task_id;
    int priority;
    bool is_active;
} Task;

/**
 * @brief 初始化任务节点
 */
void task_init(Task* t, int id, int prio);

#endif