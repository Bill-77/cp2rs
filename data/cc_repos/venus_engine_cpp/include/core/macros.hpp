#pragma once

#include <memory>
#include <string>
#include <stdexcept>

#define VENUS_API __attribute__((visibility("default")))
#define DECLARE_DYNAMIC_CLASS(ClassName) \
    public: \
        static const char* GetClassName() { return #ClassName; } \
        virtual bool IsKindOf(const char* name) const;