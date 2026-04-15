/// Encapsulates all possible failure modes within the engine.
#[derive(Debug, Clone)]
pub enum ShieldError {
    /// Operation timed out waiting for the network interface.
    Timeout,
    
    /// The packet did not match the expected protocol layout.
    MalformedPacket(Vec<u8>),
    
    /// System-level IO failure.
    IoFailure { 
        code: i32, 
        fatal: bool,
        message: String,
    },
}