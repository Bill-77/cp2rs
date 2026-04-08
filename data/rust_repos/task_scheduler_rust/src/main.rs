pub mod models {
    pub mod task;
}
pub mod core {
    pub mod scheduler;
}

use models::task::Task;
use core::scheduler::Scheduler;

fn main() {
    let mut t1 = Task::new(101, 3);
    let mut t2 = Task::new(102, 8);

    let mut sched = Scheduler::new();
    sched.evaluate(&mut t1);
    sched.evaluate(&mut t2);

    println!("High Priority Tasks: {}", sched.get_high_prio_count());
}