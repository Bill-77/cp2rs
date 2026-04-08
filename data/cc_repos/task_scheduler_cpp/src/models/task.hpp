#ifndef TASK_HPP
#define TASK_HPP

namespace models {
    /**
     * @brief 任务数据模型类
     * 封装任务属性，严格控制状态修改权限
     */
    class Task {
    private:
        int taskId;
        int priority;
        bool active{false};

    public:
        Task(int id, int prio) : taskId(id), priority(prio) {}
        
        int getPriority() const { return priority; }
        void activate() { active = true; }
        bool isActive() const { return active; }
    };
}

#endif