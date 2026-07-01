import hashlib


def is_real_function_definition(func: dict) -> bool:
    """Return true for executable function definitions, not declarations."""
    if "has_body" in func:
        return func.get("has_body") is True
    return bool(func.get("body"))


def _signature_digest(func: dict) -> str:
    signature = str(func.get("signature") or func.get("body") or func.get("name") or "")
    return hashlib.sha1(signature.encode("utf-8", errors="ignore")).hexdigest()[:8]


def strip_overload_suffix(name: str) -> str:
    """Return the callable leaf name without the overload discriminator."""
    if not name:
        return ""
    return str(name).split("#sig_", 1)[0]


def iter_function_records(file_path: str, file_data: dict, definitions_only=True):
    """
    Yield stable `(uuid, function_dict)` records for C/C++/Rust parsed files.

    UUIDs remain backward-compatible for non-overloaded functions. If multiple
    callables share the same natural UUID, every member of that overload set
    receives a deterministic `#sig_<hash>` suffix based on its signature.
    """
    records = []

    def add(base_uid, func):
        if definitions_only and not is_real_function_definition(func):
            return
        records.append((base_uid, func))

    for func in file_data.get("functions", []) + file_data.get("standalone_functions", []):
        add(f"{file_path}::{func.get('name')}", func)

    for cls in file_data.get("classes", []):
        for method in cls.get("methods", []):
            add(f"{file_path}::{cls.get('name')}::{method.get('name')}", method)

    for impl in file_data.get("impl_blocks", []):
        for method in impl.get("methods", []):
            add(f"{file_path}::{impl.get('target_type')}::{method.get('name')}", method)

    counts = {}
    for base_uid, _ in records:
        counts[base_uid] = counts.get(base_uid, 0) + 1

    used = set()
    for base_uid, func in records:
        uid = base_uid
        if counts.get(base_uid, 0) > 1:
            uid = f"{base_uid}#sig_{_signature_digest(func)}"
            counter = 2
            while uid in used:
                uid = f"{base_uid}#sig_{_signature_digest(func)}_{counter}"
                counter += 1
        used.add(uid)
        yield uid, func
