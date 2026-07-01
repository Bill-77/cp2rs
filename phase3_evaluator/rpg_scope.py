import fnmatch
import re

from .function_uid import iter_function_records, strip_overload_suffix


def _as_string_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def intermediate_function_scope(intermediate: dict) -> dict:
    """
    Return optional function selectors attached to an RPG Intermediate node.

    Normal RPG nodes are physical files and have no filters, which means the
    whole file participates in the parent Root. For monolithic C/C++ files, a
    prompt may emit logical behavior slices sharing the same file_path and list
    the exact functions that belong to that slice in `included_functions`.
    """
    names = []
    for key in ("included_functions", "included_function_names", "function_names"):
        names.extend(_as_string_list(intermediate.get(key)))
    patterns = []
    for key in ("included_function_patterns", "function_patterns"):
        patterns.extend(_as_string_list(intermediate.get(key)))
    return {
        "names": {strip_overload_suffix(name) for name in names if name},
        "patterns": [pattern for pattern in patterns if pattern],
    }


def intermediate_function_filters(intermediate: dict) -> set:
    return intermediate_function_scope(intermediate)["names"]


def _uid_match_candidates(uid: str, func: dict) -> set:
    bare_uid = strip_overload_suffix(uid)
    parts = [part for part in bare_uid.split("::") if part]
    candidates = {uid, bare_uid}
    if parts:
        candidates.add(parts[-1])
    if len(parts) >= 2:
        candidates.add("::".join(parts[-2:]))

    name = str(func.get("name") or "").strip()
    if name:
        candidates.add(name)

    owner = str(func.get("belongs_to_class") or func.get("owner") or "").strip()
    if owner and name:
        candidates.add(f"{owner}::{name}")

    return {strip_overload_suffix(item) for item in candidates if item}


def _pattern_matches(candidate: str, pattern: str) -> bool:
    try:
        if any(char in pattern for char in "^$[]()+{}|\\"):
            return re.search(pattern, candidate) is not None
    except re.error:
        pass
    return fnmatch.fnmatch(candidate, pattern)


def _matches_scope(uid: str, func: dict, scope: dict) -> bool:
    names = scope.get("names") or set()
    patterns = scope.get("patterns") or []
    if not names and not patterns:
        return True
    candidates = _uid_match_candidates(uid, func)
    if candidates & names:
        return True
    return any(
        _pattern_matches(candidate, pattern)
        for candidate in candidates
        for pattern in patterns
    )


def _merge_scope(existing: dict, incoming: dict) -> dict:
    existing.setdefault("names", set()).update(incoming.get("names") or set())
    existing.setdefault("patterns", []).extend(incoming.get("patterns") or [])
    return existing


def collect_root_functions(root_ids_str, rpg, parsed_db, definitions_only=True):
    """
    Collect unique functions for one or more RPG roots.

    If an Intermediate node has no `included_functions`, the whole file is in
    scope. If one or more Intermediate nodes for the same file have filters,
    only the union of those named functions is in scope for that Root. This lets
    Phase 2 split large monolithic C/C++ files into behavior-level slices
    without making Phase 3A see every function in every slice.
    """
    if not root_ids_str:
        return []

    root_ids = {root_id.strip() for root_id in str(root_ids_str).split(",") if root_id.strip()}
    if not root_ids:
        return []

    file_filters = {}
    for inter in rpg.get("nodes", {}).get("intermediate_nodes", []):
        if inter.get("parent_root") not in root_ids:
            continue
        file_path = inter.get("file_path")
        if not file_path:
            continue
        scope = intermediate_function_scope(inter)
        if not scope["names"] and not scope["patterns"]:
            file_filters[file_path] = None
        elif file_path not in file_filters:
            file_filters[file_path] = {
                "names": set(scope["names"]),
                "patterns": list(scope["patterns"]),
            }
        elif file_filters[file_path] is not None:
            _merge_scope(file_filters[file_path], scope)

    unique_funcs = {}
    for file_path, filters in file_filters.items():
        file_data = parsed_db.get("files", {}).get(file_path)
        if not file_data:
            continue
        for uid, func in iter_function_records(file_path, file_data, definitions_only=definitions_only):
            if filters is not None and not _matches_scope(uid, func, filters):
                continue
            unique_funcs[uid] = func

    return list(unique_funcs.items())
