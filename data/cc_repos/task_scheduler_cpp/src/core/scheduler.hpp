#ifndef SCHEDULER_HPP
#define SCHEDULER_HPP

namespace core {

    /**
     * @brief 泛型任务调度引擎
     * 基于模板支持不同类型的 Task 评估
     */
    template <typename T>
    class Scheduler {
    private:
        int highPrioCount{0}; // 私有状态计数器

    public:
        int getHighPrioCount() const { return highPrioCount; }

        void evaluate(T& item);
    };

    template <typename T>
    void Scheduler<T>::evaluate(T& item) {
        if (item.getPriority() > 5) {
            item.activate();
            highPrioCount++;
        }
    }
}

#endif