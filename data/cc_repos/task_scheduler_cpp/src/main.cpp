#include <iostream>
#include "models/task.hpp"
#include "core/scheduler.hpp"

int main() {
    models::Task t1(101, 3);
    models::Task t2(102, 8);

    core::Scheduler<models::Task> sched;
    sched.evaluate(t1);
    sched.evaluate(t2);

    std::cout << "High Priority Tasks: " << sched.getHighPrioCount() << "\n";
    return 0;
}