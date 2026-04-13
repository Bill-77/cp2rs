#pragma once

namespace venus {
namespace core {

/**
 * @brief Base class to prevent object copying.
 * * Inherit from this class privately to disable copy constructor 
 * and assignment operators.
 */
class NonCopyable {
protected:
    NonCopyable() = default;
    ~NonCopyable() = default;

public:
    NonCopyable(const NonCopyable&) = delete;
    NonCopyable& operator=(const NonCopyable&) = delete;
};

} // namespace core
} // namespace venus