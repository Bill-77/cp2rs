/// 任务数据结构
/// `is_active` 字段仅对当前 crate 内的模块可见，防止外部乱改
pub struct Task {
    pub task_id: i32,
    pub priority: i32,
    pub(crate) is_active: bool,
}

impl Task {
    /// 实例化新任务
    pub fn new(id: i32, prio: i32) -> Self {
        Self {
            task_id: id,
            priority: prio,
            is_active: false,
        }
    }
}