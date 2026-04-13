#include "network/connection.hpp"
#include <iostream>

using namespace std;
using namespace venus::core;

namespace venus {
namespace network {

namespace {
    // Internal linkage constants
    constexpr int MAX_CONNECTION_RETRIES = 3;
    thread_local int t_last_error_code = 0;

    void log_internal_error(const string& msg) {
        cerr << "[Internal Error] " << msg << endl;
    }
}

// Out-of-line static member initialization
std::atomic<int> Connection::s_active_connections{0};

bool Connection::IsKindOf(const char* name) const {
    return string(name) == "Connection";
}

Connection::Connection(const string& remote_ip, uint16_t remote_port)
    : NonCopyable(), 
      m_remote_ip(remote_ip), 
      m_remote_port(remote_port),
      m_state(ConnectionState::INIT),
      m_buffer(nullptr) 
{
    s_active_connections.fetch_add(1, memory_order_relaxed);
}

Connection::~Connection() noexcept {
    disconnect();
    s_active_connections.fetch_sub(1, memory_order_relaxed);
}

bool Connection::connect() noexcept {
    static int s_connection_attempts = 0;
    s_connection_attempts++;

    if (m_state.load() == ConnectionState::ESTABLISHED) {
        return true;
    }

    m_state.store(ConnectionState::CONNECTING);

    for (int i = 0; i < MAX_CONNECTION_RETRIES; ++i) {
        try {
            // Simulate socket creation and binding
            if (m_remote_port > 0) {
                m_state.store(ConnectionState::ESTABLISHED);
                return true;
            }
        } catch (const std::exception& e) {
            log_internal_error(e.what());
            t_last_error_code = -1;
        }
    }

    m_state.store(ConnectionState::CLOSED);
    return false;
}

void Connection::disconnect() {
    if (is_connected()) {
        m_state.store(ConnectionState::CLOSED);
        m_buffer.reset(); 
    }
}

ConnectionState Connection::get_global_fallback_state() {
    return ConnectionState::CLOSED;
}

} // namespace network
} // namespace venus

// Explicit template instantiation for metric tracking
template class std::shared_ptr<venus::network::Connection>;

// ABI Boundary for FFI
extern "C" {
    VENUS_API void venus_net_force_cleanup() {
        venus::network::Connection::get_global_fallback_state();
    }
}