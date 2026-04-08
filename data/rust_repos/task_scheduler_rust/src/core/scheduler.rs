/// 定义可被调度器评估的行为契约
pub trait Schedulable {
    fn get_prio(&self) -> i32;
    fn activate(&mut self);
}

// 为具体的数据模型实现契约
impl Schedulable for crate::models::task::Task {
    fn get_prio(&self) -> i32 { self.priority }
    fn activate(&mut self) { self.is_active = true; }
}

/// 泛型调度器，要求 T 必须实现 Schedulable 契约
pub struct Scheduler<T> {
    high_prio_count: i32,
    _marker: std::marker::PhantomData<T>,
}

impl<T: Schedulable> Scheduler<T> {
    pub fn new() -> Self {
        Self { high_prio_count: 0, _marker: std::marker::PhantomData }
    }

    pub fn get_high_prio_count(&self) -> i32 {
        self.high_prio_count
    }

    pub fn evaluate(&mut self, item: &mut T) {
        if item.get_prio() > 5 {
            item.activate();
            self.high_prio_count += 1;
        }
    }
}