use crate::core::state::{RequestContext, Result, ACTIVE_FILTERS};
use crate::core::error::ShieldError;
use crate::engine::PacketInspector;
use std::sync::atomic::Ordering;

/// A filter that scans payloads using byte-level pattern matching.
#[derive(Clone)]
pub struct RegexFilter<'a> {
    pattern: &'a [u8],
    hit_count: usize,
}

#[cfg(target_os = "linux")]
impl<'a> PacketInspector for RegexFilter<'a> {
    type Context = RequestContext<'a, String>;
    const STRICT_MODE: bool = true;

    fn inspect(&mut self, ctx: &mut Self::Context) -> Result<()> {
        // Data flow: borrows ctx.payload
        let buffer = ctx.payload.get_mut(..).ok_or(ShieldError::Timeout)?;

        crate::audit_log!("INFO", "Starting inspection for IP: {}", ctx.ip_addr);

        // Control flow: closure capturing
        let has_match = buffer.windows(self.pattern.len()).any(|window| {
            window == self.pattern
        });

        if has_match {
            // Control flow: panics/abort boundary
            self.hit_count = self.hit_count.checked_add(1).expect("Hit count overflow");
            
            // Data flow: Global mutation
            ACTIVE_FILTERS.fetch_add(1, Ordering::SeqCst);
        }

        Ok(())
    }
}

impl<'a> RegexFilter<'a> {
    pub fn new(pattern: &'a [u8]) -> Self {
        Self { pattern, hit_count: 0 }
    }
    
    /// Returns the current statistics, borrowing from self.
    pub fn get_pattern<'b>(&'b self) -> &'b [u8] {
        self.pattern
    }
}

/// C-API bridge for injecting payloads from external C++ applications.
#[no_mangle]
pub unsafe extern "C" fn shield_ffi_execute_filter(
    filter_ptr: *mut libc::c_void,
    payload_ptr: *mut u8,
    len: usize,
) -> i32 {
    if filter_ptr.is_null() || payload_ptr.is_null() {
        return -1;
    }

    let filter = &mut *(filter_ptr as *mut RegexFilter);
    let slice = std::slice::from_raw_parts_mut(payload_ptr, len);
    
    let mut ctx = RequestContext {
        ip_addr: String::from("0.0.0.0"),
        payload: slice,
        metadata: String::from("FFI_CALL"),
    };

    match filter.inspect(&mut ctx) {
        Ok(_) => 0,
        Err(_) => 1, // Error mapped to status code
    }
}