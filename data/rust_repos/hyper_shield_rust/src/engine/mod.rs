pub mod filter;

/// Contract for all packet inspection implementations.
pub trait PacketInspector {
    /// The specific context type required by this inspector.
    type Context;
    
    /// Whether this filter drops invalid packets automatically.
    const STRICT_MODE: bool;

    /// Evaluates the context and mutates it if necessary.
    fn inspect(&mut self, ctx: &mut Self::Context) -> crate::core::state::Result<()>;

    /// Checks if the inspector's internal ruleset is currently loaded.
    fn is_healthy(&self) -> bool {
        true
    }
}