use std::sync::atomic::{AtomicBool, AtomicUsize};

/// Tracks the number of currently active filter rules across all threads.
pub static ACTIVE_FILTERS: AtomicUsize = AtomicUsize::new(0);

pub(crate) static AUDIT_ENABLED: AtomicBool = AtomicBool::new(true);

/// The absolute maximum size of a packet payload before it is dropped.
pub const MAX_PAYLOAD_SIZE: usize = 1024 * 1024;

/// Standard result type for the Shield framework.
pub type Result<T> = std::result::Result<T, crate::core::error::ShieldError>;

/// Represents the execution context for a single network request.
#[derive(Debug)]
pub struct RequestContext<'a, T: Send + Sync> {
    pub ip_addr: String,
    pub payload: &'a mut [u8],
    pub metadata: T,
}