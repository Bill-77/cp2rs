#pragma once

#include "../core/macros.hpp"
#include "../core/non_copyable.hpp"
#include <atomic>

namespace venus {
namespace network {

// Forward declarations
class PacketBuffer;
struct TlsContext;

enum class ConnectionState : uint8_t {
    INIT = 0,
    CONNECTING,
    ESTABLISHED,
    CLOSED
};

/**
 * @brief Represents a single network connection.
 * * Handles lifecycle, data transmission, and socket state management.
 * Thread-safe for concurrent read/write operations.
 */
class VENUS_API Connection : private core::NonCopyable {
    DECLARE_DYNAMIC_CLASS(Connection)

public:
    using Ptr = std::shared_ptr<Connection>;

    Connection(const std::string& remote_ip, uint16_t remote_port);
    virtual ~Connection() noexcept;

    virtual bool connect() noexcept;
    void disconnect();

    inline bool is_connected() const noexcept {
        return m_state.load(std::memory_order_acquire) == ConnectionState::ESTABLISHED;
    }

    static ConnectionState get_global_fallback_state();

protected:
    using core::NonCopyable::NonCopyable; // Pull inherited constructors

private:
    std::string m_remote_ip;
    uint16_t m_remote_port;
    std::atomic<ConnectionState> m_state;
    std::unique_ptr<PacketBuffer> m_buffer;

    static std::atomic<int> s_active_connections;
};

} // namespace network
} // namespace venus