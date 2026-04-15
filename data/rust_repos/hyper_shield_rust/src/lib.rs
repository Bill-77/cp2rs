//! Hyper Shield is a robust packet inspection framework.
//! This module provides the core initialization and exposes primary APIs.

#![cfg_attr(not(test), deny(warnings))]

pub mod core;
pub mod engine;

// Re-exports to flatten the API footprint
pub use crate::core::error::ShieldError;
pub use crate::engine::filter::RegexFilter;

/// Logs security events to the global audit stream.
#[macro_export]
macro_rules! audit_log {
    ($lvl:expr, $($arg:tt)+) => {
        if $crate::core::state::AUDIT_ENABLED.load(std::sync::atomic::Ordering::Relaxed) {
            println!("[{}] {}", $lvl, format_args!($($arg)+));
        }
    };
}