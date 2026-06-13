# CP2RS Phase 3B Adapter Synthesis

You generate a repository-specific 3B public-first adapter.

Important rules:
- Return a single valid JSON object only. No Markdown fences. No explanations outside JSON.
- Return compact JSON when possible; avoid long comments or duplicated prose so the response is not truncated.
- Use the adapter shape shown in `required_adapter_shape`.
- Generate public behavior operations from source test evidence and 3A aligned function pairs.
- Prefer `source_test_case_evidence` over broad file snippets when designing operations: one operation should reflect a concrete source test case or a tight group of source tests with the same observable behavior.
- Prefer `source_assertion_evidence` when deciding executable oracle values: it lists source assertion expressions, literals, and aligned functions mentioned by each assertion.
- Use `source_function_test_evidence` to ground every `source_functions` entry.
- Use `target_aligned_api_context` and `target_public_api_signatures` to write Rust calls that actually exist.
- Use `target_crate_import_hint.crate_name_for_rust_code` when importing the Rust crate in integration tests.
- Do not rely on target repository tests or examples; the target may have no tests. Infer target API usage from Cargo.toml/lib.rs, parsed public signatures, owner_type, call_hint, and body excerpts only.
- For every source function listed in a `public_operations.*.source_functions` entry, copy every corresponding `tgt_uuid` from `alignment_scope.public_eligible_pairs_with_src_test_evidence` into that operation's `target_functions`. You may add support public target APIs too, but do not omit the 3A target recipe for a declared source function.
- Use `source_fixture_evidence` when source tests rely on input/expected files rather than inline literals.
- Pay attention to each target API `owner_type` and `call_hint`; do not call an `Object` method on a `JsonValue` unless you first obtain an `Object` value/reference.
- For target signatures with generic `Into<...>` parameters, pass concrete values directly when possible instead of adding unnecessary `.into()` calls.
- The `normalization` field is an audit note. The actual executable oracle must appear in `rust_test_harness`.
- Do not invent target behavior that is not grounded in source tests or fixtures.
- Maximize reliable coverage of `alignment_scope.public_eligible_pairs_with_src_test_evidence`; do not stop after a few examples if more source-tested public functions have clear assertions or fixtures.
- Broad coverage is welcome only when each operation is still grounded in concrete source test evidence. Omit a function only when replay would require speculation or non-public target APIs.
- Avoid brittle exact string-format assertions unless the source test/fixture explicitly provides that exact expected string. For printing/pretty output without exact expected fixtures, prefer parseability, structural checks, or clearly grounded substring/property checks.
- For every trace event, set `oracle_source` and `oracle_confidence`. Use `high` only for concrete assertions or expected fixtures. Use `medium` for normalized behavior properties inferred from source tests.
- Use only public Rust APIs in `rust_test_harness`.
- Every `trace_events[].id` must be a valid Rust function identifier.
- The Rust harness must define exactly one `#[test] fn <trace_event_id>()` for each trace event id.
- Do not add extra `#[test]` functions without a matching trace event id.
- If you want to test another behavior, declare a matching `public_operations` entry and `trace_events` entry.
- If a source aligned function is too hard to replay reliably, omit it; the framework will count it as adapter_missing.
- The `evidence` fields should cite concrete source test paths/names from the context.
- Every declared target function should appear in the Rust harness through the actual target API call.
- The Rust integration test must compile as tests/cp2rs_3b_public.rs inside the target crate.

Context:
{
  "schema_version": "3b.adapter_synthesis_context.v3",
  "source_repository": "cJSON",
  "target_repository": "json-rust",
  "objective": "Generate a repository-specific 3B public-first adapter. Use source test evidence and 3A alignments to create replayable public behavior operations.",
  "constraints": [
    "Do not compare ABI, raw pointer values, memory ownership, or raw return types when languages differ.",
    "Derive observable behavior from source tests, fixtures, expected files, and assertion intent.",
    "Use only public target APIs for L1 replay.",
    "If an aligned function has test evidence but no reliable replay recipe, omit it so adapter_missing can report it.",
    "The LLM generates a replay hypothesis; correctness is decided only by compiling and running target replay."
  ],
  "generation_policy": {
    "public_first": true,
    "default_layer": "public_behavior",
    "adapter_is_repo_specific": true,
    "oracle_rule": "Every executable assertion must be grounded in source test evidence, fixtures, or a direct public API property implied by that evidence. Use oracle_confidence=high only when the source test/fixture gives a concrete expected result.",
    "coverage_rule": "Maximize reliable coverage of source-tested public 3A pairs. Group functions by concrete source test cases when needed, and omit a function only when its observable behavior cannot be replayed through public target APIs without speculation."
  },
  "alignment_scope": {
    "public_eligible_pairs_with_src_test_evidence": [
      {
        "src_uuid": "cJSON.c::cJSON_GetStringValue",
        "src_signature": "CJSON_PUBLIC(char *) cJSON_GetStringValue(const cJSON * const item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::as_str"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::as_str",
            "signature": "pub fn as_str(&self) -> Option<&str>"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_GetNumberValue",
        "src_signature": "CJSON_PUBLIC(double) cJSON_GetNumberValue(const cJSON * const item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::as_f64"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::as_f64",
            "signature": "pub fn as_f64(&self) -> Option<f64>"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_Parse",
        "src_signature": "CJSON_PUBLIC(cJSON *) cJSON_Parse(const char *value)",
        "tgt_uuids": [
          "src/parser.rs::parse"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/parser.rs::parse",
            "signature": "pub fn parse(source: &str) -> Result<JsonValue>"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_ParseWithOpts",
        "src_signature": "CJSON_PUBLIC(cJSON *) cJSON_ParseWithOpts(const char *value, const char **return_parse_end, cJSON_bool require_null_terminated)",
        "tgt_uuids": [
          "src/parser.rs::parse"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/parser.rs::parse",
            "signature": "pub fn parse(source: &str) -> Result<JsonValue>"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_Print",
        "src_signature": "CJSON_PUBLIC(char *) cJSON_Print(const cJSON *item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::pretty"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::pretty",
            "signature": "pub fn pretty(&self, spaces: u16) -> String"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_PrintUnformatted",
        "src_signature": "CJSON_PUBLIC(char *) cJSON_PrintUnformatted(const cJSON *item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::dump"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::dump",
            "signature": "pub fn dump(&self) -> String"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_GetArraySize",
        "src_signature": "CJSON_PUBLIC(int) cJSON_GetArraySize(const cJSON *array)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::len"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::len",
            "signature": "pub fn len(&self) -> usize"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_GetObjectItemCaseSensitive",
        "src_signature": "CJSON_PUBLIC(cJSON *) cJSON_GetObjectItemCaseSensitive(const cJSON * const object, const char * const string)",
        "tgt_uuids": [
          "src/object.rs::Object::get"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::get",
            "signature": "pub fn get(&self, key: &str) -> Option<&JsonValue>"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_HasObjectItem",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_HasObjectItem(const cJSON *object, const char *string)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::has_key"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::has_key",
            "signature": "pub fn has_key(&self, key: &str) -> bool"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddItemToArray",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_AddItemToArray(cJSON *array, cJSON *item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::push"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::push",
            "signature": "pub fn push<T>(&mut self, value: T) -> Result<()>\r\n    where T: Into<JsonValue>"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddItemToObject",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_AddItemToObject(cJSON *object, const char *string, cJSON *item)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddItemToObjectCS",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_AddItemToObjectCS(cJSON *object, const char *string, cJSON *item)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddTrueToObject",
        "src_signature": "CJSON_PUBLIC(cJSON*) cJSON_AddTrueToObject(cJSON * const object, const char * const name)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddFalseToObject",
        "src_signature": "CJSON_PUBLIC(cJSON*) cJSON_AddFalseToObject(cJSON * const object, const char * const name)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddBoolToObject",
        "src_signature": "CJSON_PUBLIC(cJSON*) cJSON_AddBoolToObject(cJSON * const object, const char * const name, const cJSON_bool boolean)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddNumberToObject",
        "src_signature": "CJSON_PUBLIC(cJSON*) cJSON_AddNumberToObject(cJSON * const object, const char * const name, const double number)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddStringToObject",
        "src_signature": "CJSON_PUBLIC(cJSON*) cJSON_AddStringToObject(cJSON * const object, const char * const name, const char * const string)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddObjectToObject",
        "src_signature": "CJSON_PUBLIC(cJSON*) cJSON_AddObjectToObject(cJSON * const object, const char * const name)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_AddArrayToObject",
        "src_signature": "CJSON_PUBLIC(cJSON*) cJSON_AddArrayToObject(cJSON * const object, const char * const name)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "Medium"
      },
      {
        "src_uuid": "cJSON.c::cJSON_DetachItemFromObject",
        "src_signature": "CJSON_PUBLIC(cJSON *) cJSON_DetachItemFromObject(cJSON *object, const char *string)",
        "tgt_uuids": [
          "src/object.rs::Object::remove"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::remove",
            "signature": "pub fn remove(&mut self, key: &str) -> Option<JsonValue>"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_DetachItemFromObjectCaseSensitive",
        "src_signature": "CJSON_PUBLIC(cJSON *) cJSON_DetachItemFromObjectCaseSensitive(cJSON *object, const char *string)",
        "tgt_uuids": [
          "src/object.rs::Object::remove"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::remove",
            "signature": "pub fn remove(&mut self, key: &str) -> Option<JsonValue>"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_DeleteItemFromObject",
        "src_signature": "CJSON_PUBLIC(void) cJSON_DeleteItemFromObject(cJSON *object, const char *string)",
        "tgt_uuids": [
          "src/object.rs::Object::remove"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::remove",
            "signature": "pub fn remove(&mut self, key: &str) -> Option<JsonValue>"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_DeleteItemFromObjectCaseSensitive",
        "src_signature": "CJSON_PUBLIC(void) cJSON_DeleteItemFromObjectCaseSensitive(cJSON *object, const char *string)",
        "tgt_uuids": [
          "src/object.rs::Object::remove"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::remove",
            "signature": "pub fn remove(&mut self, key: &str) -> Option<JsonValue>"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_ReplaceItemInObject",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_ReplaceItemInObject(cJSON *object, const char *string, cJSON *newitem)",
        "tgt_uuids": [
          "src/object.rs::Object::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/object.rs::Object::insert",
            "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_DetachItemFromArray",
        "src_signature": "CJSON_PUBLIC(cJSON *) cJSON_DetachItemFromArray(cJSON *array, int which)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::array_remove"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::array_remove",
            "signature": "pub fn array_remove(&mut self, index: usize) -> JsonValue"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_DeleteItemFromArray",
        "src_signature": "CJSON_PUBLIC(void) cJSON_DeleteItemFromArray(cJSON *array, int which)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::array_remove"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::array_remove",
            "signature": "pub fn array_remove(&mut self, index: usize) -> JsonValue"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_ReplaceItemInObjectCaseSensitive",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_ReplaceItemInObjectCaseSensitive(cJSON *object, const char *string, cJSON *newitem)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::insert"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::insert",
            "signature": "pub fn insert<T>(&mut self, key: &str, value: T) -> Result<()>\r\n    where T: Into<JsonValue>"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_CreateArray",
        "src_signature": "CJSON_PUBLIC(cJSON *) cJSON_CreateArray(void)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::new_array"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::new_array",
            "signature": "pub fn new_array() -> JsonValue"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_CreateObject",
        "src_signature": "CJSON_PUBLIC(cJSON *) cJSON_CreateObject(void)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::new_object"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::new_object",
            "signature": "pub fn new_object() -> JsonValue"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_IsBool",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_IsBool(const cJSON * const item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::is_boolean"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::is_boolean",
            "signature": "pub fn is_boolean(&self) -> bool"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_IsNull",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_IsNull(const cJSON * const item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::is_null"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::is_null",
            "signature": "pub fn is_null(&self) -> bool"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_IsNumber",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_IsNumber(const cJSON * const item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::is_number"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::is_number",
            "signature": "pub fn is_number(&self) -> bool"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_IsString",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_IsString(const cJSON * const item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::is_string"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::is_string",
            "signature": "pub fn is_string(&self) -> bool"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_IsArray",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_IsArray(const cJSON * const item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::is_array"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::is_array",
            "signature": "pub fn is_array(&self) -> bool"
          }
        ],
        "confidence": "High"
      },
      {
        "src_uuid": "cJSON.c::cJSON_IsObject",
        "src_signature": "CJSON_PUBLIC(cJSON_bool) cJSON_IsObject(const cJSON * const item)",
        "tgt_uuids": [
          "src/value/mod.rs::JsonValue::is_object"
        ],
        "target_signatures": [
          {
            "tgt_uuid": "src/value/mod.rs::JsonValue::is_object",
            "signature": "pub fn is_object(&self) -> bool"
          }
        ],
        "confidence": "High"
      }
    ],
    "public_eligible_pair_count": 35,
    "scoped_pair_count": 35
  },
  "test_inventory_summary": {
    "test_files": 24,
    "test_cases": 162,
    "aligned_test_cases": 62,
    "build_targets": 26,
    "framework_files": {
      "cmake_ctest": 2,
      "unity": 21
    },
    "device_required_files": 0
  },
  "source_test_evidence": [
    {
      "path": "tests/misc_tests.c",
      "frameworks": [
        "unity"
      ],
      "test_cases": [
        {
          "framework": "unity",
          "name": "cjson_array_foreach_should_loop_over_arrays"
        },
        {
          "framework": "unity",
          "name": "cjson_array_foreach_should_not_dereference_null_pointer"
        },
        {
          "framework": "unity",
          "name": "cjson_get_object_item_should_get_object_items"
        },
        {
          "framework": "unity",
          "name": "cjson_get_object_item_case_sensitive_should_get_object_items"
        },
        {
          "framework": "unity",
          "name": "cjson_get_object_item_should_not_crash_with_array"
        },
        {
          "framework": "unity",
          "name": "cjson_get_object_item_case_sensitive_should_not_crash_with_array"
        },
        {
          "framework": "unity",
          "name": "typecheck_functions_should_check_type"
        },
        {
          "framework": "unity",
          "name": "cjson_should_not_parse_to_deeply_nested_jsons"
        },
        {
          "framework": "unity",
          "name": "cjson_should_not_follow_too_deep_circular_references"
        },
        {
          "framework": "unity",
          "name": "cjson_set_number_value_should_set_numbers"
        },
        {
          "framework": "unity",
          "name": "cjson_detach_item_via_pointer_should_detach_items"
        },
        {
          "framework": "unity",
          "name": "cjson_detach_item_via_pointer_should_return_null_if_item_prev_is_null"
        },
        {
          "framework": "unity",
          "name": "cjson_replace_item_via_pointer_should_replace_items"
        },
        {
          "framework": "unity",
          "name": "cjson_replace_item_in_object_should_preserve_name"
        },
        {
          "framework": "unity",
          "name": "cjson_functions_should_not_crash_with_null_pointers"
        },
        {
          "framework": "unity",
          "name": "cjson_set_valuestring_should_return_null_if_strings_overlap"
        },
        {
          "framework": "unity",
          "name": "ensure_should_fail_on_failed_realloc"
        },
        {
          "framework": "unity",
          "name": "skip_utf8_bom_should_skip_bom"
        },
        {
          "framework": "unity",
          "name": "skip_utf8_bom_should_not_skip_bom_if_not_at_beginning"
        },
        {
          "framework": "unity",
          "name": "cjson_get_string_value_should_get_a_string"
        }
      ],
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_AddItemToArray",
        "cJSON_AddItemToObject",
        "cJSON_AddItemToObjectCS",
        "cJSON_CreateArray",
        "cJSON_CreateObject",
        "cJSON_DeleteItemFromArray",
        "cJSON_DeleteItemFromObject",
        "cJSON_DeleteItemFromObjectCaseSensitive",
        "cJSON_DetachItemFromArray",
        "cJSON_DetachItemFromObject",
        "cJSON_DetachItemFromObjectCaseSensitive",
        "cJSON_GetArraySize",
        "cJSON_GetNumberValue",
        "cJSON_GetObjectItemCaseSensitive",
        "cJSON_GetStringValue",
        "cJSON_HasObjectItem",
        "cJSON_IsArray",
        "cJSON_IsBool",
        "cJSON_IsNull",
        "cJSON_IsNumber",
        "cJSON_IsObject",
        "cJSON_IsString",
        "cJSON_Parse",
        "cJSON_ParseWithOpts",
        "cJSON_Print",
        "cJSON_PrintUnformatted",
        "cJSON_ReplaceItemInObject",
        "cJSON_ReplaceItemInObjectCaseSensitive"
      ],
      "snippet": "64:     cJSON_ArrayForEach(element, array);\n65: }\n66: \n67: static void cjson_get_object_item_should_get_object_items(void)\n68: {\n69:     cJSON *item = NULL;\n70:     cJSON *found = NULL;\n71: \n72:     item = cJSON_Parse(\"{\\\"one\\\":1, \\\"Two\\\":2, \\\"tHree\\\":3}\");\n73: \n74:     found = cJSON_GetObjectItem(NULL, \"test\");\n75:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");\n76: \n77:     found = cJSON_GetObjectItem(item, NULL);\n78:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");\n79: \n80:     found = cJSON_GetObjectItem(item, \"one\");\n81:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");\n82:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);\n83: \n84:     found = cJSON_GetObjectItem(item, \"tWo\");\n85:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");\n...\n95:     cJSON_Delete(item);\n96: }\n97: \n98: static void cjson_get_object_item_case_sensitive_should_get_object_items(void)\n99: {\n100:     cJSON *item = NULL;\n101:     cJSON *found = NULL;\n102: \n103:     item = cJSON_Parse(\"{\\\"one\\\":1, \\\"Two\\\":2, \\\"tHree\\\":3}\");\n104: \n105:     found = cJSON_GetObjectItemCaseSensitive(NULL, \"test\");\n106:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");\n107: \n108:     found = cJSON_GetObjectItemCaseSensitive(item, NULL);\n109:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");\n110: \n111:     found = cJSON_GetObjectItemCaseSensitive(item, \"one\");\n112:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");\n113:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);\n114: \n115:     found = cJSON_GetObjectItemCaseSensitive(item, \"Two\");\n116:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");\n117:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);\n118: \n119:     found = cJSON_GetObjectItemCaseSensitive(item, \"tHree\");\n120:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");\n121:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);\n122: \n123:     found = cJSON_GetObjectItemCaseSensitive(item, \"One\");\n124:     TEST_ASSERT_NULL_MESSAGE(found, \"Should not find something that isn't there.\");\n125: \n126:     cJSON_Delete(item);\n127: }\n128: \n129: static void cjson_get_object_item_should_not_crash_with_array(void)\n130: {\n131:     cJSON *array = NULL;\n132:     cJSON *found = NULL;\n133:     array = cJSON_Parse(\"[1]\");\n134: \n135:     found = cJSON_GetObjectItem(array, \"name\");\n136:     TEST_ASSERT_NULL(found);\n137: \n138:     cJSON_Delete(array);\n139: }\n140: \n141: static void cjson_get_object_item_case_sensitive_should_not_crash_with_array(void)\n142: {\n143:     cJSON *array = NULL;\n144:     cJSON *found = NULL;\n145:     array = cJSON_Parse(\"[1]\");\n146: \n147:     found = cJSON_GetObjectItemCaseSensitive(array, \"name\");\n148:     TEST_ASSERT_NULL(found);\n149: \n150:     cJSON_Delete(array);\n151: }\n152: \n153: static void typecheck_functions_should_check_type(void)\n154: {\n155:     cJSON invalid[1];\n156:     cJSON item[1];\n157:     invalid->type = cJSON_Invalid;\n158:     invalid->type |= cJSON_StringIsConst;\n159:     item->type = cJSON_False;\n160:     item->type |= cJSON_StringIsConst;\n...\n162:     TEST_ASSERT_FALSE(cJSON_IsInvalid(NULL));\n163:     TEST_ASSERT_FALSE(cJSON_IsInvalid(item));\n164:     TEST_ASSERT_TRUE(cJSON_IsInvalid(invalid));\n165: \n166:     item->type = cJSON_False | cJSON_StringIsConst;\n167:     TEST_ASSERT_FALSE(cJSON_IsFalse(NULL));\n168:     TEST_ASSERT_FALSE(cJSON_IsFalse(invalid));\n169:     TEST_ASSERT_TRUE(cJSON_IsFalse(item));\n170:     TEST_ASSERT_TRUE(cJSON_IsBool(item));\n171: \n172:     item->type = cJSON_True | cJSON_StringIsConst;\n173:     TEST_ASSERT_FALSE(cJSON_IsTrue(NULL));\n174:     TEST_ASSERT_FALSE(cJSON_IsTrue(invalid));\n175:     TEST_ASSERT_TRUE(cJSON_IsTrue(item));\n176:     TEST_ASSERT_TRUE(cJSON_IsBool(item));\n177: \n178:     item->type = cJSON_NULL | cJSON_StringIsConst;\n179:     TEST_ASSERT_FALSE(cJSON_IsNull(NULL));\n180:     TEST_ASSERT_FALSE(cJSON_IsNull(invalid));\n181:     TEST_ASSERT_TRUE(cJSON_IsNull(item));\n182: \n183:     item->type = cJSON_Number | cJSON_StringIsConst;\n184:     TEST_ASSERT_FALSE(cJSON_IsNumber(NULL));\n185:     TEST_ASSERT_FALSE(cJSON_IsNumber(inv",
      "assertion_lines": [
        "75:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");",
        "78:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");",
        "81:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
        "82:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);",
        "85:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
        "106:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");",
        "109:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");",
        "112:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
        "113:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);",
        "116:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
        "117:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);",
        "120:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");",
        "121:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);",
        "124:     TEST_ASSERT_NULL_MESSAGE(found, \"Should not find something that isn't there.\");",
        "136:     TEST_ASSERT_NULL(found);",
        "148:     TEST_ASSERT_NULL(found);",
        "162:     TEST_ASSERT_FALSE(cJSON_IsInvalid(NULL));",
        "163:     TEST_ASSERT_FALSE(cJSON_IsInvalid(item));"
      ],
      "literal_samples": [
        "\"{\\\"one\\\":1, \\\"Two\\\":2, \\\"tHree\\\":3}\"",
        "\"test\"",
        "\"Failed to fail on NULL pointer.\"",
        "\"Failed to fail on NULL string.\"",
        "\"one\"",
        "\"Failed to find first item.\"",
        "\"tWo\"",
        "\"Two\"",
        "\"tHree\"",
        "\"Failed to find item.\"",
        "\"One\"",
        "\"Should not find something that isn't there.\"",
        "\"[1]\"",
        "\"name\"",
        "64",
        "65",
        "66",
        "67",
        "68",
        "69",
        "70",
        "71",
        "72",
        "1",
        "2",
        "3",
        "73",
        "74"
      ]
    },
    {
      "path": "tests/readme_examples.c",
      "frameworks": [
        "unity"
      ],
      "test_cases": [
        {
          "framework": "unity",
          "name": "create_monitor_should_create_a_monitor"
        },
        {
          "framework": "unity",
          "name": "create_monitor_with_helpers_should_create_a_monitor"
        },
        {
          "framework": "unity",
          "name": "supports_full_hd_should_check_for_full_hd_support"
        }
      ],
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_AddItemToArray",
        "cJSON_AddItemToObject",
        "cJSON_AddNumberToObject",
        "cJSON_AddStringToObject",
        "cJSON_CreateArray",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive",
        "cJSON_IsNumber",
        "cJSON_IsString",
        "cJSON_Parse",
        "cJSON_Print"
      ],
      "snippet": "52:     char *string = NULL;\n53:     cJSON *name = NULL;\n54:     cJSON *resolutions = NULL;\n55:     cJSON *resolution = NULL;\n56:     cJSON *width = NULL;\n57:     cJSON *height = NULL;\n58:     size_t index = 0;\n59: \n60:     cJSON *monitor = cJSON_CreateObject();\n61:     if (monitor == NULL)\n62:     {\n63:         goto end;\n64:     }\n65: \n66:     name = cJSON_CreateString(\"Awesome 4K\");\n67:     if (name == NULL)\n68:     {\n69:         goto end;\n70:     }\n71:     /* after creation was successful, immediately add it to the monitor,\n72:      * thereby transferring ownership of the pointer to it */\n73:     cJSON_AddItemToObject(monitor, \"name\", name);\n74: \n75:     resolutions = cJSON_CreateArray();\n76:     if (resolutions == NULL)\n77:     {\n78:         goto end;\n79:     }\n80:     cJSON_AddItemToObject(monitor, \"resolutions\", resolutions);\n81: \n82:     for (index = 0; index < (sizeof(resolution_numbers) / (2 * sizeof(int))); ++index)\n83:     {\n84:         resolution = cJSON_CreateObject();\n85:         if (resolution == NULL)\n86:         {\n87:             goto end;\n88:         }\n89:         cJSON_AddItemToArray(resolutions, resolution);\n90: \n91:         width = cJSON_CreateNumber(resolution_numbers[index][0]);\n92:         if (width == NULL)\n93:         {\n94:             goto end;\n95:         }\n96:         cJSON_AddItemToObject(resolution, \"width\", width);\n97: \n98:         height = cJSON_CreateNumber(resolution_numbers[index][1]);\n99:         if (height == NULL)\n100:         {\n101:             goto end;\n102:         }\n103:         cJSON_AddItemToObject(resolution, \"height\", height);\n104:     }\n105: \n106:     string = cJSON_Print(monitor);\n107:     if (string == NULL)\n108:     {\n109:         fprintf(stderr, \"Failed to print monitor.\\n\");\n110:     }\n111: \n112: end:\n113:     cJSON_Delete(monitor);\n114:     return string;\n115: }\n116: \n117: static char *create_monitor_with_helpers(void)\n118: {\n119:     const unsigned int resolution_numbers[3][2] = {\n120:         {1280, 720},\n121:         {1920, 1080},\n122:         {3840, 2160}\n123:     };\n124:     char *string = NULL;\n125:     cJSON *resolutions = NULL;\n126:     size_t index = 0;\n127: \n128:     cJSON *monitor = cJSON_CreateObject();\n129: \n130:     if (cJSON_AddStringToObject(monitor, \"name\", \"Awesome 4K\") == NULL)\n131:     {\n132:         goto end;\n133:     }\n134: \n135:     resolutions = cJSON_AddArrayToObject(monitor, \"resolutions\");\n136:     if (resolutions == NULL)\n137:     {\n138:         goto end;\n139:     }\n140: \n141:     for (index = 0; index < (sizeof(resolution_numbers) / (2 * sizeof(int))); ++index)\n142:     {\n143:         cJSON *resolution = cJSON_CreateObject();\n144: \n145:         if (cJSON_AddNumberToObject(resolution, \"width\", resolution_numbers[index][0]) == NULL)\n146:         {\n147:             goto end;\n148:         }\n149: \n150:         if(cJSON_AddNumberToObject(resolution, \"height\", resolution_numbers[index][1]) == NULL)\n151:         {\n152:             goto end;\n153:         }\n154: \n155:         cJSON_AddItemToArray(resolutions, resolution);\n156:     }\n157: \n158:     string = cJSON_Print(monitor);\n159:     if (string == NULL) {\n160:         fprintf(stderr, \"Failed to print monitor.\\n\");\n161:     }\n162: \n163: end:\n164:     cJSON_Delete(monitor);\n165:     return string;\n166: }\n167: \n168: /* return 1 if the monitor supports full hd, 0 otherwise */\n169: static int supports_full_hd(const char * const monitor)\n170: {\n171:     const cJSON *resolution = NULL;\n172:     const cJSON *resolutions = NULL;\n173:     const cJSON *name = NULL;\n174:     int status = 0;\n175:     cJSON *monitor_json = cJSON_Parse(monitor);\n176:     if (monitor_json == NULL)\n177:     {\n178:         const char *error_ptr = cJSON_GetErrorPtr();\n179:         if (error_ptr != NULL)\n180:         {\n181:             fprintf(stderr, \"Error before: %s\\n\", error_ptr);\n182:         }\n183:         status = 0;\n184:         goto end;\n185:     }\n186: \n187:     name = cJSON_GetObjectItemCaseSensitive(monitor_json, \"name\");\n188:     if (cJSON_IsString(name) && (name->valuestring != NULL))\n189:     {\n190:         printf(\"Checking monitor \\\"%s\\\"\\n\", name->valuestring);\n191:     }\n192: \n193:     resolutions = cJSON_GetObjectIte",
      "assertion_lines": [],
      "literal_samples": [
        "\"Awesome 4K\"",
        "\"name\"",
        "\"resolutions\"",
        "\"width\"",
        "\"height\"",
        "\"Failed to print monitor.\\n\"",
        "\"Error before: %s\\n\"",
        "\"Checking monitor \\\"%s\\\"\\n\"",
        "52",
        "53",
        "54",
        "55",
        "56",
        "57",
        "58",
        "0",
        "59",
        "60",
        "61",
        "62",
        "63",
        "64",
        "65",
        "66",
        "67",
        "68",
        "69",
        "70"
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "frameworks": [
        "unity"
      ],
      "test_cases": [
        {
          "framework": "unity",
          "name": "cjson_add_null_should_add_null"
        },
        {
          "framework": "unity",
          "name": "cjson_add_null_should_fail_with_null_pointers"
        },
        {
          "framework": "unity",
          "name": "cjson_add_null_should_fail_on_allocation_failure"
        },
        {
          "framework": "unity",
          "name": "cjson_add_true_should_add_true"
        },
        {
          "framework": "unity",
          "name": "cjson_add_true_should_fail_with_null_pointers"
        },
        {
          "framework": "unity",
          "name": "cjson_add_true_should_fail_on_allocation_failure"
        },
        {
          "framework": "unity",
          "name": "cjson_create_int_array_should_fail_on_allocation_failure"
        },
        {
          "framework": "unity",
          "name": "cjson_create_float_array_should_fail_on_allocation_failure"
        },
        {
          "framework": "unity",
          "name": "cjson_create_double_array_should_fail_on_allocation_failure"
        },
        {
          "framework": "unity",
          "name": "cjson_create_string_array_should_fail_on_allocation_failure"
        },
        {
          "framework": "unity",
          "name": "cjson_add_false_should_add_false"
        },
        {
          "framework": "unity",
          "name": "cjson_add_false_should_fail_with_null_pointers"
        },
        {
          "framework": "unity",
          "name": "cjson_add_false_should_fail_on_allocation_failure"
        },
        {
          "framework": "unity",
          "name": "cjson_add_bool_should_add_bool"
        },
        {
          "framework": "unity",
          "name": "cjson_add_bool_should_fail_with_null_pointers"
        },
        {
          "framework": "unity",
          "name": "cjson_add_bool_should_fail_on_allocation_failure"
        },
        {
          "framework": "unity",
          "name": "cjson_add_number_should_add_number"
        },
        {
          "framework": "unity",
          "name": "cjson_add_number_should_fail_with_null_pointers"
        },
        {
          "framework": "unity",
          "name": "cjson_add_number_should_fail_on_allocation_failure"
        },
        {
          "framework": "unity",
          "name": "cjson_add_string_should_add_string"
        }
      ],
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_AddBoolToObject",
        "cJSON_AddFalseToObject",
        "cJSON_AddNumberToObject",
        "cJSON_AddObjectToObject",
        "cJSON_AddStringToObject",
        "cJSON_AddTrueToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "snippet": "42: \n43: static cJSON_Hooks failing_hooks = {\n44:     failing_malloc,\n45:     normal_free\n46: };\n47: \n48: static void cjson_add_null_should_add_null(void)\n49: {\n50:     cJSON *root = cJSON_CreateObject();\n51:     cJSON *null = NULL;\n52: \n53:     cJSON_AddNullToObject(root, \"null\");\n54: \n55:     TEST_ASSERT_NOT_NULL(null = cJSON_GetObjectItemCaseSensitive(root, \"null\"));\n56:     TEST_ASSERT_EQUAL_INT(null->type, cJSON_NULL);\n57: \n58:     cJSON_Delete(root);\n59: }\n60: \n61: static void cjson_add_null_should_fail_with_null_pointers(void)\n62: {\n63:     cJSON *root = cJSON_CreateObject();\n64: \n65:     TEST_ASSERT_NULL(cJSON_AddNullToObject(NULL, \"null\"));\n66:     TEST_ASSERT_NULL(cJSON_AddNullToObject(root, NULL));\n67: \n68:     cJSON_Delete(root);\n69: }\n70: \n71: static void cjson_add_null_should_fail_on_allocation_failure(void)\n72: {\n73:     cJSON *root = cJSON_CreateObject();\n74: \n75:     cJSON_InitHooks(&failing_hooks);\n76: \n77:     TEST_ASSERT_NULL(cJSON_AddNullToObject(root, \"null\"));\n78: \n79:     cJSON_InitHooks(NULL);\n80: \n81:     cJSON_Delete(root);\n82: }\n83: \n84: static void cjson_add_true_should_add_true(void)\n85: {\n86:     cJSON *root = cJSON_CreateObject();\n87:     cJSON *true_item = NULL;\n88: \n89:     cJSON_AddTrueToObject(root, \"true\");\n90: \n91:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));\n92:     TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);\n93: \n94:     cJSON_Delete(root);\n95: }\n96: \n97: static void cjson_add_true_should_fail_with_null_pointers(void)\n98: {\n99:     cJSON *root = cJSON_CreateObject();\n100: \n101:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(NULL, \"true\"));\n102:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, NULL));\n103: \n104:     cJSON_Delete(root);\n105: }\n106: \n107: static void cjson_add_true_should_fail_on_allocation_failure(void)\n108: {\n109:     cJSON *root = cJSON_CreateObject();\n110: \n111:     cJSON_InitHooks(&failing_hooks);\n112: \n113:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, \"true\"));\n114: \n115:     cJSON_InitHooks(NULL);\n116: \n117:     cJSON_Delete(root);\n118: }\n119: \n120: static void cjson_create_int_array_should_fail_on_allocation_failure(void)\n121: {\n122:     int numbers[] = {1, 2, 3};\n123: \n124:     cJSON_InitHooks(&failing_hooks);\n125: \n126:     TEST_ASSERT_NULL(cJSON_CreateIntArray(numbers, 3));\n...\n158: \n159:     TEST_ASSERT_NULL(cJSON_CreateStringArray(strings, 3));\n160: \n161:     cJSON_InitHooks(NULL);\n162: }\n163: \n164: static void cjson_add_false_should_add_false(void)\n165: {\n166:     cJSON *root = cJSON_CreateObject();\n167:     cJSON *false_item = NULL;\n168: \n169:     cJSON_AddFalseToObject(root, \"false\");\n170: \n171:     TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));\n172:     TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);\n173: \n174:     cJSON_Delete(root);\n175: }\n176: \n177: static void cjson_add_false_should_fail_with_null_pointers(void)\n178: {\n179:     cJSON *root = cJSON_CreateObject();\n180: \n181:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(NULL, \"false\"));\n182:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, NULL));\n183: \n184:     cJSON_Delete(root);\n185: }\n186: \n187: static void cjson_add_false_should_fail_on_allocation_failure(void)\n188: {\n189:     cJSON *root = cJSON_CreateObject();\n190: \n191:     cJSON_InitHooks(&failing_hooks);\n192: \n193:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, \"false\"));\n194: \n195:     cJSON_InitHooks(NULL);\n196: \n197:     cJSON_Delete(root);\n198: }\n199: \n200: static void cjson_add_bool_should_add_bool(void)\n201: {\n202:     cJSON *root = cJSON_CreateObject();\n203:     cJSON *true_item = NULL;\n204:     cJSON *false_item = NULL;\n205: \n206:     /* true */\n207:     cJSON_AddBoolToObject(root, \"true\", true);\n208:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));\n209:     TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);\n210: \n211:     /* false */\n212:     cJSON_AddBoolToObject(root, \"false\", false);\n213:     TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));\n214:     TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);\n215: \n216:     cJSON_Delete(root);\n217: }\n218: \n219: static voi",
      "assertion_lines": [
        "55:     TEST_ASSERT_NOT_NULL(null = cJSON_GetObjectItemCaseSensitive(root, \"null\"));",
        "56:     TEST_ASSERT_EQUAL_INT(null->type, cJSON_NULL);",
        "65:     TEST_ASSERT_NULL(cJSON_AddNullToObject(NULL, \"null\"));",
        "66:     TEST_ASSERT_NULL(cJSON_AddNullToObject(root, NULL));",
        "77:     TEST_ASSERT_NULL(cJSON_AddNullToObject(root, \"null\"));",
        "91:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));",
        "92:     TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);",
        "101:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(NULL, \"true\"));",
        "102:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, NULL));",
        "113:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, \"true\"));",
        "126:     TEST_ASSERT_NULL(cJSON_CreateIntArray(numbers, 3));",
        "159:     TEST_ASSERT_NULL(cJSON_CreateStringArray(strings, 3));",
        "171:     TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));",
        "172:     TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);",
        "181:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(NULL, \"false\"));",
        "182:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, NULL));",
        "193:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, \"false\"));",
        "208:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));"
      ],
      "literal_samples": [
        "\"null\"",
        "\"true\"",
        "\"false\"",
        "42",
        "43",
        "44",
        "45",
        "46",
        "47",
        "48",
        "49",
        "50",
        "51",
        "52",
        "53",
        "54",
        "55",
        "56",
        "57",
        "58",
        "59",
        "60",
        "61",
        "62",
        "63",
        "64",
        "65",
        "66"
      ]
    },
    {
      "path": "test.c",
      "frameworks": [],
      "test_cases": [],
      "calls_aligned_public_functions": [
        "cJSON_AddFalseToObject",
        "cJSON_AddItemToArray",
        "cJSON_AddItemToObject",
        "cJSON_AddNumberToObject",
        "cJSON_AddStringToObject",
        "cJSON_CreateArray",
        "cJSON_CreateObject",
        "cJSON_Print",
        "cJSON_ReplaceItemInObject"
      ],
      "snippet": "45:     /* declarations */\n46:     char *out = NULL;\n47:     char *buf = NULL;\n48:     char *buf_fail = NULL;\n49:     size_t len = 0;\n50:     size_t len_fail = 0;\n51: \n52:     /* formatted print */\n53:     out = cJSON_Print(root);\n54: \n55:     /* create buffer to succeed */\n56:     /* the extra 5 bytes are because of inaccuracies when reserving memory */\n57:     len = strlen(out) + 5;\n58:     buf = (char*)malloc(len);\n59:     if (buf == NULL)\n60:     {\n61:         printf(\"Failed to allocate memory.\\n\");\n62:         exit(1);\n63:     }\n64: \n65:     /* create buffer to fail */\n66:     len_fail = strlen(out);\n...\n160:             \"US\"\n161:         }\n162:     };\n163:     volatile double zero = 0.0;\n164: \n165:     /* Here we construct some JSON standards, from the JSON site. */\n166: \n167:     /* Our \"Video\" datatype: */\n168:     root = cJSON_CreateObject();\n169:     cJSON_AddItemToObject(root, \"name\", cJSON_CreateString(\"Jack (\\\"Bee\\\") Nimble\"));\n170:     cJSON_AddItemToObject(root, \"format\", fmt = cJSON_CreateObject());\n171:     cJSON_AddStringToObject(fmt, \"type\", \"rect\");\n172:     cJSON_AddNumberToObject(fmt, \"width\", 1920);\n173:     cJSON_AddNumberToObject(fmt, \"height\", 1080);\n174:     cJSON_AddFalseToObject (fmt, \"interlace\");\n175:     cJSON_AddNumberToObject(fmt, \"frame rate\", 24);\n176: \n177:     /* Print to text */\n178:     if (print_preallocated(root) != 0) {\n179:         cJSON_Delete(root);\n180:         exit(EXIT_FAILURE);\n181:     }\n182:     cJSON_Delete(root);\n183: \n184:     /* Our \"days of the week\" array: */\n185:     root = cJSON_CreateStringArray(strings, 7);\n186: \n187:     if (print_preallocated(root) != 0) {\n188:         cJSON_Delete(root);\n189:         exit(EXIT_FAILURE);\n190:     }\n191:     cJSON_Delete(root);\n192: \n193:     /* Our matrix: */\n194:     root = cJSON_CreateArray();\n195:     for (i = 0; i < 3; i++)\n196:     {\n197:         cJSON_AddItemToArray(root, cJSON_CreateIntArray(numbers[i], 3));\n198:     }\n199: \n200:     /* cJSON_ReplaceItemInArray(root, 1, cJSON_CreateString(\"Replacement\")); */\n201: \n202:     if (print_preallocated(root) != 0) {\n203:         cJSON_Delete(root);\n204:         exit(EXIT_FAILURE);\n205:     }\n206:     cJSON_Delete(root);\n207: \n208:     /* Our \"gallery\" item: */\n209:     root = cJSON_CreateObject();\n210:     cJSON_AddItemToObject(root, \"Image\", img = cJSON_CreateObject());\n211:     cJSON_AddNumberToObject(img, \"Width\", 800);\n212:     cJSON_AddNumberToObject(img, \"Height\", 600);\n213:     cJSON_AddStringToObject(img, \"Title\", \"View from 15th Floor\");\n214:     cJSON_AddItemToObject(img, \"Thumbnail\", thm = cJSON_CreateObject());\n215:     cJSON_AddStringToObject(thm, \"Url\", \"http:/*www.example.com/image/481989943\");\n216:     cJSON_AddNumberToObject(thm, \"Height\", 125);\n217:     cJSON_AddStringToObject(thm, \"Width\", \"100\");\n218:     cJSON_AddItemToObject(img, \"IDs\", cJSON_CreateIntArray(ids, 4));\n219: \n220:     if (print_preallocated(root) != 0) {\n221:         cJSON_Delete(root);\n222:         exit(EXIT_FAILURE);\n223:     }\n224:     cJSON_Delete(root);\n225: \n226:     /* Our array of \"records\": */\n227:     root = cJSON_CreateArray();\n228:     for (i = 0; i < 2; i++)\n229:     {\n230:         cJSON_AddItemToArray(root, fld = cJSON_CreateObject());\n231:         cJSON_AddStringToObject(fld, \"precision\", fields[i].precision);\n232:         cJSON_AddNumberToObject(fld, \"Latitude\", fields[i].lat);\n233:         cJSON_AddNumberToObject(fld, \"Longitude\", fields[i].lon);\n234:         cJSON_AddStringToObject(fld, \"Address\", fields[i].address);\n235:         cJSON_AddStringToObject(fld, \"City\", fields[i].city);\n236:         cJSON_AddStringToObject(fld, \"State\", fields[i].state);\n237:         cJSON_AddStringToObject(fld, \"Zip\", fields[i].zip);\n238:         cJSON_AddStringToObject(fld, \"Country\", fields[i].country);\n239:     }\n240: \n241:     /* cJSON_ReplaceItemInObject(cJSON_GetArrayItem(root, 1), \"City\", cJSON_CreateIntArray(ids, 4)); */\n242: \n243:     if (print_preallocated(root) != 0) {\n244:         cJSON_Delete(root);\n245:         exit(EXIT_FAILURE);\n246:     }\n247:     cJSON_Delete(root);\n248: \n249:     root = cJSON_CreateObject();\n250:     cJSON_AddNumberToObject(root, \"number\", 1.0 / zero);\n251: ",
      "assertion_lines": [],
      "literal_samples": [
        "\"Failed to allocate memory.\\n\"",
        "\"US\"",
        "\"Video\"",
        "\"name\"",
        "\"Jack (\\\"Bee\\\") Nimble\"",
        "\"format\"",
        "\"type\"",
        "\"rect\"",
        "\"width\"",
        "\"height\"",
        "\"interlace\"",
        "\"frame rate\"",
        "\"days of the week\"",
        "\"Replacement\"",
        "\"gallery\"",
        "\"Image\"",
        "\"Width\"",
        "\"Height\"",
        "\"Title\"",
        "\"View from 15th Floor\"",
        "\"Thumbnail\"",
        "\"Url\"",
        "\"http:/*www.example.com/image/481989943\"",
        "\"100\"",
        "\"IDs\"",
        "\"records\"",
        "\"precision\"",
        "\"Latitude\""
      ]
    },
    {
      "path": "tests/json_patch_tests.c",
      "frameworks": [
        "unity"
      ],
      "test_cases": [
        {
          "framework": "unity",
          "name": "cjson_utils_should_pass_json_patch_test_tests"
        },
        {
          "framework": "unity",
          "name": "cjson_utils_should_pass_json_patch_test_spec_tests"
        },
        {
          "framework": "unity",
          "name": "cjson_utils_should_pass_json_patch_test_cjson_utils_tests"
        }
      ],
      "calls_aligned_public_functions": [
        "cJSON_GetObjectItemCaseSensitive",
        "cJSON_IsArray",
        "cJSON_IsString",
        "cJSON_Parse",
        "cJSON_Print"
      ],
      "snippet": "32: static cJSON *parse_test_file(const char * const filename)\n33: {\n34:     char *file = NULL;\n35:     cJSON *json = NULL;\n36: \n37:     file = read_file(filename);\n38:     TEST_ASSERT_NOT_NULL_MESSAGE(file, \"Failed to read file.\");\n39: \n40:     json = cJSON_Parse(file);\n41:     TEST_ASSERT_NOT_NULL_MESSAGE(json, \"Failed to parse test json.\");\n42:     TEST_ASSERT_TRUE_MESSAGE(cJSON_IsArray(json), \"Json is not an array.\");\n43: \n44:     free(file);\n45: \n46:     return json;\n47: }\n48: \n49: static cJSON_bool test_apply_patch(const cJSON * const test)\n50: {\n51:     cJSON *doc = NULL;\n52:     cJSON *patch = NULL;\n53:     cJSON *expected = NULL;\n54:     cJSON *error_element = NULL;\n55:     cJSON *comment = NULL;\n56:     cJSON *disabled = NULL;\n57: \n58:     cJSON *object = NULL;\n59:     cJSON_bool successful = false;\n60: \n61:     /* extract all the data out of the test */\n62:     comment = cJSON_GetObjectItemCaseSensitive(test, \"comment\");\n63:     if (cJSON_IsString(comment))\n64:     {\n65:         printf(\"Testing \\\"%s\\\"\\n\", comment->valuestring);\n66:     }\n67:     else\n68:     {\n69:         printf(\"Testing unknown\\n\");\n70:     }\n71: \n72:     disabled = cJSON_GetObjectItemCaseSensitive(test, \"disabled\");\n73:     if (cJSON_IsTrue(disabled))\n74:     {\n75:         printf(\"SKIPPED\\n\");\n76:         return true;\n77:     }\n78: \n79:     doc = cJSON_GetObjectItemCaseSensitive(test, \"doc\");\n80:     TEST_ASSERT_NOT_NULL_MESSAGE(doc, \"No \\\"doc\\\" in the test.\");\n81:     patch = cJSON_GetObjectItemCaseSensitive(test, \"patch\");\n82:     TEST_ASSERT_NOT_NULL_MESSAGE(patch, \"No \\\"patch\\\"in the test.\");\n83:     /* Make a working copy of 'doc' */\n84:     object = cJSON_Duplicate(doc, true);\n85:     TEST_ASSERT_NOT_NULL(object);\n86: \n87:     expected = cJSON_GetObjectItemCaseSensitive(test, \"expected\");\n88:     error_element = cJSON_GetObjectItemCaseSensitive(test, \"error\");\n89:     if (error_element != NULL)\n90:     {\n91:         /* excepting an error */\n92:         TEST_ASSERT_TRUE_MESSAGE(0 != cJSONUtils_ApplyPatchesCaseSensitive(object, patch), \"Test didn't fail as it's supposed to.\");\n93: \n94:         successful = true;\n95:     }\n96:     else\n97:     {\n98:         /* apply the patch */\n99:         TEST_ASSERT_EQUAL_INT_MESSAGE(0, cJSONUtils_ApplyPatchesCaseSensitive(object, patch), \"Failed to apply patches.\");\n100:         successful = true;\n101: \n...\n126:     cJSON *expected = NULL;\n127:     cJSON *disabled = NULL;\n128: \n129:     cJSON *object = NULL;\n130:     cJSON_bool successful = false;\n131: \n132:     char *printed_patch = NULL;\n133: \n134:     disabled = cJSON_GetObjectItemCaseSensitive(test, \"disabled\");\n135:     if (cJSON_IsTrue(disabled))\n136:     {\n137:         printf(\"SKIPPED\\n\");\n138:         return true;\n139:     }\n140: \n141:     doc = cJSON_GetObjectItemCaseSensitive(test, \"doc\");\n142:     TEST_ASSERT_NOT_NULL_MESSAGE(doc, \"No \\\"doc\\\" in the test.\");\n143: \n144:     /* Make a working copy of 'doc' */\n145:     object = cJSON_Duplicate(doc, true);\n146:     TEST_ASSERT_NOT_NULL(object);\n147: \n148:     expected = cJSON_GetObjectItemCaseSensitive(test, \"expected\");\n149:     if (expected == NULL)\n150:     {\n151:         cJSON_Delete(object);\n152:         /* if there is no expected output, this test doesn't make sense */\n153:         return true;\n154:     }\n155: \n156:     patch = cJSONUtils_GeneratePatchesCaseSensitive(doc, expected);\n157:     TEST_ASSERT_NOT_NULL_MESSAGE(patch, \"Failed to generate patches.\");\n158: \n159:     printed_patch = cJSON_Print(patch);\n160:     printf(\"%s\\n\", printed_patch);\n161:     free(printed_patch);\n162: \n163:     /* apply the generated patch */\n164:     TEST_ASSERT_EQUAL_INT_MESSAGE(0, cJSONUtils_ApplyPatchesCaseSensitive(object, patch), \"Failed to apply generated patch.\");\n165: \n166:     successful = cJSON_Compare(object, expected, true);\n167: \n168:     cJSON_Delete(patch);\n169:     cJSON_Delete(object);\n170: \n171:     if (successful)\n172:     {",
      "assertion_lines": [
        "38:     TEST_ASSERT_NOT_NULL_MESSAGE(file, \"Failed to read file.\");",
        "41:     TEST_ASSERT_NOT_NULL_MESSAGE(json, \"Failed to parse test json.\");",
        "42:     TEST_ASSERT_TRUE_MESSAGE(cJSON_IsArray(json), \"Json is not an array.\");",
        "80:     TEST_ASSERT_NOT_NULL_MESSAGE(doc, \"No \\\"doc\\\" in the test.\");",
        "82:     TEST_ASSERT_NOT_NULL_MESSAGE(patch, \"No \\\"patch\\\"in the test.\");",
        "85:     TEST_ASSERT_NOT_NULL(object);",
        "92:         TEST_ASSERT_TRUE_MESSAGE(0 != cJSONUtils_ApplyPatchesCaseSensitive(object, patch), \"Test didn't fail as it's supposed to.\");",
        "99:         TEST_ASSERT_EQUAL_INT_MESSAGE(0, cJSONUtils_ApplyPatchesCaseSensitive(object, patch), \"Failed to apply patches.\");",
        "142:     TEST_ASSERT_NOT_NULL_MESSAGE(doc, \"No \\\"doc\\\" in the test.\");",
        "146:     TEST_ASSERT_NOT_NULL(object);",
        "157:     TEST_ASSERT_NOT_NULL_MESSAGE(patch, \"Failed to generate patches.\");",
        "164:     TEST_ASSERT_EQUAL_INT_MESSAGE(0, cJSONUtils_ApplyPatchesCaseSensitive(object, patch), \"Failed to apply generated patch.\");"
      ],
      "literal_samples": [
        "\"Failed to read file.\"",
        "\"Failed to parse test json.\"",
        "\"Json is not an array.\"",
        "\"comment\"",
        "\"Testing \\\"%s\\\"\\n\"",
        "\"Testing unknown\\n\"",
        "\"disabled\"",
        "\"SKIPPED\\n\"",
        "\"doc\"",
        "\"No \\\"doc\\\" in the test.\"",
        "\"patch\"",
        "\"No \\\"patch\\\"in the test.\"",
        "\"expected\"",
        "\"error\"",
        "\"Test didn't fail as it's supposed to.\"",
        "\"Failed to apply patches.\"",
        "\"Failed to generate patches.\"",
        "\"%s\\n\"",
        "\"Failed to apply generated patch.\"",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "38",
        "39",
        "40"
      ]
    },
    {
      "path": "tests/old_utils_tests.c",
      "frameworks": [
        "unity"
      ],
      "test_cases": [
        {
          "framework": "unity",
          "name": "json_pointer_tests"
        },
        {
          "framework": "unity",
          "name": "misc_tests"
        },
        {
          "framework": "unity",
          "name": "sort_tests"
        },
        {
          "framework": "unity",
          "name": "merge_tests"
        },
        {
          "framework": "unity",
          "name": "generate_merge_tests"
        }
      ],
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_CreateObject",
        "cJSON_Parse",
        "cJSON_PrintUnformatted"
      ],
      "snippet": "61:         \"\\\"e^f\\\": 3,\"\n62:         \"\\\"g|h\\\": 4,\"\n63:         \"\\\"i\\\\\\\\j\\\": 5,\"\n64:         \"\\\"k\\\\\\\"l\\\": 6,\"\n65:         \"\\\" \\\": 7,\"\n66:         \"\\\"m~n\\\": 8\"\n67:         \"}\";\n68: \n69:     root = cJSON_Parse(json);\n70: \n71:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"\"), root);\n72:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo\"), cJSON_GetObjectItem(root, \"foo\"));\n73:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);\n74:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);\n75:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/\"), cJSON_GetObjectItem(root, \"\"));\n76:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/a~1b\"), cJSON_GetObjectItem(root, \"a/b\"));\n77:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c%d\"), cJSON_GetObjectItem(root, \"c%d\"));\n78:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c^f\"), cJSON_GetObjectItem(root, \"c^f\"));\n79:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c|f\"), cJSON_GetObjectItem(root, \"c|f\"));\n80:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/i\\\\j\"), cJSON_GetObjectItem(root, \"i\\\\j\"));\n81:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/k\\\"l\"), cJSON_GetObjectItem(root, \"k\\\"l\"));\n82:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/ \"), cJSON_GetObjectItem(root, \" \"));\n...\n94:     cJSON *object2 = NULL;\n95:     cJSON *object3 = NULL;\n96:     cJSON *object4 = NULL;\n97:     cJSON *nums = NULL;\n98:     cJSON *num6 = NULL;\n99:     char *pointer = NULL;\n100: \n101:     printf(\"JSON Pointer construct\\n\");\n102:     object = cJSON_CreateObject();\n103:     nums = cJSON_CreateIntArray(numbers, 10);\n104:     num6 = cJSON_GetArrayItem(nums, 6);\n105:     cJSON_AddItemToObject(object, \"numbers\", nums);\n106: \n107:     pointer = cJSONUtils_FindPointerFromObjectTo(object, num6);\n108:     TEST_ASSERT_EQUAL_STRING(\"/numbers/6\", pointer);\n109:     free(pointer);\n110: \n111:     pointer = cJSONUtils_FindPointerFromObjectTo(object, nums);\n112:     TEST_ASSERT_EQUAL_STRING(\"/numbers\", pointer);\n113:     free(pointer);\n114: \n115:     pointer = cJSONUtils_FindPointerFromObjectTo(object, object);\n116:     TEST_ASSERT_EQUAL_STRING(\"\", pointer);\n117:     free(pointer);\n118: \n119:     object1 = cJSON_CreateObject();\n120:     object2 = cJSON_CreateString(\"m~n\");\n121:     cJSON_AddItemToObject(object1, \"m~n\", object2);\n122:     pointer = cJSONUtils_FindPointerFromObjectTo(object1, object2);\n123:     TEST_ASSERT_EQUAL_STRING(\"/m~0n\",pointer);\n124:     free(pointer);\n125: \n126:     object3 = cJSON_CreateObject();\n127:     object4 = cJSON_CreateString(\"m/n\");\n128:     cJSON_AddItemToObject(object3, \"m/n\", object4);\n129:     pointer = cJSONUtils_FindPointerFromObjectTo(object3, object4);\n130:     TEST_ASSERT_EQUAL_STRING(\"/m~1n\",pointer);\n131:     free(pointer);\n132: \n133:     cJSON_Delete(object);\n134:     cJSON_Delete(object1);\n135:     cJSON_Delete(object3);\n136: }\n137: \n138: static void sort_tests(void)\n139: {\n140:     /* Misc tests */\n141:     const char *random = \"QWERTYUIOPASDFGHJKLZXCVBNM\";\n142:     char buf[2] = {'\\0', '\\0'};\n143:     cJSON *sortme = NULL;\n144:     size_t i = 0;\n145:     cJSON *current_element = NULL;\n146: \n147:     /* JSON Sort test: */\n148:     sortme = cJSON_CreateObject();\n149:     for (i = 0; i < 26; i++)\n150:     {\n151:         buf[0] = random[i];\n152:         cJSON_AddItemToObject(sortme, buf, cJSON_CreateNumber(1));\n153:     }\n154: \n155:     cJSONUtils_SortObject(sortme);\n156: \n157:     /* check sorting */\n158:     current_element = sortme->child->next;\n159:     for (i = 1; (i < 26) && (current_element != NULL) && (current_element->prev != NULL); i++)\n160:     {\n161:         TEST_ASSERT_TRUE(current_element->string[0] >= current_element->prev->string[0]);\n162:         current_element = current_element->next;\n163:     }\n164: \n165:     cJSON_Delete(sortme);\n...\n170:     size_t i = 0;\n171:     char *patchtext = NULL;\n172:     char *after = NULL;\n173: \n174:     /* Merge tests: */\n175:     printf(\"JSON Merge Patch tests\\n\");\n176:     for (i = 0; i < 15; i++)\n177:     {\n178:         cJSON *object_to",
      "assertion_lines": [
        "71:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"\"), root);",
        "72:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo\"), cJSON_GetObjectItem(root, \"foo\"));",
        "73:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);",
        "74:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);",
        "75:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/\"), cJSON_GetObjectItem(root, \"\"));",
        "76:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/a~1b\"), cJSON_GetObjectItem(root, \"a/b\"));",
        "77:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c%d\"), cJSON_GetObjectItem(root, \"c%d\"));",
        "78:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c^f\"), cJSON_GetObjectItem(root, \"c^f\"));",
        "79:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c|f\"), cJSON_GetObjectItem(root, \"c|f\"));",
        "80:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/i\\\\j\"), cJSON_GetObjectItem(root, \"i\\\\j\"));",
        "81:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/k\\\"l\"), cJSON_GetObjectItem(root, \"k\\\"l\"));",
        "82:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/ \"), cJSON_GetObjectItem(root, \" \"));",
        "108:     TEST_ASSERT_EQUAL_STRING(\"/numbers/6\", pointer);",
        "112:     TEST_ASSERT_EQUAL_STRING(\"/numbers\", pointer);",
        "116:     TEST_ASSERT_EQUAL_STRING(\"\", pointer);",
        "123:     TEST_ASSERT_EQUAL_STRING(\"/m~0n\",pointer);",
        "130:     TEST_ASSERT_EQUAL_STRING(\"/m~1n\",pointer);",
        "161:         TEST_ASSERT_TRUE(current_element->string[0] >= current_element->prev->string[0]);"
      ],
      "literal_samples": [
        "\"\\\"e^f\\\": 3,\"",
        "\"\\\"g|h\\\": 4,\"",
        "\"\\\"i\\\\\\\\j\\\": 5,\"",
        "\"\\\"k\\\\\\\"l\\\": 6,\"",
        "\"\\\" \\\": 7,\"",
        "\"\\\"m~n\\\": 8\"",
        "\"}\"",
        "\"\"",
        "\"/foo\"",
        "\"foo\"",
        "\"/foo/0\"",
        "\"/\"",
        "\"/a~1b\"",
        "\"a/b\"",
        "\"/c%d\"",
        "\"c%d\"",
        "\"/c^f\"",
        "\"c^f\"",
        "\"/c|f\"",
        "\"c|f\"",
        "\"/i\\\\j\"",
        "\"i\\\\j\"",
        "\"/k\\\"l\"",
        "\"k\\\"l\"",
        "\"/ \"",
        "\" \"",
        "\"JSON Pointer construct\\n\"",
        "\"numbers\""
      ]
    },
    {
      "path": "tests/parse_examples.c",
      "frameworks": [
        "unity"
      ],
      "test_cases": [
        {
          "framework": "unity",
          "name": "file_test1_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "file_test2_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "file_test3_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "file_test4_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "file_test5_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "file_test6_should_not_be_parsed"
        },
        {
          "framework": "unity",
          "name": "file_test7_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "file_test8_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "file_test9_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "file_test10_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "file_test11_should_be_parsed_and_printed"
        },
        {
          "framework": "unity",
          "name": "test12_should_not_be_parsed"
        },
        {
          "framework": "unity",
          "name": "test13_should_be_parsed_without_null_termination"
        },
        {
          "framework": "unity",
          "name": "test14_should_not_be_parsed"
        },
        {
          "framework": "unity",
          "name": "test15_should_not_heap_buffer_overflow"
        }
      ],
      "calls_aligned_public_functions": [
        "cJSON_Parse",
        "cJSON_Print"
      ],
      "snippet": "28: #include \"unity/src/unity.h\"\n29: #include \"common.h\"\n30: \n31: static cJSON *parse_file(const char *filename)\n32: {\n33:     cJSON *parsed = NULL;\n34:     char *content = read_file(filename);\n35: \n36:     parsed = cJSON_Parse(content);\n37: \n38:     if (content != NULL)\n39:     {\n40:         free(content);\n41:     }\n42: \n43:     return parsed;\n44: }\n45: \n46: static void do_test(const char *test_name)\n47: {\n48:     char *expected = NULL;\n49:     char *actual = NULL;\n...\n72:     expected = read_file(expected_path);\n73:     TEST_ASSERT_NOT_NULL_MESSAGE(expected, \"Failed to read expected output.\");\n74: \n75:     /* read and parse test */\n76:     tree = parse_file(test_path);\n77:     TEST_ASSERT_NOT_NULL_MESSAGE(tree, \"Failed to read of parse test.\");\n78: \n79:     /* print the parsed tree */\n80:     actual = cJSON_Print(tree);\n81:     TEST_ASSERT_NOT_NULL_MESSAGE(actual, \"Failed to print tree back to JSON.\");\n82: \n83: \n84:     TEST_ASSERT_EQUAL_STRING(expected, actual);\n85: \n86:     /* cleanup resources */\n87:     if (expected != NULL)\n88:     {\n89:         free(expected);\n90:     }\n91:     if (tree != NULL)\n92:     {\n93:         cJSON_Delete(tree);\n...\n134: static void file_test6_should_not_be_parsed(void)\n135: {\n136:     char *test6 = NULL;\n137:     cJSON *tree = NULL;\n138: \n139:     test6 = read_file(\"inputs/test6\");\n140:     TEST_ASSERT_NOT_NULL_MESSAGE(test6, \"Failed to read test6 data.\");\n141: \n142:     tree = cJSON_Parse(test6);\n143:     TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse what is not JSON.\");\n144: \n145:     TEST_ASSERT_EQUAL_PTR_MESSAGE(test6, cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");\n146: \n147:     if (test6 != NULL)\n148:     {\n149:         free(test6);\n150:     }\n151:     if (tree != NULL)\n152:     {\n153:         cJSON_Delete(tree);\n154:     }\n155: }\n...\n179:     do_test(\"test11\");\n180: }\n181: \n182: static void test12_should_not_be_parsed(void)\n183: {\n184:     const char *test12 = \"{ \\\"name\\\": \";\n185:     cJSON *tree = NULL;\n186: \n187:     tree = cJSON_Parse(test12);\n188:     TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse incomplete JSON.\");\n189: \n190:     TEST_ASSERT_EQUAL_PTR_MESSAGE(test12 + strlen(test12), cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");\n191: \n192:     if (tree != NULL)\n193:     {\n194:         cJSON_Delete(tree);\n195:     }\n196: }\n197: \n198: static void test13_should_be_parsed_without_null_termination(void)\n199: {\n200:     cJSON *tree = NULL;",
      "assertion_lines": [
        "73:     TEST_ASSERT_NOT_NULL_MESSAGE(expected, \"Failed to read expected output.\");",
        "77:     TEST_ASSERT_NOT_NULL_MESSAGE(tree, \"Failed to read of parse test.\");",
        "81:     TEST_ASSERT_NOT_NULL_MESSAGE(actual, \"Failed to print tree back to JSON.\");",
        "84:     TEST_ASSERT_EQUAL_STRING(expected, actual);",
        "140:     TEST_ASSERT_NOT_NULL_MESSAGE(test6, \"Failed to read test6 data.\");",
        "143:     TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse what is not JSON.\");",
        "145:     TEST_ASSERT_EQUAL_PTR_MESSAGE(test6, cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");",
        "188:     TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse incomplete JSON.\");",
        "190:     TEST_ASSERT_EQUAL_PTR_MESSAGE(test12 + strlen(test12), cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");"
      ],
      "literal_samples": [
        "\"unity/src/unity.h\"",
        "\"common.h\"",
        "\"Failed to read expected output.\"",
        "\"Failed to read of parse test.\"",
        "\"Failed to print tree back to JSON.\"",
        "\"inputs/test6\"",
        "\"Failed to read test6 data.\"",
        "\"Should fail to parse what is not JSON.\"",
        "\"Error pointer is incorrect.\"",
        "\"test11\"",
        "\"{ \\\"name\\\": \"",
        "\"Should fail to parse incomplete JSON.\"",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "38",
        "39",
        "40",
        "41",
        "42",
        "43"
      ]
    },
    {
      "path": "tests/compare_tests.c",
      "frameworks": [
        "unity"
      ],
      "test_cases": [
        {
          "framework": "unity",
          "name": "cjson_compare_should_compare_null_pointer_as_not_equal"
        },
        {
          "framework": "unity",
          "name": "cjson_compare_should_compare_invalid_as_not_equal"
        },
        {
          "framework": "unity",
          "name": "cjson_compare_should_compare_numbers"
        },
        {
          "framework": "unity",
          "name": "cjson_compare_should_compare_booleans"
        },
        {
          "framework": "unity",
          "name": "cjson_compare_should_compare_null"
        },
        {
          "framework": "unity",
          "name": "cjson_compare_should_not_accept_invalid_types"
        },
        {
          "framework": "unity",
          "name": "cjson_compare_should_compare_strings"
        },
        {
          "framework": "unity",
          "name": "cjson_compare_should_compare_raw"
        },
        {
          "framework": "unity",
          "name": "cjson_compare_should_compare_arrays"
        },
        {
          "framework": "unity",
          "name": "cjson_compare_should_compare_objects"
        }
      ],
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "snippet": "25: #include \"common.h\"\n26: \n27: static cJSON_bool compare_from_string(const char * const a, const char * const b, const cJSON_bool case_sensitive)\n28: {\n29:     cJSON *a_json = NULL;\n30:     cJSON *b_json = NULL;\n31:     cJSON_bool result = false;\n32: \n33:     a_json = cJSON_Parse(a);\n34:     TEST_ASSERT_NOT_NULL_MESSAGE(a_json, \"Failed to parse a.\");\n35:     b_json = cJSON_Parse(b);\n36:     TEST_ASSERT_NOT_NULL_MESSAGE(b_json, \"Failed to parse b.\");\n37: \n38:     result = cJSON_Compare(a_json, b_json, case_sensitive);\n39: \n40:     cJSON_Delete(a_json);\n41:     cJSON_Delete(b_json);\n42: \n43:     return result;\n44: }\n45: \n46: static void cjson_compare_should_compare_null_pointer_as_not_equal(void)\n47: {\n48:     TEST_ASSERT_FALSE(cJSON_Compare(NULL, NULL, true));\n...\n118:     TEST_ASSERT_FALSE(compare_from_string(\"\\\"ABCDEFG\\\"\", \"\\\"abcdefg\\\"\", false));\n119: }\n120: \n121: static void cjson_compare_should_compare_raw(void)\n122: {\n123:     cJSON *raw1 = NULL;\n124:     cJSON *raw2 = NULL;\n125: \n126:     raw1 = cJSON_Parse(\"\\\"[true, false]\\\"\");\n127:     TEST_ASSERT_NOT_NULL(raw1);\n128:     raw2 = cJSON_Parse(\"\\\"[true, false]\\\"\");\n129:     TEST_ASSERT_NOT_NULL(raw2);\n130: \n131:     raw1->type = cJSON_Raw;\n132:     raw2->type = cJSON_Raw;\n133: \n134:     TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, true));\n135:     TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, false));\n136: \n137:     cJSON_Delete(raw1);\n138:     cJSON_Delete(raw2);\n139: }\n140: \n141: static void cjson_compare_should_compare_arrays(void)",
      "assertion_lines": [
        "34:     TEST_ASSERT_NOT_NULL_MESSAGE(a_json, \"Failed to parse a.\");",
        "36:     TEST_ASSERT_NOT_NULL_MESSAGE(b_json, \"Failed to parse b.\");",
        "48:     TEST_ASSERT_FALSE(cJSON_Compare(NULL, NULL, true));",
        "118:     TEST_ASSERT_FALSE(compare_from_string(\"\\\"ABCDEFG\\\"\", \"\\\"abcdefg\\\"\", false));",
        "127:     TEST_ASSERT_NOT_NULL(raw1);",
        "129:     TEST_ASSERT_NOT_NULL(raw2);",
        "134:     TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, true));",
        "135:     TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, false));"
      ],
      "literal_samples": [
        "\"common.h\"",
        "\"Failed to parse a.\"",
        "\"Failed to parse b.\"",
        "\"\\\"ABCDEFG\\\"\"",
        "\"\\\"abcdefg\\\"\"",
        "\"\\\"[true, false]\\\"\"",
        "25",
        "26",
        "27",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "38",
        "39",
        "40",
        "41",
        "42",
        "43",
        "44",
        "45",
        "46"
      ]
    },
    {
      "path": "tests/parse_with_opts.c",
      "frameworks": [
        "unity"
      ],
      "test_cases": [
        {
          "framework": "unity",
          "name": "parse_with_opts_should_handle_null"
        },
        {
          "framework": "unity",
          "name": "parse_with_opts_should_handle_empty_strings"
        },
        {
          "framework": "unity",
          "name": "parse_with_opts_should_handle_incomplete_json"
        },
        {
          "framework": "unity",
          "name": "parse_with_opts_should_require_null_if_requested"
        },
        {
          "framework": "unity",
          "name": "parse_with_opts_should_return_parse_end"
        },
        {
          "framework": "unity",
          "name": "parse_with_opts_should_parse_utf8_bom"
        }
      ],
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "snippet": "23: #include \"unity/examples/unity_config.h\"\n24: #include \"unity/src/unity.h\"\n25: #include \"common.h\"\n26: \n27: static void parse_with_opts_should_handle_null(void)\n28: {\n29:     const char *error_pointer = NULL;\n30:     cJSON *item = NULL;\n31:     TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, &error_pointer, false), \"Failed to handle NULL input.\");\n32:     item = cJSON_ParseWithOpts(\"{}\", NULL, false);\n33:     TEST_ASSERT_NOT_NULL_MESSAGE(item, \"Failed to handle NULL error pointer.\");\n34:     cJSON_Delete(item);\n35:     TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, NULL, false), \"Failed to handle both NULL.\");\n36:     TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(\"{\", NULL, false), \"Failed to handle NULL error pointer with parse error.\");\n37: }\n38: \n39: static void parse_with_opts_should_handle_empty_strings(void)\n40: {\n41:     const char empty_string[] = \"\";\n42:     const char *error_pointer = NULL;\n43: \n44:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, NULL, false));\n45:     TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());\n46: \n47:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, &error_pointer, false));\n48:     TEST_ASSERT_EQUAL_PTR(empty_string, error_pointer);\n49:     TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());\n50: }\n51: \n52: static void parse_with_opts_should_handle_incomplete_json(void)\n53: {\n54:     const char json[] = \"{ \\\"name\\\": \";\n55:     const char *parse_end = NULL;\n56: \n57:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(json, &parse_end, false));\n58:     TEST_ASSERT_EQUAL_PTR(json + strlen(json), parse_end);\n59:     TEST_ASSERT_EQUAL_PTR(json + strlen(json), cJSON_GetErrorPtr());\n60: }\n61: \n62: static void parse_with_opts_should_require_null_if_requested(void)\n63: {\n64:     cJSON *item = cJSON_ParseWithOpts(\"{}\", NULL, true);\n65:     TEST_ASSERT_NOT_NULL(item);\n66:     cJSON_Delete(item);\n67:     item = cJSON_ParseWithOpts(\"{} \\n\", NULL, true);\n68:     TEST_ASSERT_NOT_NULL(item);\n69:     cJSON_Delete(item);\n70:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(\"{}x\", NULL, true));\n71: }\n72: \n73: static void parse_with_opts_should_return_parse_end(void)\n74: {\n75:     const char json[] = \"[] empty array XD\";\n76:     const char *parse_end = NULL;\n77: \n78:     cJSON *item = cJSON_ParseWithOpts(json, &parse_end, false);\n79:     TEST_ASSERT_NOT_NULL(item);\n80:     TEST_ASSERT_EQUAL_PTR(json + 2, parse_end);\n81:     cJSON_Delete(item);\n82: }\n83: \n84: static void parse_with_opts_should_parse_utf8_bom(void)\n85: {\n86:     cJSON *with_bom = NULL;\n87:     cJSON *without_bom = NULL;\n88: \n89:     with_bom = cJSON_ParseWithOpts(\"\\xEF\\xBB\\xBF{}\", NULL, true);\n90:     TEST_ASSERT_NOT_NULL(with_bom);\n91:     without_bom = cJSON_ParseWithOpts(\"{}\", NULL, true);\n92:     TEST_ASSERT_NOT_NULL(with_bom);\n93: \n94:     TEST_ASSERT_TRUE(cJSON_Compare(with_bom, without_bom, true));\n95: \n96:     cJSON_Delete(with_bom);\n97:     cJSON_Delete(without_bom);\n98: }\n99: \n100: int CJSON_CDECL main(void)\n101: {\n102:     UNITY_BEGIN();\n103: \n104:     RUN_TEST(parse_with_opts_should_handle_null);",
      "assertion_lines": [
        "31:     TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, &error_pointer, false), \"Failed to handle NULL input.\");",
        "33:     TEST_ASSERT_NOT_NULL_MESSAGE(item, \"Failed to handle NULL error pointer.\");",
        "35:     TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, NULL, false), \"Failed to handle both NULL.\");",
        "36:     TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(\"{\", NULL, false), \"Failed to handle NULL error pointer with parse error.\");",
        "44:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, NULL, false));",
        "45:     TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());",
        "47:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, &error_pointer, false));",
        "48:     TEST_ASSERT_EQUAL_PTR(empty_string, error_pointer);",
        "49:     TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());",
        "57:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(json, &parse_end, false));",
        "58:     TEST_ASSERT_EQUAL_PTR(json + strlen(json), parse_end);",
        "59:     TEST_ASSERT_EQUAL_PTR(json + strlen(json), cJSON_GetErrorPtr());",
        "65:     TEST_ASSERT_NOT_NULL(item);",
        "68:     TEST_ASSERT_NOT_NULL(item);",
        "70:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(\"{}x\", NULL, true));",
        "79:     TEST_ASSERT_NOT_NULL(item);",
        "80:     TEST_ASSERT_EQUAL_PTR(json + 2, parse_end);",
        "90:     TEST_ASSERT_NOT_NULL(with_bom);"
      ],
      "literal_samples": [
        "\"unity/examples/unity_config.h\"",
        "\"unity/src/unity.h\"",
        "\"common.h\"",
        "\"Failed to handle NULL input.\"",
        "\"{}\"",
        "\"Failed to handle NULL error pointer.\"",
        "\"Failed to handle both NULL.\"",
        "\"{\"",
        "\"Failed to handle NULL error pointer with parse error.\"",
        "\"\"",
        "\"{ \\\"name\\\": \"",
        "\"{} \\n\"",
        "\"{}x\"",
        "\"[] empty array XD\"",
        "\"\\xEF\\xBB\\xBF{}\"",
        "23",
        "24",
        "25",
        "26",
        "27",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35"
      ]
    }
  ],
  "source_test_case_evidence": [
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_set_bool_value_must_not_break_objects",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject",
        "cJSON_IsObject",
        "cJSON_IsString"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_TRUE((cJSON_SetBoolValue(refobj, 1) == cJSON_Invalid));",
        "TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));",
        "TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 1) == cJSON_True));",
        "TEST_ASSERT_TRUE(cJSON_IsTrue(bobj));",
        "TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 0) == cJSON_False));",
        "TEST_ASSERT_TRUE(cJSON_IsString(sobj));",
        "TEST_ASSERT_TRUE(cJSON_IsObject(oobj));",
        "TEST_ASSERT_TRUE(cJSON_IsString(refobj));",
        "TEST_ASSERT_TRUE(refobj->type & cJSON_IsReference);",
        "TEST_ASSERT_TRUE(cJSON_IsObject(refobj));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE((cJSON_SetBoolValue(refobj, 1) == cJSON_Invalid));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 1) == cJSON_True));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsTrue(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsTrue(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 0) == cJSON_False));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsString(sobj));",
          "mentions_aligned_functions": [
            "cJSON_IsString"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsString(sobj));",
          "mentions_aligned_functions": [
            "cJSON_IsString"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsString(sobj));",
          "mentions_aligned_functions": [
            "cJSON_IsString"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsObject(oobj));",
          "mentions_aligned_functions": [
            "cJSON_IsObject"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        }
      ],
      "literal_samples": [
        "\"test\"",
        "\"conststring\"",
        "1",
        "0"
      ],
      "body_excerpt": "1: {\n2:     cJSON *bobj, *sobj, *oobj, *refobj = NULL;\n3: \n4:     TEST_ASSERT_TRUE((cJSON_SetBoolValue(refobj, 1) == cJSON_Invalid));\n5: \n6:     bobj = cJSON_CreateFalse();\n7:     TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));\n8:     TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 1) == cJSON_True));\n9:     TEST_ASSERT_TRUE(cJSON_IsTrue(bobj));\n10:     cJSON_SetBoolValue(bobj, 1);\n11:     TEST_ASSERT_TRUE(cJSON_IsTrue(bobj));\n12:     TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 0) == cJSON_False));\n13:     TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));\n14:     cJSON_SetBoolValue(bobj, 0);\n15:     TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));\n16: \n17:     sobj = cJSON_CreateString(\"test\");\n18:     TEST_ASSERT_TRUE(cJSON_IsString(sobj));\n19:     cJSON_SetBoolValue(sobj, 1);\n20:     TEST_ASSERT_TRUE(cJSON_IsString(sobj));\n21:     cJSON_SetBoolValue(sobj, 0);\n22:     TEST_ASSERT_TRUE(cJSON_IsString(sobj));\n23: \n24:     oobj = cJSON_CreateObject();\n25:     TEST_ASSERT_TRUE(cJSON_IsObject(oobj));\n26:     cJSON_SetBoolValue(oobj, 1);\n27:     TEST_ASSERT_TRUE(cJSON_IsObject(oobj));\n28:     cJSON_SetBoolValue(oobj, 0);\n29:     TEST_ASSERT_TRUE(cJSON_IsObject(oobj));\n30: \n31:     refobj = cJSON_CreateStringReference(\"conststring\");\n32:     TEST_ASSERT_TRUE(cJSON_IsString(refobj));\n33:     TEST_ASSERT_TRUE(refobj->type & cJSON_IsReference);\n34:     cJSON_SetBoolValue(refobj, 1);\n35:     TEST_ASSERT_TRUE(cJSON_IsString(refobj));\n36:     TEST_ASSERT_TRUE(refobj->type & cJSON_IsReference);\n37:     cJSON_SetBoolValue(refobj, 0);\n38:     TEST_ASSERT_TRUE(cJSON_IsString(refobj));\n39:     TEST_ASSERT_TRUE(refobj->type & "
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_replace_item_via_pointer_should_replace_items",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToArray",
        "cJSON_CreateArray"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(beginning);",
        "TEST_ASSERT_NOT_NULL(middle);",
        "TEST_ASSERT_NOT_NULL(end);",
        "TEST_ASSERT_NOT_NULL(array);",
        "TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, beginning, &(replacements[0])));",
        "TEST_ASSERT_TRUE(replacements[0].prev == end);",
        "TEST_ASSERT_TRUE(replacements[0].next == middle);",
        "TEST_ASSERT_TRUE(middle->prev == &(replacements[0]));",
        "TEST_ASSERT_TRUE(array->child == &(replacements[0]));",
        "TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, middle, &(replacements[1])));",
        "TEST_ASSERT_TRUE(replacements[1].prev == &(replacements[0]));",
        "TEST_ASSERT_TRUE(replacements[1].next == end);",
        "TEST_ASSERT_TRUE(end->prev == &(replacements[1]));",
        "TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, end, &(replacements[2])));",
        "TEST_ASSERT_TRUE(replacements[2].prev == &(replacements[1]));",
        "TEST_ASSERT_NULL(replacements[2].next);",
        "TEST_ASSERT_TRUE(replacements[1].next == &(replacements[2]));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(beginning);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(middle);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(end);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(array);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, beginning, &(replacements[0])));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(replacements[0].prev == end);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(replacements[0].next == middle);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(middle->prev == &(replacements[0]));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(array->child == &(replacements[0]));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, middle, &(replacements[1])));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(replacements[1].prev == &(replacements[0]));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1",
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(replacements[1].next == end);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "truth_oracle"
        }
      ],
      "literal_samples": [
        "3",
        "0",
        "1",
        "2"
      ],
      "body_excerpt": "1: {\n2:     cJSON replacements[3];\n3:     cJSON *beginning = NULL;\n4:     cJSON *middle = NULL;\n5:     cJSON *end = NULL;\n6:     cJSON *array = NULL;\n7: \n8:     beginning = cJSON_CreateNull();\n9:     TEST_ASSERT_NOT_NULL(beginning);\n10:     middle = cJSON_CreateNull();\n11:     TEST_ASSERT_NOT_NULL(middle);\n12:     end = cJSON_CreateNull();\n13:     TEST_ASSERT_NOT_NULL(end);\n14: \n15:     array = cJSON_CreateArray();\n16:     TEST_ASSERT_NOT_NULL(array);\n17: \n18:     cJSON_AddItemToArray(array, beginning);\n19:     cJSON_AddItemToArray(array, middle);\n20:     cJSON_AddItemToArray(array, end);\n21: \n22:     memset(replacements, '\\0', sizeof(replacements));\n23: \n24:     /* replace beginning */\n25:     TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, beginning, &(replacements[0])));\n26:     TEST_ASSERT_TRUE(replacements[0].prev == end);\n27:     TEST_ASSERT_TRUE(replacements[0].next == middle);\n28:     TEST_ASSERT_TRUE(middle->prev == &(replacements[0]));\n29:     TEST_ASSERT_TRUE(array->child == &(replacements[0]));\n30: \n31:     /* replace middle */\n32:     TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, middle, &(replacements[1])));\n33:     TEST_ASSERT_TRUE(replacements[1].prev == &(replacements[0]));\n34:     TEST_ASSERT_TRUE(replacements[1].next == end);\n35:     TEST_ASSERT_TRUE(end->prev == &(replacements[1]));\n36: \n37:     /* replace end */\n38:     TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, end, &(replacements[2])));\n39:     TEST_ASSERT_TRUE(replacements[2].prev == &(replacements[1]));\n40:     TEST_ASSERT_NULL(replacements[2].next);\n41:     TEST_ASSERT_TRUE(repla"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_get_object_item_case_sensitive_should_get_object_items",
      "calls_aligned_public_functions": [
        "cJSON_GetObjectItemCaseSensitive",
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");",
        "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");",
        "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
        "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);",
        "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);",
        "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");",
        "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);",
        "TEST_ASSERT_NULL_MESSAGE(found, \"Should not find something that isn't there.\");"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to fail on NULL pointer.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to fail on NULL string.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find first item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find first item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "3"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Should not find something that isn't there.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Should not find something that isn't there.\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"{\\\"one\\\":1, \\\"Two\\\":2, \\\"tHree\\\":3}\"",
        "\"test\"",
        "\"Failed to fail on NULL pointer.\"",
        "\"Failed to fail on NULL string.\"",
        "\"one\"",
        "\"Failed to find first item.\"",
        "\"Two\"",
        "\"tHree\"",
        "\"Failed to find item.\"",
        "\"One\"",
        "\"Should not find something that isn't there.\"",
        "1",
        "2",
        "3"
      ],
      "body_excerpt": "1: {\n2:     cJSON *item = NULL;\n3:     cJSON *found = NULL;\n4: \n5:     item = cJSON_Parse(\"{\\\"one\\\":1, \\\"Two\\\":2, \\\"tHree\\\":3}\");\n6: \n7:     found = cJSON_GetObjectItemCaseSensitive(NULL, \"test\");\n8:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");\n9: \n10:     found = cJSON_GetObjectItemCaseSensitive(item, NULL);\n11:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");\n12: \n13:     found = cJSON_GetObjectItemCaseSensitive(item, \"one\");\n14:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");\n15:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);\n16: \n17:     found = cJSON_GetObjectItemCaseSensitive(item, \"Two\");\n18:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");\n19:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);\n20: \n21:     found = cJSON_GetObjectItemCaseSensitive(item, \"tHree\");\n22:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");\n23:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);\n24: \n25:     found = cJSON_GetObjectItemCaseSensitive(item, \"One\");\n26:     TEST_ASSERT_NULL_MESSAGE(found, \"Should not find something that isn't there.\");\n27: \n28:     cJSON_Delete(item);\n29: }"
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "name": "misc_tests",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_EQUAL_STRING(\"/numbers/6\", pointer);",
        "TEST_ASSERT_EQUAL_STRING(\"/numbers\", pointer);",
        "TEST_ASSERT_EQUAL_STRING(\"\", pointer);",
        "TEST_ASSERT_EQUAL_STRING(\"/m~0n\",pointer);",
        "TEST_ASSERT_EQUAL_STRING(\"/m~1n\",pointer);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"/numbers/6\", pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/numbers/6\"",
            "6"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"/numbers\", pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/numbers\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"\", pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"/m~0n\",pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/m~0n\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"/m~1n\",pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/m~1n\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"JSON Pointer construct\\n\"",
        "\"numbers\"",
        "\"/numbers/6\"",
        "\"/numbers\"",
        "\"\"",
        "\"m~n\"",
        "\"/m~0n\"",
        "\"m/n\"",
        "\"/m~1n\"",
        "10",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9"
      ],
      "body_excerpt": "1: {\n2:     /* Misc tests */\n3:     int numbers[10] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};\n4:     cJSON *object = NULL;\n5:     cJSON *object1 = NULL;\n6:     cJSON *object2 = NULL;\n7:     cJSON *object3 = NULL;\n8:     cJSON *object4 = NULL;\n9:     cJSON *nums = NULL;\n10:     cJSON *num6 = NULL;\n11:     char *pointer = NULL;\n12: \n13:     printf(\"JSON Pointer construct\\n\");\n14:     object = cJSON_CreateObject();\n15:     nums = cJSON_CreateIntArray(numbers, 10);\n16:     num6 = cJSON_GetArrayItem(nums, 6);\n17:     cJSON_AddItemToObject(object, \"numbers\", nums);\n18: \n19:     pointer = cJSONUtils_FindPointerFromObjectTo(object, num6);\n20:     TEST_ASSERT_EQUAL_STRING(\"/numbers/6\", pointer);\n21:     free(pointer);\n22: \n23:     pointer = cJSONUtils_FindPointerFromObjectTo(object, nums);\n24:     TEST_ASSERT_EQUAL_STRING(\"/numbers\", pointer);\n25:     free(pointer);\n26: \n27:     pointer = cJSONUtils_FindPointerFromObjectTo(object, object);\n28:     TEST_ASSERT_EQUAL_STRING(\"\", pointer);\n29:     free(pointer);\n30: \n31:     object1 = cJSON_CreateObject();\n32:     object2 = cJSON_CreateString(\"m~n\");\n33:     cJSON_AddItemToObject(object1, \"m~n\", object2);\n34:     pointer = cJSONUtils_FindPointerFromObjectTo(object1, object2);\n35:     TEST_ASSERT_EQUAL_STRING(\"/m~0n\",pointer);\n36:     free(pointer);\n37: \n38:     object3 = cJSON_CreateObject();\n39:     object4 = cJSON_CreateString(\"m/n\");\n40:     cJSON_AddItemToObject(object3, \"m/n\", object4);\n41:     pointer = cJSONUtils_FindPointerFromObjectTo(object3, object4);\n42:     TEST_ASSERT_EQUAL_STRING(\"/m~1n\",pointer);\n43:     free(pointer);\n44: \n45: "
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_replace_item_in_object_should_preserve_name",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_ReplaceItemInObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(child);",
        "TEST_ASSERT_NOT_NULL(replacement);",
        "TEST_ASSERT_TRUE_MESSAGE(flag, \"add item to object failed\");",
        "TEST_ASSERT_TRUE(root->child == replacement);",
        "TEST_ASSERT_EQUAL_STRING(\"child\", replacement->string);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(child);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(replacement);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE_MESSAGE",
          "expression": "TEST_ASSERT_TRUE_MESSAGE(flag, \"add item to object failed\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"add item to object failed\""
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(root->child == replacement);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"child\", replacement->string);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"child\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"child\"",
        "\"add item to object failed\"",
        "1",
        "0",
        "2"
      ],
      "body_excerpt": "1: {\n2:     cJSON root[1] = {{NULL, NULL, NULL, 0, NULL, 0, 0, NULL}};\n3:     cJSON *child = NULL;\n4:     cJSON *replacement = NULL;\n5:     cJSON_bool flag = false;\n6: \n7:     child = cJSON_CreateNumber(1);\n8:     TEST_ASSERT_NOT_NULL(child);\n9:     replacement = cJSON_CreateNumber(2);\n10:     TEST_ASSERT_NOT_NULL(replacement);\n11: \n12:     flag = cJSON_AddItemToObject(root, \"child\", child);\n13:     TEST_ASSERT_TRUE_MESSAGE(flag, \"add item to object failed\");\n14:     cJSON_ReplaceItemInObject(root, \"child\", replacement);\n15: \n16:     TEST_ASSERT_TRUE(root->child == replacement);\n17:     TEST_ASSERT_EQUAL_STRING(\"child\", replacement->string);\n18: \n19:     cJSON_Delete(replacement);\n20: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_bool_should_add_bool",
      "calls_aligned_public_functions": [
        "cJSON_AddBoolToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));",
        "TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);",
        "TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));",
        "TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"true\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"true\"",
        "\"false\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3:     cJSON *true_item = NULL;\n4:     cJSON *false_item = NULL;\n5: \n6:     /* true */\n7:     cJSON_AddBoolToObject(root, \"true\", true);\n8:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));\n9:     TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);\n10: \n11:     /* false */\n12:     cJSON_AddBoolToObject(root, \"false\", false);\n13:     TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));\n14:     TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);\n15: \n16:     cJSON_Delete(root);\n17: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_number_should_add_number",
      "calls_aligned_public_functions": [
        "cJSON_AddNumberToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(number = cJSON_GetObjectItemCaseSensitive(root, \"number\"));",
        "TEST_ASSERT_EQUAL_INT(number->type, cJSON_Number);",
        "TEST_ASSERT_EQUAL_DOUBLE(number->valuedouble, 42);",
        "TEST_ASSERT_EQUAL_INT(number->valueint, 42);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(number = cJSON_GetObjectItemCaseSensitive(root, \"number\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"number\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(number->type, cJSON_Number);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(number->valuedouble, 42);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "42"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(number->valueint, 42);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "42"
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"number\"",
        "42"
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3:     cJSON *number = NULL;\n4: \n5:     cJSON_AddNumberToObject(root, \"number\", 42);\n6: \n7:     TEST_ASSERT_NOT_NULL(number = cJSON_GetObjectItemCaseSensitive(root, \"number\"));\n8: \n9:     TEST_ASSERT_EQUAL_INT(number->type, cJSON_Number);\n10:     TEST_ASSERT_EQUAL_DOUBLE(number->valuedouble, 42);\n11:     TEST_ASSERT_EQUAL_INT(number->valueint, 42);\n12: \n13:     cJSON_Delete(root);\n14: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_set_valuestring_to_object_should_not_leak_memory",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_CreateObject",
        "cJSON_IsObject",
        "cJSON_IsString",
        "cJSON_Parse"
      ],
      "case_complexity": "moderate",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(return_value);",
        "TEST_ASSERT_EQUAL_PTR_MESSAGE(ptr1, return_value, \"new valuestring shorter than old should not reallocate memory\");",
        "TEST_ASSERT_EQUAL_STRING(short_valuestring, cJSON_GetObjectItem(root, \"one\")->valuestring);",
        "TEST_ASSERT_NOT_EQUAL_MESSAGE(ptr1, return_value, \"new valuestring longer than old should reallocate memory\")",
        "TEST_ASSERT_EQUAL_STRING(long_valuestring, cJSON_GetObjectItem(root, \"one\")->valuestring);",
        "TEST_ASSERT_NULL_MESSAGE(return_value, \"valuestring of reference object should not be changed\");",
        "TEST_ASSERT_EQUAL_STRING(reference_valuestring, cJSON_GetObjectItem(root, \"two\")->valuestring);",
        "TEST_ASSERT_TRUE((cJSON_SetBoolValue(refobj, 1) == cJSON_Invalid));",
        "TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));",
        "TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 1) == cJSON_True));",
        "TEST_ASSERT_TRUE(cJSON_IsTrue(bobj));",
        "TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 0) == cJSON_False));",
        "TEST_ASSERT_TRUE(cJSON_IsString(sobj));",
        "TEST_ASSERT_TRUE(cJSON_IsObject(oobj));",
        "TEST_ASSERT_TRUE(cJSON_IsString(refobj));",
        "TEST_ASSERT_TRUE(refobj->type & cJSON_IsReference);",
        "TEST_ASSERT_TRUE(cJSON_IsObject(refobj));",
        "TEST_ASSERT_NOT_NULL(valid_big_number_json_object1);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(return_value);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR_MESSAGE",
          "expression": "TEST_ASSERT_EQUAL_PTR_MESSAGE(ptr1, return_value, \"new valuestring shorter than old should not reallocate memory\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"new valuestring shorter than old should not reallocate memory\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(short_valuestring, cJSON_GetObjectItem(root, \"one\")->valuestring);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"one\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(return_value);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_EQUAL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_EQUAL_MESSAGE(ptr1, return_value, \"new valuestring longer than old should reallocate memory\")",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"new valuestring longer than old should reallocate memory\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(long_valuestring, cJSON_GetObjectItem(root, \"one\")->valuestring);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"one\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(return_value, \"valuestring of reference object should not be changed\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"valuestring of reference object should not be changed\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(reference_",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"{}\"",
        "\"valuestring could be changed safely\"",
        "\"reference item should be freed by yourself\"",
        "\"shorter valuestring\"",
        "\"new valuestring which much longer than previous should be changed safely\"",
        "\"one\"",
        "\"two\"",
        "\"new valuestring shorter than old should not reallocate memory\"",
        "\"new valuestring longer than old should reallocate memory\"",
        "\"valuestring of reference object should not be changed\"",
        "\"test\"",
        "\"conststring\"",
        "\"{\\\"a\\\": true, \\\"b\\\": [ null,9999999999999999999999999999999999999999999999912345678901234567]}\"",
        "\"{\\\"a\\\": true, \\\"b\\\": [ null,999999999999999999999999999999999999999999999991234567890.1234567E3]}\"",
        "\"{\\\"a\\\": true, \\\"b\\\": [ null,99999999999999999999999999999999999999999999999.1234567890.1234567]}\"",
        "\"{\\\"a\\\": true, \\\"b\\\": [ null,99999999999999999999999999999999999999999999999E1234567890e1234567]}\"",
        "\"Invalid big number JSONs should not be parsed.\"",
        "1",
        "0",
        "9999999999999999999999999999999999999999999999912345678901234567",
        "999999999999999999999999999999999999999999999991234567890.123456",
        "99999999999999999999999999999999999999999999999.1234567890",
        "1234567",
        "9999999999999999999999999999999999999999999999",
        "23456789",
        "234567"
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_Parse(\"{}\");\n3:     const char *stringvalue = \"valuestring could be changed safely\";\n4:     const char *reference_valuestring = \"reference item should be freed by yourself\";\n5:     const char *short_valuestring = \"shorter valuestring\";\n6:     const char *long_valuestring = \"new valuestring which much longer than previous should be changed safely\";\n7:     cJSON *item1 = cJSON_CreateString(stringvalue);\n8:     cJSON *item2 = cJSON_CreateStringReference(reference_valuestring);\n9:     char *ptr1 = NULL;\n10:     char *return_value = NULL;\n11: \n12:     cJSON_AddItemToObject(root, \"one\", item1);\n13:     cJSON_AddItemToObject(root, \"two\", item2);\n14: \n15:     ptr1 = item1->valuestring;\n16:     return_value = cJSON_SetValuestring(cJSON_GetObjectItem(root, \"one\"), short_valuestring);\n17:     TEST_ASSERT_NOT_NULL(return_value);\n18:     TEST_ASSERT_EQUAL_PTR_MESSAGE(ptr1, return_value, \"new valuestring shorter than old should not reallocate memory\");\n19:     TEST_ASSERT_EQUAL_STRING(short_valuestring, cJSON_GetObjectItem(root, \"one\")->valuestring);\n20: \n21:     /* we needn't to free the original valuestring manually */\n22:     ptr1 = item1->valuestring;\n23:     return_value = cJSON_SetValuestring(cJSON_GetObjectItem(root, \"one\"), long_valuestring);\n24:     TEST_ASSERT_NOT_NULL(return_value);\n25:     TEST_ASSERT_NOT_EQUAL_MESSAGE(ptr1, return_value, \"new valuestring longer than old should reallocate memory\")\n26:     TEST_ASSERT_EQUAL_STRING(long_valuestring, cJSON_GetObjectItem(root, \"one\")->valuestring);\n27: \n28:     return_value = cJSON_SetValuestring(c"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "typecheck_functions_should_check_type",
      "calls_aligned_public_functions": [
        "cJSON_IsArray",
        "cJSON_IsBool",
        "cJSON_IsNull",
        "cJSON_IsNumber",
        "cJSON_IsObject",
        "cJSON_IsString"
      ],
      "case_complexity": "moderate",
      "assertion_lines": [
        "TEST_ASSERT_FALSE(cJSON_IsInvalid(NULL));",
        "TEST_ASSERT_FALSE(cJSON_IsInvalid(item));",
        "TEST_ASSERT_TRUE(cJSON_IsInvalid(invalid));",
        "TEST_ASSERT_FALSE(cJSON_IsFalse(NULL));",
        "TEST_ASSERT_FALSE(cJSON_IsFalse(invalid));",
        "TEST_ASSERT_TRUE(cJSON_IsFalse(item));",
        "TEST_ASSERT_TRUE(cJSON_IsBool(item));",
        "TEST_ASSERT_FALSE(cJSON_IsTrue(NULL));",
        "TEST_ASSERT_FALSE(cJSON_IsTrue(invalid));",
        "TEST_ASSERT_TRUE(cJSON_IsTrue(item));",
        "TEST_ASSERT_FALSE(cJSON_IsNull(NULL));",
        "TEST_ASSERT_FALSE(cJSON_IsNull(invalid));",
        "TEST_ASSERT_TRUE(cJSON_IsNull(item));",
        "TEST_ASSERT_FALSE(cJSON_IsNumber(NULL));",
        "TEST_ASSERT_FALSE(cJSON_IsNumber(invalid));",
        "TEST_ASSERT_TRUE(cJSON_IsNumber(item));",
        "TEST_ASSERT_FALSE(cJSON_IsString(NULL));",
        "TEST_ASSERT_FALSE(cJSON_IsString(invalid));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsInvalid(NULL));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsInvalid(item));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsInvalid(invalid));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsFalse(NULL));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsFalse(invalid));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsFalse(item));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsBool(item));",
          "mentions_aligned_functions": [
            "cJSON_IsBool"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsTrue(NULL));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsTrue(invalid));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsTrue(item));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsBool(item));",
          "mentions_aligned_functions": [
            "cJSON_IsBool"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsNull(NULL));",
          "mentions_aligned_functions": [
            "cJSON_IsNull"
          ],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        }
      ],
      "literal_samples": [
        "1"
      ],
      "body_excerpt": "1: {\n2:     cJSON invalid[1];\n3:     cJSON item[1];\n4:     invalid->type = cJSON_Invalid;\n5:     invalid->type |= cJSON_StringIsConst;\n6:     item->type = cJSON_False;\n7:     item->type |= cJSON_StringIsConst;\n8: \n9:     TEST_ASSERT_FALSE(cJSON_IsInvalid(NULL));\n10:     TEST_ASSERT_FALSE(cJSON_IsInvalid(item));\n11:     TEST_ASSERT_TRUE(cJSON_IsInvalid(invalid));\n12: \n13:     item->type = cJSON_False | cJSON_StringIsConst;\n14:     TEST_ASSERT_FALSE(cJSON_IsFalse(NULL));\n15:     TEST_ASSERT_FALSE(cJSON_IsFalse(invalid));\n16:     TEST_ASSERT_TRUE(cJSON_IsFalse(item));\n17:     TEST_ASSERT_TRUE(cJSON_IsBool(item));\n18: \n19:     item->type = cJSON_True | cJSON_StringIsConst;\n20:     TEST_ASSERT_FALSE(cJSON_IsTrue(NULL));\n21:     TEST_ASSERT_FALSE(cJSON_IsTrue(invalid));\n22:     TEST_ASSERT_TRUE(cJSON_IsTrue(item));\n23:     TEST_ASSERT_TRUE(cJSON_IsBool(item));\n24: \n25:     item->type = cJSON_NULL | cJSON_StringIsConst;\n26:     TEST_ASSERT_FALSE(cJSON_IsNull(NULL));\n27:     TEST_ASSERT_FALSE(cJSON_IsNull(invalid));\n28:     TEST_ASSERT_TRUE(cJSON_IsNull(item));\n29: \n30:     item->type = cJSON_Number | cJSON_StringIsConst;\n31:     TEST_ASSERT_FALSE(cJSON_IsNumber(NULL));\n32:     TEST_ASSERT_FALSE(cJSON_IsNumber(invalid));\n33:     TEST_ASSERT_TRUE(cJSON_IsNumber(item));\n34: \n35:     item->type = cJSON_String | cJSON_StringIsConst;\n36:     TEST_ASSERT_FALSE(cJSON_IsString(NULL));\n37:     TEST_ASSERT_FALSE(cJSON_IsString(invalid));\n38:     TEST_ASSERT_TRUE(cJSON_IsString(item));\n39: \n40:     item->type = cJSON_Array | cJSON_StringIsConst;\n41:     TEST_ASSERT_FALSE(cJSON_IsArray(NULL));"
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "name": "json_pointer_tests",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"\"), root);",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo\"), cJSON_GetObjectItem(root, \"foo\"));",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/\"), cJSON_GetObjectItem(root, \"\"));",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/a~1b\"), cJSON_GetObjectItem(root, \"a/b\"));",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c%d\"), cJSON_GetObjectItem(root, \"c%d\"));",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c^f\"), cJSON_GetObjectItem(root, \"c^f\"));",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c|f\"), cJSON_GetObjectItem(root, \"c|f\"));",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/i\\\\j\"), cJSON_GetObjectItem(root, \"i\\\\j\"));",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/k\\\"l\"), cJSON_GetObjectItem(root, \"k\\\"l\"));",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/ \"), cJSON_GetObjectItem(root, \" \"));",
        "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/m~0n\"), cJSON_GetObjectItem(root, \"m~n\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"\"), root);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo\"), cJSON_GetObjectItem(root, \"foo\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/foo\"",
            "\"foo\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/foo/0\"",
            "\"foo\"",
            "0"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/foo/0\"",
            "\"foo\"",
            "0"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/\"), cJSON_GetObjectItem(root, \"\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/\"",
            "\"\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/a~1b\"), cJSON_GetObjectItem(root, \"a/b\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/a~1b\"",
            "\"a/b\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c%d\"), cJSON_GetObjectItem(root, \"c%d\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/c%d\"",
            "\"c%d\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c^f\"), cJSON_GetObjectItem(root, \"c^f\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/c^f\"",
            "\"c^f\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c|f\"), cJSON_GetObjectItem(root, \"c|f\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/c|f\"",
            "\"c|f\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/i\\\\j\"), cJSON_GetObjectItem(root, \"i\\\\j\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/i\\\\j\"",
            "\"i\\\\j\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/k\\\"l\"), cJSON_GetObjectItem(root, \"k\\\"l\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/k\\\"l\"",
            "\"k\\\"l\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/ \"), cJSON_GetObjectItem(root, \" \"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/ \"",
            "\" \""
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"{\"",
        "\"\\\"foo\\\": [\\\"bar\\\", \\\"baz\\\"],\"",
        "\"\\\"\\\": 0,\"",
        "\"\\\"a/b\\\": 1,\"",
        "\"\\\"c%d\\\": 2,\"",
        "\"\\\"e^f\\\": 3,\"",
        "\"\\\"g|h\\\": 4,\"",
        "\"\\\"i\\\\\\\\j\\\": 5,\"",
        "\"\\\"k\\\\\\\"l\\\": 6,\"",
        "\"\\\" \\\": 7,\"",
        "\"\\\"m~n\\\": 8\"",
        "\"}\"",
        "\"\"",
        "\"/foo\"",
        "\"foo\"",
        "\"/foo/0\"",
        "\"/\"",
        "\"/a~1b\"",
        "\"a/b\"",
        "\"/c%d\"",
        "\"c%d\"",
        "\"/c^f\"",
        "\"c^f\"",
        "\"/c|f\"",
        "\"c|f\"",
        "\"/i\\\\j\"",
        "\"i\\\\j\"",
        "\"/k\\\"l\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = NULL;\n3:     const char *json=\n4:         \"{\"\n5:         \"\\\"foo\\\": [\\\"bar\\\", \\\"baz\\\"],\"\n6:         \"\\\"\\\": 0,\"\n7:         \"\\\"a/b\\\": 1,\"\n8:         \"\\\"c%d\\\": 2,\"\n9:         \"\\\"e^f\\\": 3,\"\n10:         \"\\\"g|h\\\": 4,\"\n11:         \"\\\"i\\\\\\\\j\\\": 5,\"\n12:         \"\\\"k\\\\\\\"l\\\": 6,\"\n13:         \"\\\" \\\": 7,\"\n14:         \"\\\"m~n\\\": 8\"\n15:         \"}\";\n16: \n17:     root = cJSON_Parse(json);\n18: \n19:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"\"), root);\n20:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo\"), cJSON_GetObjectItem(root, \"foo\"));\n21:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);\n22:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);\n23:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/\"), cJSON_GetObjectItem(root, \"\"));\n24:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/a~1b\"), cJSON_GetObjectItem(root, \"a/b\"));\n25:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c%d\"), cJSON_GetObjectItem(root, \"c%d\"));\n26:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c^f\"), cJSON_GetObjectItem(root, \"c^f\"));\n27:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c|f\"), cJSON_GetObjectItem(root, \"c|f\"));\n28:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/i\\\\j\"), cJSON_GetObjectItem(root, \"i\\\\j\"));\n29:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/k\\\"l\"), cJSON_GetObjectItem(root, \"k\\\"l\"));\n30:     TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/ \"), cJSON_GetObjectItem(roo"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_get_object_item_should_get_object_items",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");",
        "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");",
        "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
        "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);",
        "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);",
        "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");",
        "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);",
        "TEST_ASSERT_NULL_MESSAGE(found, \"Should not find something that isn't there.\");"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to fail on NULL pointer.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to fail on NULL string.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find first item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find first item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "3"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Should not find something that isn't there.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Should not find something that isn't there.\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"{\\\"one\\\":1, \\\"Two\\\":2, \\\"tHree\\\":3}\"",
        "\"test\"",
        "\"Failed to fail on NULL pointer.\"",
        "\"Failed to fail on NULL string.\"",
        "\"one\"",
        "\"Failed to find first item.\"",
        "\"tWo\"",
        "\"three\"",
        "\"Failed to find item.\"",
        "\"four\"",
        "\"Should not find something that isn't there.\"",
        "1",
        "2",
        "3"
      ],
      "body_excerpt": "1: {\n2:     cJSON *item = NULL;\n3:     cJSON *found = NULL;\n4: \n5:     item = cJSON_Parse(\"{\\\"one\\\":1, \\\"Two\\\":2, \\\"tHree\\\":3}\");\n6: \n7:     found = cJSON_GetObjectItem(NULL, \"test\");\n8:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");\n9: \n10:     found = cJSON_GetObjectItem(item, NULL);\n11:     TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");\n12: \n13:     found = cJSON_GetObjectItem(item, \"one\");\n14:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");\n15:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);\n16: \n17:     found = cJSON_GetObjectItem(item, \"tWo\");\n18:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");\n19:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);\n20: \n21:     found = cJSON_GetObjectItem(item, \"three\");\n22:     TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");\n23:     TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);\n24: \n25:     found = cJSON_GetObjectItem(item, \"four\");\n26:     TEST_ASSERT_NULL_MESSAGE(found, \"Should not find something that isn't there.\");\n27: \n28:     cJSON_Delete(item);\n29: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_string_should_add_string",
      "calls_aligned_public_functions": [
        "cJSON_AddStringToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(string = cJSON_GetObjectItemCaseSensitive(root, \"string\"));",
        "TEST_ASSERT_EQUAL_INT(string->type, cJSON_String);",
        "TEST_ASSERT_EQUAL_STRING(string->valuestring, \"Hello World!\");"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(string = cJSON_GetObjectItemCaseSensitive(root, \"string\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"string\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(string->type, cJSON_String);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(string->valuestring, \"Hello World!\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Hello World!\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"string\"",
        "\"Hello World!\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3:     cJSON *string = NULL;\n4: \n5:     cJSON_AddStringToObject(root, \"string\", \"Hello World!\");\n6: \n7:     TEST_ASSERT_NOT_NULL(string = cJSON_GetObjectItemCaseSensitive(root, \"string\"));\n8:     TEST_ASSERT_EQUAL_INT(string->type, cJSON_String);\n9:     TEST_ASSERT_EQUAL_STRING(string->valuestring, \"Hello World!\");\n10: \n11:     cJSON_Delete(root);\n12: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_create_object_reference_should_create_an_object_reference",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObjectCS",
        "cJSON_CreateObject",
        "cJSON_IsNumber",
        "cJSON_IsObject"
      ],
      "case_complexity": "moderate",
      "assertion_lines": [
        "TEST_ASSERT_TRUE(cJSON_IsNumber(number));",
        "TEST_ASSERT_TRUE(cJSON_IsObject(number_object));",
        "TEST_ASSERT_TRUE(number_reference->child == number);",
        "TEST_ASSERT_EQUAL_INT(cJSON_Object | cJSON_IsReference, number_reference->type);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsNumber(number));",
          "mentions_aligned_functions": [
            "cJSON_IsNumber"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsObject(number_object));",
          "mentions_aligned_functions": [
            "cJSON_IsObject"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(number_reference->child == number);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(cJSON_Object | cJSON_IsReference, number_reference->type);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"number\"",
        "42"
      ],
      "body_excerpt": "1: {\n2:     cJSON *number_reference = NULL;\n3:     cJSON *number_object = cJSON_CreateObject();\n4:     cJSON *number = cJSON_CreateNumber(42);\n5:     const char key[] = \"number\";\n6: \n7:     TEST_ASSERT_TRUE(cJSON_IsNumber(number));\n8:     TEST_ASSERT_TRUE(cJSON_IsObject(number_object));\n9:     cJSON_AddItemToObjectCS(number_object, key, number);\n10: \n11:     number_reference = cJSON_CreateObjectReference(number);\n12:     TEST_ASSERT_TRUE(number_reference->child == number);\n13:     TEST_ASSERT_EQUAL_INT(cJSON_Object | cJSON_IsReference, number_reference->type);\n14: \n15:     cJSON_Delete(number_object);\n16:     cJSON_Delete(number_reference);\n17: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_create_array_reference_should_create_an_array_reference",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToArray",
        "cJSON_CreateArray",
        "cJSON_IsArray",
        "cJSON_IsNumber"
      ],
      "case_complexity": "moderate",
      "assertion_lines": [
        "TEST_ASSERT_TRUE(cJSON_IsNumber(number));",
        "TEST_ASSERT_TRUE(cJSON_IsArray(number_array));",
        "TEST_ASSERT_TRUE(number_reference->child == number);",
        "TEST_ASSERT_EQUAL_INT(cJSON_Array | cJSON_IsReference, number_reference->type);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsNumber(number));",
          "mentions_aligned_functions": [
            "cJSON_IsNumber"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsArray(number_array));",
          "mentions_aligned_functions": [
            "cJSON_IsArray"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(number_reference->child == number);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(cJSON_Array | cJSON_IsReference, number_reference->type);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "42"
      ],
      "body_excerpt": "1: {\n2:     cJSON *number_reference = NULL;\n3:     cJSON *number_array = cJSON_CreateArray();\n4:     cJSON *number = cJSON_CreateNumber(42);\n5: \n6:     TEST_ASSERT_TRUE(cJSON_IsNumber(number));\n7:     TEST_ASSERT_TRUE(cJSON_IsArray(number_array));\n8:     cJSON_AddItemToArray(number_array, number);\n9: \n10:     number_reference = cJSON_CreateArrayReference(number);\n11:     TEST_ASSERT_TRUE(number_reference->child == number);\n12:     TEST_ASSERT_EQUAL_INT(cJSON_Array | cJSON_IsReference, number_reference->type);\n13: \n14:     cJSON_Delete(number_array);\n15:     cJSON_Delete(number_reference);\n16: }"
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "name": "parse_with_opts_should_handle_null",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, &error_pointer, false), \"Failed to handle NULL input.\");",
        "TEST_ASSERT_NOT_NULL_MESSAGE(item, \"Failed to handle NULL error pointer.\");",
        "TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, NULL, false), \"Failed to handle both NULL.\");",
        "TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(\"{\", NULL, false), \"Failed to handle NULL error pointer with parse error.\");"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, &error_pointer, false), \"Failed to handle NULL input.\");",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [
            "\"Failed to handle NULL input.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(item, \"Failed to handle NULL error pointer.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to handle NULL error pointer.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, NULL, false), \"Failed to handle both NULL.\");",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [
            "\"Failed to handle both NULL.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(\"{\", NULL, false), \"Failed to handle NULL error pointer with parse error.\");",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [
            "\"{\"",
            "\"Failed to handle NULL error pointer with parse error.\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"Failed to handle NULL input.\"",
        "\"{}\"",
        "\"Failed to handle NULL error pointer.\"",
        "\"Failed to handle both NULL.\"",
        "\"{\"",
        "\"Failed to handle NULL error pointer with parse error.\""
      ],
      "body_excerpt": "1: {\n2:     const char *error_pointer = NULL;\n3:     cJSON *item = NULL;\n4:     TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, &error_pointer, false), \"Failed to handle NULL input.\");\n5:     item = cJSON_ParseWithOpts(\"{}\", NULL, false);\n6:     TEST_ASSERT_NOT_NULL_MESSAGE(item, \"Failed to handle NULL error pointer.\");\n7:     cJSON_Delete(item);\n8:     TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, NULL, false), \"Failed to handle both NULL.\");\n9:     TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(\"{\", NULL, false), \"Failed to handle NULL error pointer with parse error.\");\n10: }"
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "name": "parse_with_opts_should_handle_empty_strings",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, NULL, false));",
        "TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());",
        "TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, &error_pointer, false));",
        "TEST_ASSERT_EQUAL_PTR(empty_string, error_pointer);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, NULL, false));",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, &error_pointer, false));",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(empty_string, error_pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"\""
      ],
      "body_excerpt": "1: {\n2:     const char empty_string[] = \"\";\n3:     const char *error_pointer = NULL;\n4: \n5:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, NULL, false));\n6:     TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());\n7: \n8:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, &error_pointer, false));\n9:     TEST_ASSERT_EQUAL_PTR(empty_string, error_pointer);\n10:     TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());\n11: }"
    },
    {
      "path": "tests/compare_tests.c",
      "framework": "unity",
      "name": "cjson_compare_should_compare_raw",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(raw1);",
        "TEST_ASSERT_NOT_NULL(raw2);",
        "TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, true));",
        "TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, false));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(raw1);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(raw2);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, true));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, false));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        }
      ],
      "literal_samples": [
        "\"\\\"[true, false]\\\"\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *raw1 = NULL;\n3:     cJSON *raw2 = NULL;\n4: \n5:     raw1 = cJSON_Parse(\"\\\"[true, false]\\\"\");\n6:     TEST_ASSERT_NOT_NULL(raw1);\n7:     raw2 = cJSON_Parse(\"\\\"[true, false]\\\"\");\n8:     TEST_ASSERT_NOT_NULL(raw2);\n9: \n10:     raw1->type = cJSON_Raw;\n11:     raw2->type = cJSON_Raw;\n12: \n13:     TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, true));\n14:     TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, false));\n15: \n16:     cJSON_Delete(raw1);\n17:     cJSON_Delete(raw2);\n18: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_parse_big_numbers_should_not_report_error",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(valid_big_number_json_object1);",
        "TEST_ASSERT_NOT_NULL(valid_big_number_json_object2);",
        "TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(invalid_big_number_json1), \"Invalid big number JSONs should not be parsed.\");",
        "TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(invalid_big_number_json2), \"Invalid big number JSONs should not be parsed.\");"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(valid_big_number_json_object1);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(valid_big_number_json_object2);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(invalid_big_number_json1), \"Invalid big number JSONs should not be parsed.\");",
          "mentions_aligned_functions": [
            "cJSON_Parse"
          ],
          "literal_samples": [
            "\"Invalid big number JSONs should not be parsed.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(invalid_big_number_json2), \"Invalid big number JSONs should not be parsed.\");",
          "mentions_aligned_functions": [
            "cJSON_Parse"
          ],
          "literal_samples": [
            "\"Invalid big number JSONs should not be parsed.\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"{\\\"a\\\": true, \\\"b\\\": [ null,9999999999999999999999999999999999999999999999912345678901234567]}\"",
        "\"{\\\"a\\\": true, \\\"b\\\": [ null,999999999999999999999999999999999999999999999991234567890.1234567E3]}\"",
        "\"{\\\"a\\\": true, \\\"b\\\": [ null,99999999999999999999999999999999999999999999999.1234567890.1234567]}\"",
        "\"{\\\"a\\\": true, \\\"b\\\": [ null,99999999999999999999999999999999999999999999999E1234567890e1234567]}\"",
        "\"Invalid big number JSONs should not be parsed.\"",
        "9999999999999999999999999999999999999999999999912345678901234567",
        "999999999999999999999999999999999999999999999991234567890.123456",
        "99999999999999999999999999999999999999999999999.1234567890",
        "1234567",
        "9999999999999999999999999999999999999999999999",
        "23456789",
        "234567"
      ],
      "body_excerpt": "1: {\n2:     cJSON *valid_big_number_json_object1 = cJSON_Parse(\"{\\\"a\\\": true, \\\"b\\\": [ null,9999999999999999999999999999999999999999999999912345678901234567]}\");\n3:     cJSON *valid_big_number_json_object2 = cJSON_Parse(\"{\\\"a\\\": true, \\\"b\\\": [ null,999999999999999999999999999999999999999999999991234567890.1234567E3]}\");\n4:     const char *invalid_big_number_json1 = \"{\\\"a\\\": true, \\\"b\\\": [ null,99999999999999999999999999999999999999999999999.1234567890.1234567]}\";\n5:     const char *invalid_big_number_json2 = \"{\\\"a\\\": true, \\\"b\\\": [ null,99999999999999999999999999999999999999999999999E1234567890e1234567]}\";\n6: \n7:     TEST_ASSERT_NOT_NULL(valid_big_number_json_object1);\n8:     TEST_ASSERT_NOT_NULL(valid_big_number_json_object2);\n9:     TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(invalid_big_number_json1), \"Invalid big number JSONs should not be parsed.\");\n10:     TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(invalid_big_number_json2), \"Invalid big number JSONs should not be parsed.\");\n11: \n12:     cJSON_Delete(valid_big_number_json_object1);\n13:     cJSON_Delete(valid_big_number_json_object2);\n14: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_raw_should_add_raw",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(raw = cJSON_GetObjectItemCaseSensitive(root, \"raw\"));",
        "TEST_ASSERT_EQUAL_INT(raw->type, cJSON_Raw);",
        "TEST_ASSERT_EQUAL_STRING(raw->valuestring, \"{}\");"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(raw = cJSON_GetObjectItemCaseSensitive(root, \"raw\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"raw\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(raw->type, cJSON_Raw);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(raw->valuestring, \"{}\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"{}\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"raw\"",
        "\"{}\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3:     cJSON *raw = NULL;\n4: \n5:     cJSON_AddRawToObject(root, \"raw\", \"{}\");\n6: \n7:     TEST_ASSERT_NOT_NULL(raw = cJSON_GetObjectItemCaseSensitive(root, \"raw\"));\n8:     TEST_ASSERT_EQUAL_INT(raw->type, cJSON_Raw);\n9:     TEST_ASSERT_EQUAL_STRING(raw->valuestring, \"{}\");\n10: \n11:     cJSON_Delete(root);\n12: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_add_item_to_object_should_not_use_after_free_when_string_is_aliased",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(object);",
        "TEST_ASSERT_NOT_NULL(number);",
        "TEST_ASSERT_NOT_NULL(name);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(object);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(number);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(name);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        }
      ],
      "literal_samples": [
        "\"number\"",
        "42"
      ],
      "body_excerpt": "1: {\n2:     cJSON *object = cJSON_CreateObject();\n3:     cJSON *number = cJSON_CreateNumber(42);\n4:     char *name = (char *)cJSON_strdup((const unsigned char *)\"number\", &global_hooks);\n5: \n6:     TEST_ASSERT_NOT_NULL(object);\n7:     TEST_ASSERT_NOT_NULL(number);\n8:     TEST_ASSERT_NOT_NULL(name);\n9: \n10:     number->string = name;\n11: \n12:     /* The following should not have a use after free\n13:      * that would show up in valgrind or with AddressSanitizer */\n14:     cJSON_AddItemToObject(object, number->string, number);\n15: \n16:     cJSON_Delete(object);\n17: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_true_should_add_true",
      "calls_aligned_public_functions": [
        "cJSON_AddTrueToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));",
        "TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"true\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"true\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3:     cJSON *true_item = NULL;\n4: \n5:     cJSON_AddTrueToObject(root, \"true\");\n6: \n7:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));\n8:     TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_false_should_add_false",
      "calls_aligned_public_functions": [
        "cJSON_AddFalseToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));",
        "TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"false\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3:     cJSON *false_item = NULL;\n4: \n5:     cJSON_AddFalseToObject(root, \"false\");\n6: \n7:     TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));\n8:     TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cJSON_add_object_should_add_object",
      "calls_aligned_public_functions": [
        "cJSON_AddObjectToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(object = cJSON_GetObjectItemCaseSensitive(root, \"object\"));",
        "TEST_ASSERT_EQUAL_INT(object->type, cJSON_Object);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(object = cJSON_GetObjectItemCaseSensitive(root, \"object\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"object\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(object->type, cJSON_Object);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"object\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3:     cJSON *object = NULL;\n4: \n5:     cJSON_AddObjectToObject(root, \"object\");\n6:     TEST_ASSERT_NOT_NULL(object = cJSON_GetObjectItemCaseSensitive(root, \"object\"));\n7:     TEST_ASSERT_EQUAL_INT(object->type, cJSON_Object);\n8: \n9:     cJSON_Delete(root);\n10: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cJSON_add_array_should_add_array",
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(array = cJSON_GetObjectItemCaseSensitive(root, \"array\"));",
        "TEST_ASSERT_EQUAL_INT(array->type, cJSON_Array);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(array = cJSON_GetObjectItemCaseSensitive(root, \"array\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"array\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(array->type, cJSON_Array);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"array\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3:     cJSON *array = NULL;\n4: \n5:     cJSON_AddArrayToObject(root, \"array\");\n6:     TEST_ASSERT_NOT_NULL(array = cJSON_GetObjectItemCaseSensitive(root, \"array\"));\n7:     TEST_ASSERT_EQUAL_INT(array->type, cJSON_Array);\n8: \n9:     cJSON_Delete(root);\n10: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_delete_item_from_array_should_not_broken_list_structure",
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_AddItemToArray",
        "cJSON_DeleteItemFromArray",
        "cJSON_Parse",
        "cJSON_PrintUnformatted"
      ],
      "case_complexity": "moderate",
      "assertion_lines": [
        "TEST_ASSERT_EQUAL_STRING(expected_json1, str1);",
        "TEST_ASSERT_EQUAL_STRING(expected_json2, str2);",
        "TEST_ASSERT_EQUAL_STRING(expected_json3, str3);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(expected_json1, str1);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(expected_json2, str2);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(expected_json3, str3);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"{\\\"rd\\\":[{\\\"a\\\":\\\"123\\\"}]}\"",
        "\"{\\\"rd\\\":[{\\\"a\\\":\\\"123\\\"},{\\\"b\\\":\\\"456\\\"}]}\"",
        "\"{\\\"rd\\\":[{\\\"b\\\":\\\"456\\\"}]}\"",
        "\"{}\"",
        "\"rd\"",
        "\"{\\\"a\\\":\\\"123\\\"}\"",
        "\"{\\\"b\\\":\\\"456\\\"}\"",
        "123",
        "456",
        "0"
      ],
      "body_excerpt": "1: {\n2:     const char expected_json1[] = \"{\\\"rd\\\":[{\\\"a\\\":\\\"123\\\"}]}\";\n3:     const char expected_json2[] = \"{\\\"rd\\\":[{\\\"a\\\":\\\"123\\\"},{\\\"b\\\":\\\"456\\\"}]}\";\n4:     const char expected_json3[] = \"{\\\"rd\\\":[{\\\"b\\\":\\\"456\\\"}]}\";\n5:     char *str1 = NULL;\n6:     char *str2 = NULL;\n7:     char *str3 = NULL;\n8: \n9:     cJSON *root = cJSON_Parse(\"{}\");\n10: \n11:     cJSON *array = cJSON_AddArrayToObject(root, \"rd\");\n12:     cJSON *item1 = cJSON_Parse(\"{\\\"a\\\":\\\"123\\\"}\");\n13:     cJSON *item2 = cJSON_Parse(\"{\\\"b\\\":\\\"456\\\"}\");\n14: \n15:     cJSON_AddItemToArray(array, item1);\n16:     str1 = cJSON_PrintUnformatted(root);\n17:     TEST_ASSERT_EQUAL_STRING(expected_json1, str1);\n18:     free(str1);\n19: \n20:     cJSON_AddItemToArray(array, item2);\n21:     str2 = cJSON_PrintUnformatted(root);\n22:     TEST_ASSERT_EQUAL_STRING(expected_json2, str2);\n23:     free(str2);\n24: \n25:     /* this should not broken list structure */\n26:     cJSON_DeleteItemFromArray(array, 0);\n27:     str3 = cJSON_PrintUnformatted(root);\n28:     TEST_ASSERT_EQUAL_STRING(expected_json3, str3);\n29:     free(str3);\n30: \n31:     cJSON_Delete(root);\n32: }"
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "name": "parse_with_opts_should_handle_incomplete_json",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_ParseWithOpts(json, &parse_end, false));",
        "TEST_ASSERT_EQUAL_PTR(json + strlen(json), parse_end);",
        "TEST_ASSERT_EQUAL_PTR(json + strlen(json), cJSON_GetErrorPtr());"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_ParseWithOpts(json, &parse_end, false));",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(json + strlen(json), parse_end);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(json + strlen(json), cJSON_GetErrorPtr());",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"{ \\\"name\\\": \""
      ],
      "body_excerpt": "1: {\n2:     const char json[] = \"{ \\\"name\\\": \";\n3:     const char *parse_end = NULL;\n4: \n5:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(json, &parse_end, false));\n6:     TEST_ASSERT_EQUAL_PTR(json + strlen(json), parse_end);\n7:     TEST_ASSERT_EQUAL_PTR(json + strlen(json), cJSON_GetErrorPtr());\n8: }"
    },
    {
      "path": "tests/parse_examples.c",
      "framework": "unity",
      "name": "file_test6_should_not_be_parsed",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL_MESSAGE(test6, \"Failed to read test6 data.\");",
        "TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse what is not JSON.\");",
        "TEST_ASSERT_EQUAL_PTR_MESSAGE(test6, cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(test6, \"Failed to read test6 data.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to read test6 data.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse what is not JSON.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Should fail to parse what is not JSON.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR_MESSAGE",
          "expression": "TEST_ASSERT_EQUAL_PTR_MESSAGE(test6, cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Error pointer is incorrect.\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"inputs/test6\"",
        "\"Failed to read test6 data.\"",
        "\"Should fail to parse what is not JSON.\"",
        "\"Error pointer is incorrect.\""
      ],
      "body_excerpt": "1: {\n2:     char *test6 = NULL;\n3:     cJSON *tree = NULL;\n4: \n5:     test6 = read_file(\"inputs/test6\");\n6:     TEST_ASSERT_NOT_NULL_MESSAGE(test6, \"Failed to read test6 data.\");\n7: \n8:     tree = cJSON_Parse(test6);\n9:     TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse what is not JSON.\");\n10: \n11:     TEST_ASSERT_EQUAL_PTR_MESSAGE(test6, cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");\n12: \n13:     if (test6 != NULL)\n14:     {\n15:         free(test6);\n16:     }\n17:     if (tree != NULL)\n18:     {\n19:         cJSON_Delete(tree);\n20:     }\n21: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_get_string_value_should_get_a_string",
      "calls_aligned_public_functions": [
        "cJSON_GetStringValue"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_TRUE(cJSON_GetStringValue(string) == string->valuestring);",
        "TEST_ASSERT_NULL(cJSON_GetStringValue(number));",
        "TEST_ASSERT_NULL(cJSON_GetStringValue(NULL));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_GetStringValue(string) == string->valuestring);",
          "mentions_aligned_functions": [
            "cJSON_GetStringValue"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_GetStringValue(number));",
          "mentions_aligned_functions": [
            "cJSON_GetStringValue"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_GetStringValue(NULL));",
          "mentions_aligned_functions": [
            "cJSON_GetStringValue"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"test\"",
        "1"
      ],
      "body_excerpt": "1: {\n2:     cJSON *string = cJSON_CreateString(\"test\");\n3:     cJSON *number = cJSON_CreateNumber(1);\n4: \n5:     TEST_ASSERT_TRUE(cJSON_GetStringValue(string) == string->valuestring);\n6:     TEST_ASSERT_NULL(cJSON_GetStringValue(number));\n7:     TEST_ASSERT_NULL(cJSON_GetStringValue(NULL));\n8: \n9:     cJSON_Delete(number);\n10:     cJSON_Delete(string);\n11: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_get_number_value_should_get_a_number",
      "calls_aligned_public_functions": [
        "cJSON_GetNumberValue"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_EQUAL_DOUBLE(cJSON_GetNumberValue(number), number->valuedouble);",
        "TEST_ASSERT_DOUBLE_IS_NAN(cJSON_GetNumberValue(string));",
        "TEST_ASSERT_DOUBLE_IS_NAN(cJSON_GetNumberValue(NULL));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(cJSON_GetNumberValue(number), number->valuedouble);",
          "mentions_aligned_functions": [
            "cJSON_GetNumberValue"
          ],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_DOUBLE_IS_NAN",
          "expression": "TEST_ASSERT_DOUBLE_IS_NAN(cJSON_GetNumberValue(string));",
          "mentions_aligned_functions": [
            "cJSON_GetNumberValue"
          ],
          "literal_samples": [],
          "oracle_hint": "assertion_line"
        },
        {
          "macro": "TEST_ASSERT_DOUBLE_IS_NAN",
          "expression": "TEST_ASSERT_DOUBLE_IS_NAN(cJSON_GetNumberValue(NULL));",
          "mentions_aligned_functions": [
            "cJSON_GetNumberValue"
          ],
          "literal_samples": [],
          "oracle_hint": "assertion_line"
        }
      ],
      "literal_samples": [
        "\"test\"",
        "1"
      ],
      "body_excerpt": "1: {\n2:     cJSON *string = cJSON_CreateString(\"test\");\n3:     cJSON *number = cJSON_CreateNumber(1);\n4: \n5:     TEST_ASSERT_EQUAL_DOUBLE(cJSON_GetNumberValue(number), number->valuedouble);\n6:     TEST_ASSERT_DOUBLE_IS_NAN(cJSON_GetNumberValue(string));\n7:     TEST_ASSERT_DOUBLE_IS_NAN(cJSON_GetNumberValue(NULL));\n8: \n9:     cJSON_Delete(number);\n10:     cJSON_Delete(string);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_null_should_add_null",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(null = cJSON_GetObjectItemCaseSensitive(root, \"null\"));",
        "TEST_ASSERT_EQUAL_INT(null->type, cJSON_NULL);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(null = cJSON_GetObjectItemCaseSensitive(root, \"null\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"null\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(null->type, cJSON_NULL);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"null\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3:     cJSON *null = NULL;\n4: \n5:     cJSON_AddNullToObject(root, \"null\");\n6: \n7:     TEST_ASSERT_NOT_NULL(null = cJSON_GetObjectItemCaseSensitive(root, \"null\"));\n8:     TEST_ASSERT_EQUAL_INT(null->type, cJSON_NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_true_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddTrueToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddTrueToObject(NULL, \"true\"));",
        "TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, NULL));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddTrueToObject(NULL, \"true\"));",
          "mentions_aligned_functions": [
            "cJSON_AddTrueToObject"
          ],
          "literal_samples": [
            "\"true\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, NULL));",
          "mentions_aligned_functions": [
            "cJSON_AddTrueToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"true\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(NULL, \"true\"));\n5:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, NULL));\n6: \n7:     cJSON_Delete(root);\n8: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_false_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddFalseToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddFalseToObject(NULL, \"false\"));",
        "TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, NULL));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddFalseToObject(NULL, \"false\"));",
          "mentions_aligned_functions": [
            "cJSON_AddFalseToObject"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, NULL));",
          "mentions_aligned_functions": [
            "cJSON_AddFalseToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"false\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(NULL, \"false\"));\n5:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, NULL));\n6: \n7:     cJSON_Delete(root);\n8: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_bool_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddBoolToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddBoolToObject(NULL, \"false\", false));",
        "TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, NULL, false));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddBoolToObject(NULL, \"false\", false));",
          "mentions_aligned_functions": [
            "cJSON_AddBoolToObject"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, NULL, false));",
          "mentions_aligned_functions": [
            "cJSON_AddBoolToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"false\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     TEST_ASSERT_NULL(cJSON_AddBoolToObject(NULL, \"false\", false));\n5:     TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, NULL, false));\n6: \n7:     cJSON_Delete(root);\n8: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_number_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddNumberToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddNumberToObject(NULL, \"number\", 42));",
        "TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, NULL, 42));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNumberToObject(NULL, \"number\", 42));",
          "mentions_aligned_functions": [
            "cJSON_AddNumberToObject"
          ],
          "literal_samples": [
            "\"number\"",
            "42"
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, NULL, 42));",
          "mentions_aligned_functions": [
            "cJSON_AddNumberToObject"
          ],
          "literal_samples": [
            "42"
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"number\"",
        "42"
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     TEST_ASSERT_NULL(cJSON_AddNumberToObject(NULL, \"number\", 42));\n5:     TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, NULL, 42));\n6: \n7:     cJSON_Delete(root);\n8: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_string_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddStringToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddStringToObject(NULL, \"string\", \"string\"));",
        "TEST_ASSERT_NULL(cJSON_AddStringToObject(root, NULL, \"string\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddStringToObject(NULL, \"string\", \"string\"));",
          "mentions_aligned_functions": [
            "cJSON_AddStringToObject"
          ],
          "literal_samples": [
            "\"string\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddStringToObject(root, NULL, \"string\"));",
          "mentions_aligned_functions": [
            "cJSON_AddStringToObject"
          ],
          "literal_samples": [
            "\"string\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"string\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     TEST_ASSERT_NULL(cJSON_AddStringToObject(NULL, \"string\", \"string\"));\n5:     TEST_ASSERT_NULL(cJSON_AddStringToObject(root, NULL, \"string\"));\n6: \n7:     cJSON_Delete(root);\n8: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_object_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddObjectToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddObjectToObject(NULL, \"object\"));",
        "TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, NULL));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddObjectToObject(NULL, \"object\"));",
          "mentions_aligned_functions": [
            "cJSON_AddObjectToObject"
          ],
          "literal_samples": [
            "\"object\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, NULL));",
          "mentions_aligned_functions": [
            "cJSON_AddObjectToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"object\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     TEST_ASSERT_NULL(cJSON_AddObjectToObject(NULL, \"object\"));\n5:     TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, NULL));\n6: \n7:     cJSON_Delete(root);\n8: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_array_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddArrayToObject(NULL, \"array\"));",
        "TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, NULL));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddArrayToObject(NULL, \"array\"));",
          "mentions_aligned_functions": [
            "cJSON_AddArrayToObject"
          ],
          "literal_samples": [
            "\"array\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, NULL));",
          "mentions_aligned_functions": [
            "cJSON_AddArrayToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"array\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     TEST_ASSERT_NULL(cJSON_AddArrayToObject(NULL, \"array\"));\n5:     TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, NULL));\n6: \n7:     cJSON_Delete(root);\n8: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_should_not_follow_too_deep_circular_references",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToArray",
        "cJSON_CreateArray",
        "cJSON_DetachItemFromArray"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(x);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(x);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "1",
        "0"
      ],
      "body_excerpt": "1: {\n2:     cJSON *o = cJSON_CreateArray();\n3:     cJSON *a = cJSON_CreateArray();\n4:     cJSON *b = cJSON_CreateArray();\n5:     cJSON *x;\n6: \n7:     cJSON_AddItemToArray(o, a);\n8:     cJSON_AddItemToArray(a, b);\n9:     cJSON_AddItemToArray(b, o);\n10: \n11:     x = cJSON_Duplicate(o, 1);\n12:     TEST_ASSERT_NULL(x);\n13:     cJSON_DetachItemFromArray(b, 0);\n14:     cJSON_Delete(o);\n15: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_add_item_to_object_or_array_should_not_add_itself",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToArray",
        "cJSON_AddItemToObject",
        "cJSON_CreateArray",
        "cJSON_CreateObject"
      ],
      "case_complexity": "moderate",
      "assertion_lines": [
        "TEST_ASSERT_FALSE_MESSAGE(flag, \"add an object to itself should fail\");",
        "TEST_ASSERT_FALSE_MESSAGE(flag, \"add an array to itself should fail\");"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_FALSE_MESSAGE",
          "expression": "TEST_ASSERT_FALSE_MESSAGE(flag, \"add an object to itself should fail\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"add an object to itself should fail\""
          ],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE_MESSAGE",
          "expression": "TEST_ASSERT_FALSE_MESSAGE(flag, \"add an array to itself should fail\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"add an array to itself should fail\""
          ],
          "oracle_hint": "falsehood_oracle"
        }
      ],
      "literal_samples": [
        "\"key\"",
        "\"add an object to itself should fail\"",
        "\"add an array to itself should fail\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *object = cJSON_CreateObject();\n3:     cJSON *array = cJSON_CreateArray();\n4:     cJSON_bool flag = false;\n5: \n6:     flag = cJSON_AddItemToObject(object, \"key\", object);\n7:     TEST_ASSERT_FALSE_MESSAGE(flag, \"add an object to itself should fail\");\n8: \n9:     flag = cJSON_AddItemToArray(array, array);\n10:     TEST_ASSERT_FALSE_MESSAGE(flag, \"add an array to itself should fail\");\n11: \n12:     cJSON_Delete(object);\n13:     cJSON_Delete(array);\n14: }"
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "name": "parse_with_opts_should_require_null_if_requested",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(item);",
        "TEST_ASSERT_NULL(cJSON_ParseWithOpts(\"{}x\", NULL, true));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(item);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(item);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_ParseWithOpts(\"{}x\", NULL, true));",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [
            "\"{}x\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"{}\"",
        "\"{} \\n\"",
        "\"{}x\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *item = cJSON_ParseWithOpts(\"{}\", NULL, true);\n3:     TEST_ASSERT_NOT_NULL(item);\n4:     cJSON_Delete(item);\n5:     item = cJSON_ParseWithOpts(\"{} \\n\", NULL, true);\n6:     TEST_ASSERT_NOT_NULL(item);\n7:     cJSON_Delete(item);\n8:     TEST_ASSERT_NULL(cJSON_ParseWithOpts(\"{}x\", NULL, true));\n9: }"
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "name": "parse_with_opts_should_return_parse_end",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(item);",
        "TEST_ASSERT_EQUAL_PTR(json + 2, parse_end);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(item);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(json + 2, parse_end);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"[] empty array XD\"",
        "2"
      ],
      "body_excerpt": "1: {\n2:     const char json[] = \"[] empty array XD\";\n3:     const char *parse_end = NULL;\n4: \n5:     cJSON *item = cJSON_ParseWithOpts(json, &parse_end, false);\n6:     TEST_ASSERT_NOT_NULL(item);\n7:     TEST_ASSERT_EQUAL_PTR(json + 2, parse_end);\n8:     cJSON_Delete(item);\n9: }"
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "name": "parse_with_opts_should_parse_utf8_bom",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NOT_NULL(with_bom);",
        "TEST_ASSERT_TRUE(cJSON_Compare(with_bom, without_bom, true));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(with_bom);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(with_bom);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_Compare(with_bom, without_bom, true));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        }
      ],
      "literal_samples": [
        "\"\\xEF\\xBB\\xBF{}\"",
        "\"{}\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *with_bom = NULL;\n3:     cJSON *without_bom = NULL;\n4: \n5:     with_bom = cJSON_ParseWithOpts(\"\\xEF\\xBB\\xBF{}\", NULL, true);\n6:     TEST_ASSERT_NOT_NULL(with_bom);\n7:     without_bom = cJSON_ParseWithOpts(\"{}\", NULL, true);\n8:     TEST_ASSERT_NOT_NULL(with_bom);\n9: \n10:     TEST_ASSERT_TRUE(cJSON_Compare(with_bom, without_bom, true));\n11: \n12:     cJSON_Delete(with_bom);\n13:     cJSON_Delete(without_bom);\n14: }"
    },
    {
      "path": "tests/parse_examples.c",
      "framework": "unity",
      "name": "test12_should_not_be_parsed",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse incomplete JSON.\");",
        "TEST_ASSERT_EQUAL_PTR_MESSAGE(test12 + strlen(test12), cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse incomplete JSON.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Should fail to parse incomplete JSON.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR_MESSAGE",
          "expression": "TEST_ASSERT_EQUAL_PTR_MESSAGE(test12 + strlen(test12), cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Error pointer is incorrect.\"",
            "2"
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"{ \\\"name\\\": \"",
        "\"Should fail to parse incomplete JSON.\"",
        "\"Error pointer is incorrect.\"",
        "2"
      ],
      "body_excerpt": "1: {\n2:     const char *test12 = \"{ \\\"name\\\": \";\n3:     cJSON *tree = NULL;\n4: \n5:     tree = cJSON_Parse(test12);\n6:     TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse incomplete JSON.\");\n7: \n8:     TEST_ASSERT_EQUAL_PTR_MESSAGE(test12 + strlen(test12), cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");\n9: \n10:     if (tree != NULL)\n11:     {\n12:         cJSON_Delete(tree);\n13:     }\n14: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_null_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddNullToObject(NULL, \"null\"));",
        "TEST_ASSERT_NULL(cJSON_AddNullToObject(root, NULL));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNullToObject(NULL, \"null\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"null\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNullToObject(root, NULL));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"null\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     TEST_ASSERT_NULL(cJSON_AddNullToObject(NULL, \"null\"));\n5:     TEST_ASSERT_NULL(cJSON_AddNullToObject(root, NULL));\n6: \n7:     cJSON_Delete(root);\n8: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_raw_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddRawToObject(NULL, \"raw\", \"{}\"));",
        "TEST_ASSERT_NULL(cJSON_AddRawToObject(root, NULL, \"{}\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddRawToObject(NULL, \"raw\", \"{}\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"raw\"",
            "\"{}\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddRawToObject(root, NULL, \"{}\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"{}\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"raw\"",
        "\"{}\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     TEST_ASSERT_NULL(cJSON_AddRawToObject(NULL, \"raw\", \"{}\"));\n5:     TEST_ASSERT_NULL(cJSON_AddRawToObject(root, NULL, \"{}\"));\n6: \n7:     cJSON_Delete(root);\n8: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_set_valuestring_should_return_null_if_strings_overlap",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_TRUE(strcmp(str, \"bcde\") == 0);",
        "TEST_ASSERT_NULL(str2);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(strcmp(str, \"bcde\") == 0);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"bcde\"",
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(str2);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"\\\"foo0z\\\"\"",
        "\"abcde\"",
        "\"bcde\"",
        "1",
        "0"
      ],
      "body_excerpt": "1: {       \n2:     cJSON *obj;\n3:     char* str;\n4:     char* str2;\n5: \n6:     obj =  cJSON_Parse(\"\\\"foo0z\\\"\");\n7:     \n8:     str =  cJSON_SetValuestring(obj, \"abcde\");\n9:     str += 1;\n10:     /* The string passed to strcpy overlap which is not allowed.*/\n11:     str2 = cJSON_SetValuestring(obj, str);\n12:     /* If it overlaps, the string will be messed up.*/\n13:     TEST_ASSERT_TRUE(strcmp(str, \"bcde\") == 0);\n14:     TEST_ASSERT_NULL(str2);\n15:     cJSON_Delete(obj);\n16: }"
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "name": "sort_tests",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_TRUE(current_element->string[0] >= current_element->prev->string[0]);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(current_element->string[0] >= current_element->prev->string[0]);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        }
      ],
      "literal_samples": [
        "\"QWERTYUIOPASDFGHJKLZXCVBNM\"",
        "2",
        "0",
        "26",
        "1"
      ],
      "body_excerpt": "1: {\n2:     /* Misc tests */\n3:     const char *random = \"QWERTYUIOPASDFGHJKLZXCVBNM\";\n4:     char buf[2] = {'\\0', '\\0'};\n5:     cJSON *sortme = NULL;\n6:     size_t i = 0;\n7:     cJSON *current_element = NULL;\n8: \n9:     /* JSON Sort test: */\n10:     sortme = cJSON_CreateObject();\n11:     for (i = 0; i < 26; i++)\n12:     {\n13:         buf[0] = random[i];\n14:         cJSON_AddItemToObject(sortme, buf, cJSON_CreateNumber(1));\n15:     }\n16: \n17:     cJSONUtils_SortObject(sortme);\n18: \n19:     /* check sorting */\n20:     current_element = sortme->child->next;\n21:     for (i = 1; (i < 26) && (current_element != NULL) && (current_element->prev != NULL); i++)\n22:     {\n23:         TEST_ASSERT_TRUE(current_element->string[0] >= current_element->prev->string[0]);\n24:         current_element = current_element->next;\n25:     }\n26: \n27:     cJSON_Delete(sortme);\n28: }"
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "name": "merge_tests",
      "calls_aligned_public_functions": [
        "cJSON_Parse",
        "cJSON_PrintUnformatted"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_EQUAL_STRING(merges[i][2], after);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(merges[i][2], after);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "\"JSON Merge Patch tests\\n\"",
        "0",
        "15",
        "1",
        "2"
      ],
      "body_excerpt": "1: {\n2:     size_t i = 0;\n3:     char *patchtext = NULL;\n4:     char *after = NULL;\n5: \n6:     /* Merge tests: */\n7:     printf(\"JSON Merge Patch tests\\n\");\n8:     for (i = 0; i < 15; i++)\n9:     {\n10:         cJSON *object_to_be_merged = cJSON_Parse(merges[i][0]);\n11:         cJSON *patch = cJSON_Parse(merges[i][1]);\n12:         patchtext = cJSON_PrintUnformatted(patch);\n13:         object_to_be_merged = cJSONUtils_MergePatch(object_to_be_merged, patch);\n14:         after = cJSON_PrintUnformatted(object_to_be_merged);\n15:         TEST_ASSERT_EQUAL_STRING(merges[i][2], after);\n16: \n17:         free(patchtext);\n18:         free(after);\n19:         cJSON_Delete(object_to_be_merged);\n20:         cJSON_Delete(patch);\n21:     }\n22: }"
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "name": "generate_merge_tests",
      "calls_aligned_public_functions": [
        "cJSON_Parse",
        "cJSON_PrintUnformatted"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_EQUAL_STRING(merges[i][2], patchedtext);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(merges[i][2], patchedtext);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        }
      ],
      "literal_samples": [
        "0",
        "15",
        "2"
      ],
      "body_excerpt": "1: {\n2:     size_t i = 0;\n3:     char *patchedtext = NULL;\n4: \n5:     /* Generate Merge tests: */\n6:     for (i = 0; i < 15; i++)\n7:     {\n8:         cJSON *from = cJSON_Parse(merges[i][0]);\n9:         cJSON *to = cJSON_Parse(merges[i][2]);\n10:         cJSON *patch = cJSONUtils_GenerateMergePatch(from,to);\n11:         from = cJSONUtils_MergePatch(from,patch);\n12:         patchedtext = cJSON_PrintUnformatted(from);\n13:         TEST_ASSERT_EQUAL_STRING(merges[i][2], patchedtext);\n14: \n15:         cJSON_Delete(from);\n16:         cJSON_Delete(to);\n17:         cJSON_Delete(patch);\n18:         free(patchedtext);\n19:     }\n20: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_true_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddTrueToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, \"true\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, \"true\"));",
          "mentions_aligned_functions": [
            "cJSON_AddTrueToObject"
          ],
          "literal_samples": [
            "\"true\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"true\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     cJSON_InitHooks(&failing_hooks);\n5: \n6:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, \"true\"));\n7: \n8:     cJSON_InitHooks(NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_false_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddFalseToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, \"false\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, \"false\"));",
          "mentions_aligned_functions": [
            "cJSON_AddFalseToObject"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"false\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     cJSON_InitHooks(&failing_hooks);\n5: \n6:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, \"false\"));\n7: \n8:     cJSON_InitHooks(NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_bool_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddBoolToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, \"false\", false));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, \"false\", false));",
          "mentions_aligned_functions": [
            "cJSON_AddBoolToObject"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"false\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     cJSON_InitHooks(&failing_hooks);\n5: \n6:     TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, \"false\", false));\n7: \n8:     cJSON_InitHooks(NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_number_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddNumberToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, \"number\", 42));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, \"number\", 42));",
          "mentions_aligned_functions": [
            "cJSON_AddNumberToObject"
          ],
          "literal_samples": [
            "\"number\"",
            "42"
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"number\"",
        "42"
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     cJSON_InitHooks(&failing_hooks);\n5: \n6:     TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, \"number\", 42));\n7: \n8:     cJSON_InitHooks(NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_string_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddStringToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddStringToObject(root, \"string\", \"string\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddStringToObject(root, \"string\", \"string\"));",
          "mentions_aligned_functions": [
            "cJSON_AddStringToObject"
          ],
          "literal_samples": [
            "\"string\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"string\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     cJSON_InitHooks(&failing_hooks);\n5: \n6:     TEST_ASSERT_NULL(cJSON_AddStringToObject(root, \"string\", \"string\"));\n7: \n8:     cJSON_InitHooks(NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_object_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddObjectToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, \"object\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, \"object\"));",
          "mentions_aligned_functions": [
            "cJSON_AddObjectToObject"
          ],
          "literal_samples": [
            "\"object\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"object\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     cJSON_InitHooks(&failing_hooks);\n5: \n6:     TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, \"object\"));\n7: \n8:     cJSON_InitHooks(NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_array_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, \"array\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, \"array\"));",
          "mentions_aligned_functions": [
            "cJSON_AddArrayToObject"
          ],
          "literal_samples": [
            "\"array\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"array\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     cJSON_InitHooks(&failing_hooks);\n5: \n6:     TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, \"array\"));\n7: \n8:     cJSON_InitHooks(NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_get_object_item_case_sensitive_should_not_crash_with_array",
      "calls_aligned_public_functions": [
        "cJSON_GetObjectItemCaseSensitive",
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(found);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(found);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"[1]\"",
        "\"name\"",
        "1"
      ],
      "body_excerpt": "1: {\n2:     cJSON *array = NULL;\n3:     cJSON *found = NULL;\n4:     array = cJSON_Parse(\"[1]\");\n5: \n6:     found = cJSON_GetObjectItemCaseSensitive(array, \"name\");\n7:     TEST_ASSERT_NULL(found);\n8: \n9:     cJSON_Delete(array);\n10: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_null_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddNullToObject(root, \"null\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNullToObject(root, \"null\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"null\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"null\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     cJSON_InitHooks(&failing_hooks);\n5: \n6:     TEST_ASSERT_NULL(cJSON_AddNullToObject(root, \"null\"));\n7: \n8:     cJSON_InitHooks(NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "name": "cjson_add_raw_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(cJSON_AddRawToObject(root, \"raw\", \"{}\"));"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddRawToObject(root, \"raw\", \"{}\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"raw\"",
            "\"{}\""
          ],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"raw\"",
        "\"{}\""
      ],
      "body_excerpt": "1: {\n2:     cJSON *root = cJSON_CreateObject();\n3: \n4:     cJSON_InitHooks(&failing_hooks);\n5: \n6:     TEST_ASSERT_NULL(cJSON_AddRawToObject(root, \"raw\", \"{}\"));\n7: \n8:     cJSON_InitHooks(NULL);\n9: \n10:     cJSON_Delete(root);\n11: }"
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "name": "cjson_get_object_item_should_not_crash_with_array",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "case_complexity": "focused",
      "assertion_lines": [
        "TEST_ASSERT_NULL(found);"
      ],
      "assertion_evidence": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(found);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ],
      "literal_samples": [
        "\"[1]\"",
        "\"name\"",
        "1"
      ],
      "body_excerpt": "1: {\n2:     cJSON *array = NULL;\n3:     cJSON *found = NULL;\n4:     array = cJSON_Parse(\"[1]\");\n5: \n6:     found = cJSON_GetObjectItem(array, \"name\");\n7:     TEST_ASSERT_NULL(found);\n8: \n9:     cJSON_Delete(array);\n10: }"
    }
  ],
  "source_assertion_evidence": [
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_functions_should_not_crash_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToArray",
        "cJSON_AddItemToObject",
        "cJSON_AddItemToObjectCS",
        "cJSON_CreateArray",
        "cJSON_DeleteItemFromArray",
        "cJSON_DeleteItemFromObject",
        "cJSON_DeleteItemFromObjectCaseSensitive",
        "cJSON_DetachItemFromArray",
        "cJSON_DetachItemFromObject",
        "cJSON_DetachItemFromObjectCaseSensitive",
        "cJSON_GetArraySize",
        "cJSON_GetObjectItemCaseSensitive",
        "cJSON_HasObjectItem",
        "cJSON_IsArray",
        "cJSON_IsBool",
        "cJSON_IsNull",
        "cJSON_IsNumber",
        "cJSON_IsObject",
        "cJSON_IsString",
        "cJSON_Parse",
        "cJSON_ParseWithOpts",
        "cJSON_Print",
        "cJSON_PrintUnformatted",
        "cJSON_ReplaceItemInObject",
        "cJSON_ReplaceItemInObjectCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_Parse(NULL));",
          "mentions_aligned_functions": [
            "cJSON_Parse"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_ParseWithOpts(NULL, NULL, true));",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_Print(NULL));",
          "mentions_aligned_functions": [
            "cJSON_Print"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_PrintUnformatted(NULL));",
          "mentions_aligned_functions": [
            "cJSON_PrintUnformatted"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_PrintBuffered(NULL, 10, true));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "10"
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_PrintPreallocated(NULL, buffer, sizeof(buffer), true));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_PrintPreallocated(item, NULL, 1, true));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_GetArrayItem(NULL, 0));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "test_name": "parse_with_opts_should_handle_null",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, &error_pointer, false), \"Failed to handle NULL input.\");",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [
            "\"Failed to handle NULL input.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(item, \"Failed to handle NULL error pointer.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to handle NULL error pointer.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(NULL, NULL, false), \"Failed to handle both NULL.\");",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [
            "\"Failed to handle both NULL.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_ParseWithOpts(\"{\", NULL, false), \"Failed to handle NULL error pointer with parse error.\");",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [
            "\"{\"",
            "\"Failed to handle NULL error pointer with parse error.\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_get_string_value_should_get_a_string",
      "calls_aligned_public_functions": [
        "cJSON_GetStringValue"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_GetStringValue(string) == string->valuestring);",
          "mentions_aligned_functions": [
            "cJSON_GetStringValue"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_GetStringValue(number));",
          "mentions_aligned_functions": [
            "cJSON_GetStringValue"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_GetStringValue(NULL));",
          "mentions_aligned_functions": [
            "cJSON_GetStringValue"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_get_number_value_should_get_a_number",
      "calls_aligned_public_functions": [
        "cJSON_GetNumberValue"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(cJSON_GetNumberValue(number), number->valuedouble);",
          "mentions_aligned_functions": [
            "cJSON_GetNumberValue"
          ],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_DOUBLE_IS_NAN",
          "expression": "TEST_ASSERT_DOUBLE_IS_NAN(cJSON_GetNumberValue(string));",
          "mentions_aligned_functions": [
            "cJSON_GetNumberValue"
          ],
          "literal_samples": [],
          "oracle_hint": "assertion_line"
        },
        {
          "macro": "TEST_ASSERT_DOUBLE_IS_NAN",
          "expression": "TEST_ASSERT_DOUBLE_IS_NAN(cJSON_GetNumberValue(NULL));",
          "mentions_aligned_functions": [
            "cJSON_GetNumberValue"
          ],
          "literal_samples": [],
          "oracle_hint": "assertion_line"
        }
      ]
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "test_name": "parse_with_opts_should_handle_empty_strings",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, NULL, false));",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_ParseWithOpts(empty_string, &error_pointer, false));",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(empty_string, error_pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(empty_string, cJSON_GetErrorPtr());",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_parse_big_numbers_should_not_report_error",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(valid_big_number_json_object1);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(valid_big_number_json_object2);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(invalid_big_number_json1), \"Invalid big number JSONs should not be parsed.\");",
          "mentions_aligned_functions": [
            "cJSON_Parse"
          ],
          "literal_samples": [
            "\"Invalid big number JSONs should not be parsed.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(invalid_big_number_json2), \"Invalid big number JSONs should not be parsed.\");",
          "mentions_aligned_functions": [
            "cJSON_Parse"
          ],
          "literal_samples": [
            "\"Invalid big number JSONs should not be parsed.\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_bool_should_add_bool",
      "calls_aligned_public_functions": [
        "cJSON_AddBoolToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"true\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_create_object_reference_should_create_an_object_reference",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObjectCS",
        "cJSON_CreateObject",
        "cJSON_IsNumber",
        "cJSON_IsObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsNumber(number));",
          "mentions_aligned_functions": [
            "cJSON_IsNumber"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsObject(number_object));",
          "mentions_aligned_functions": [
            "cJSON_IsObject"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(number_reference->child == number);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(cJSON_Object | cJSON_IsReference, number_reference->type);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_create_array_reference_should_create_an_array_reference",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToArray",
        "cJSON_CreateArray",
        "cJSON_IsArray",
        "cJSON_IsNumber"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsNumber(number));",
          "mentions_aligned_functions": [
            "cJSON_IsNumber"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsArray(number_array));",
          "mentions_aligned_functions": [
            "cJSON_IsArray"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(number_reference->child == number);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(cJSON_Array | cJSON_IsReference, number_reference->type);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_true_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddTrueToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddTrueToObject(NULL, \"true\"));",
          "mentions_aligned_functions": [
            "cJSON_AddTrueToObject"
          ],
          "literal_samples": [
            "\"true\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, NULL));",
          "mentions_aligned_functions": [
            "cJSON_AddTrueToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_false_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddFalseToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddFalseToObject(NULL, \"false\"));",
          "mentions_aligned_functions": [
            "cJSON_AddFalseToObject"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, NULL));",
          "mentions_aligned_functions": [
            "cJSON_AddFalseToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_bool_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddBoolToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddBoolToObject(NULL, \"false\", false));",
          "mentions_aligned_functions": [
            "cJSON_AddBoolToObject"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, NULL, false));",
          "mentions_aligned_functions": [
            "cJSON_AddBoolToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_number_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddNumberToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNumberToObject(NULL, \"number\", 42));",
          "mentions_aligned_functions": [
            "cJSON_AddNumberToObject"
          ],
          "literal_samples": [
            "\"number\"",
            "42"
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, NULL, 42));",
          "mentions_aligned_functions": [
            "cJSON_AddNumberToObject"
          ],
          "literal_samples": [
            "42"
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_string_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddStringToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddStringToObject(NULL, \"string\", \"string\"));",
          "mentions_aligned_functions": [
            "cJSON_AddStringToObject"
          ],
          "literal_samples": [
            "\"string\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddStringToObject(root, NULL, \"string\"));",
          "mentions_aligned_functions": [
            "cJSON_AddStringToObject"
          ],
          "literal_samples": [
            "\"string\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_object_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddObjectToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddObjectToObject(NULL, \"object\"));",
          "mentions_aligned_functions": [
            "cJSON_AddObjectToObject"
          ],
          "literal_samples": [
            "\"object\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, NULL));",
          "mentions_aligned_functions": [
            "cJSON_AddObjectToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_array_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddArrayToObject(NULL, \"array\"));",
          "mentions_aligned_functions": [
            "cJSON_AddArrayToObject"
          ],
          "literal_samples": [
            "\"array\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, NULL));",
          "mentions_aligned_functions": [
            "cJSON_AddArrayToObject"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "typecheck_functions_should_check_type",
      "calls_aligned_public_functions": [
        "cJSON_IsArray",
        "cJSON_IsBool",
        "cJSON_IsNull",
        "cJSON_IsNumber",
        "cJSON_IsObject",
        "cJSON_IsString"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsInvalid(NULL));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsInvalid(item));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsInvalid(invalid));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsFalse(NULL));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsFalse(invalid));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsFalse(item));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsBool(item));",
          "mentions_aligned_functions": [
            "cJSON_IsBool"
          ],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE",
          "expression": "TEST_ASSERT_FALSE(cJSON_IsTrue(NULL));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "falsehood_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_number_should_add_number",
      "calls_aligned_public_functions": [
        "cJSON_AddNumberToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(number = cJSON_GetObjectItemCaseSensitive(root, \"number\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"number\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(number->type, cJSON_Number);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(number->valuedouble, 42);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "42"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(number->valueint, 42);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "42"
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "test_name": "parse_with_opts_should_handle_incomplete_json",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_ParseWithOpts(json, &parse_end, false));",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(json + strlen(json), parse_end);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(json + strlen(json), cJSON_GetErrorPtr());",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "test_name": "parse_with_opts_should_require_null_if_requested",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(item);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(item);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_ParseWithOpts(\"{}x\", NULL, true));",
          "mentions_aligned_functions": [
            "cJSON_ParseWithOpts"
          ],
          "literal_samples": [
            "\"{}x\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_raw_should_add_raw",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(raw = cJSON_GetObjectItemCaseSensitive(root, \"raw\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"raw\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(raw->type, cJSON_Raw);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(raw->valuestring, \"{}\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"{}\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_string_should_add_string",
      "calls_aligned_public_functions": [
        "cJSON_AddStringToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(string = cJSON_GetObjectItemCaseSensitive(root, \"string\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"string\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(string->type, cJSON_String);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(string->valuestring, \"Hello World!\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Hello World!\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_null_should_add_null",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(null = cJSON_GetObjectItemCaseSensitive(root, \"null\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"null\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(null->type, cJSON_NULL);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_true_should_add_true",
      "calls_aligned_public_functions": [
        "cJSON_AddTrueToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"true\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_false_should_add_false",
      "calls_aligned_public_functions": [
        "cJSON_AddFalseToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cJSON_add_object_should_add_object",
      "calls_aligned_public_functions": [
        "cJSON_AddObjectToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(object = cJSON_GetObjectItemCaseSensitive(root, \"object\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"object\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(object->type, cJSON_Object);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cJSON_add_array_should_add_array",
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_CreateObject",
        "cJSON_GetObjectItemCaseSensitive"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(array = cJSON_GetObjectItemCaseSensitive(root, \"array\"));",
          "mentions_aligned_functions": [
            "cJSON_GetObjectItemCaseSensitive"
          ],
          "literal_samples": [
            "\"array\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_INT",
          "expression": "TEST_ASSERT_EQUAL_INT(array->type, cJSON_Array);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_should_not_parse_to_deeply_nested_jsons",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(deep_json), \"To deep JSONs should not be parsed.\");",
          "mentions_aligned_functions": [
            "cJSON_Parse"
          ],
          "literal_samples": [
            "\"To deep JSONs should not be parsed.\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_true_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddTrueToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, \"true\"));",
          "mentions_aligned_functions": [
            "cJSON_AddTrueToObject"
          ],
          "literal_samples": [
            "\"true\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_false_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddFalseToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, \"false\"));",
          "mentions_aligned_functions": [
            "cJSON_AddFalseToObject"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_bool_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddBoolToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, \"false\", false));",
          "mentions_aligned_functions": [
            "cJSON_AddBoolToObject"
          ],
          "literal_samples": [
            "\"false\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_number_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddNumberToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, \"number\", 42));",
          "mentions_aligned_functions": [
            "cJSON_AddNumberToObject"
          ],
          "literal_samples": [
            "\"number\"",
            "42"
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_string_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddStringToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddStringToObject(root, \"string\", \"string\"));",
          "mentions_aligned_functions": [
            "cJSON_AddStringToObject"
          ],
          "literal_samples": [
            "\"string\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_object_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddObjectToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, \"object\"));",
          "mentions_aligned_functions": [
            "cJSON_AddObjectToObject"
          ],
          "literal_samples": [
            "\"object\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_array_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, \"array\"));",
          "mentions_aligned_functions": [
            "cJSON_AddArrayToObject"
          ],
          "literal_samples": [
            "\"array\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "test_name": "json_pointer_tests",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"\"), root);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo\"), cJSON_GetObjectItem(root, \"foo\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/foo\"",
            "\"foo\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/foo/0\"",
            "\"foo\"",
            "0"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/foo/0\"), cJSON_GetObjectItem(root, \"foo\")->child);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/foo/0\"",
            "\"foo\"",
            "0"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/\"), cJSON_GetObjectItem(root, \"\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/\"",
            "\"\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/a~1b\"), cJSON_GetObjectItem(root, \"a/b\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/a~1b\"",
            "\"a/b\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c%d\"), cJSON_GetObjectItem(root, \"c%d\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/c%d\"",
            "\"c%d\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(cJSONUtils_GetPointer(root, \"/c^f\"), cJSON_GetObjectItem(root, \"c^f\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/c^f\"",
            "\"c^f\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_get_object_item_should_get_object_items",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to fail on NULL pointer.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to fail on NULL string.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find first item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find first item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "3"
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_get_object_item_case_sensitive_should_get_object_items",
      "calls_aligned_public_functions": [
        "cJSON_GetObjectItemCaseSensitive",
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL pointer.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to fail on NULL pointer.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(found, \"Failed to fail on NULL string.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to fail on NULL string.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find first item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 1);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find first item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find first item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 2);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(found, \"Failed to find item.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to find item.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_DOUBLE",
          "expression": "TEST_ASSERT_EQUAL_DOUBLE(found->valuedouble, 3);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "3"
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_replace_item_via_pointer_should_replace_items",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToArray",
        "cJSON_CreateArray"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(beginning);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(middle);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(end);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(array);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, beginning, &(replacements[0])));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(replacements[0].prev == end);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(replacements[0].next == middle);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(middle->prev == &(replacements[0]));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_set_bool_value_must_not_break_objects",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject",
        "cJSON_IsObject",
        "cJSON_IsString"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE((cJSON_SetBoolValue(refobj, 1) == cJSON_Invalid));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 1) == cJSON_True));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "1"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsTrue(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsTrue(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE((cJSON_SetBoolValue(bobj, 0) == cJSON_False));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_IsFalse(bobj));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_set_valuestring_to_object_should_not_leak_memory",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_CreateObject",
        "cJSON_IsObject",
        "cJSON_IsString",
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(return_value);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR_MESSAGE",
          "expression": "TEST_ASSERT_EQUAL_PTR_MESSAGE(ptr1, return_value, \"new valuestring shorter than old should not reallocate memory\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"new valuestring shorter than old should not reallocate memory\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(short_valuestring, cJSON_GetObjectItem(root, \"one\")->valuestring);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"one\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(return_value);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_EQUAL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_EQUAL_MESSAGE(ptr1, return_value, \"new valuestring longer than old should reallocate memory\")",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"new valuestring longer than old should reallocate memory\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(long_valuestring, cJSON_GetObjectItem(root, \"one\")->valuestring);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"one\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(return_value, \"valuestring of reference object should not be changed\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"valuestring of reference object should not be changed\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(reference_",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "test_name": "misc_tests",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"/numbers/6\", pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/numbers/6\"",
            "6"
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"/numbers\", pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/numbers\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"\", pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"/m~0n\",pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/m~0n\""
          ],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"/m~1n\",pointer);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"/m~1n\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_replace_item_in_object_should_preserve_name",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_ReplaceItemInObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(child);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(replacement);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE_MESSAGE",
          "expression": "TEST_ASSERT_TRUE_MESSAGE(flag, \"add item to object failed\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"add item to object failed\""
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(root->child == replacement);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(\"child\", replacement->string);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"child\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/compare_tests.c",
      "framework": "unity",
      "test_name": "cjson_compare_should_compare_raw",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(raw1);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(raw2);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, true));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_Compare(raw1, raw2, false));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        }
      ]
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "test_name": "parse_with_opts_should_parse_utf8_bom",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(with_bom);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(with_bom);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(cJSON_Compare(with_bom, without_bom, true));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "truth_oracle"
        }
      ]
    },
    {
      "path": "tests/parse_examples.c",
      "framework": "unity",
      "test_name": "file_test6_should_not_be_parsed",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NOT_NULL_MESSAGE(test6, \"Failed to read test6 data.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Failed to read test6 data.\""
          ],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse what is not JSON.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Should fail to parse what is not JSON.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR_MESSAGE",
          "expression": "TEST_ASSERT_EQUAL_PTR_MESSAGE(test6, cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Error pointer is incorrect.\""
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_add_item_to_object_should_not_use_after_free_when_string_is_aliased",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(object);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(number);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(name);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_delete_item_from_array_should_not_broken_list_structure",
      "calls_aligned_public_functions": [
        "cJSON_AddArrayToObject",
        "cJSON_AddItemToArray",
        "cJSON_DeleteItemFromArray",
        "cJSON_Parse",
        "cJSON_PrintUnformatted"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(expected_json1, str1);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(expected_json2, str2);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(expected_json3, str3);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/parse_with_opts.c",
      "framework": "unity",
      "test_name": "parse_with_opts_should_return_parse_end",
      "calls_aligned_public_functions": [
        "cJSON_ParseWithOpts"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NOT_NULL",
          "expression": "TEST_ASSERT_NOT_NULL(item);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "non_null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR",
          "expression": "TEST_ASSERT_EQUAL_PTR(json + 2, parse_end);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/parse_examples.c",
      "framework": "unity",
      "test_name": "test12_should_not_be_parsed",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL_MESSAGE",
          "expression": "TEST_ASSERT_NULL_MESSAGE(tree, \"Should fail to parse incomplete JSON.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Should fail to parse incomplete JSON.\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_EQUAL_PTR_MESSAGE",
          "expression": "TEST_ASSERT_EQUAL_PTR_MESSAGE(test12 + strlen(test12), cJSON_GetErrorPtr(), \"Error pointer is incorrect.\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"Error pointer is incorrect.\"",
            "2"
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_null_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNullToObject(NULL, \"null\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"null\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNullToObject(root, NULL));",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_raw_should_fail_with_null_pointers",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddRawToObject(NULL, \"raw\", \"{}\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"raw\"",
            "\"{}\""
          ],
          "oracle_hint": "null_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddRawToObject(root, NULL, \"{}\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"{}\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_set_valuestring_should_return_null_if_strings_overlap",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(strcmp(str, \"bcde\") == 0);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"bcde\"",
            "0"
          ],
          "oracle_hint": "truth_oracle"
        },
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(str2);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_add_item_to_object_or_array_should_not_add_itself",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToArray",
        "cJSON_AddItemToObject",
        "cJSON_CreateArray",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_FALSE_MESSAGE",
          "expression": "TEST_ASSERT_FALSE_MESSAGE(flag, \"add an object to itself should fail\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"add an object to itself should fail\""
          ],
          "oracle_hint": "falsehood_oracle"
        },
        {
          "macro": "TEST_ASSERT_FALSE_MESSAGE",
          "expression": "TEST_ASSERT_FALSE_MESSAGE(flag, \"add an array to itself should fail\");",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"add an array to itself should fail\""
          ],
          "oracle_hint": "falsehood_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_null_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddNullToObject(root, \"null\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"null\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/cjson_add.c",
      "framework": "unity",
      "test_name": "cjson_add_raw_should_fail_on_allocation_failure",
      "calls_aligned_public_functions": [
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(cJSON_AddRawToObject(root, \"raw\", \"{}\"));",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "\"raw\"",
            "\"{}\""
          ],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_get_object_item_should_not_crash_with_array",
      "calls_aligned_public_functions": [
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(found);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "test_name": "sort_tests",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToObject",
        "cJSON_CreateObject"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_TRUE",
          "expression": "TEST_ASSERT_TRUE(current_element->string[0] >= current_element->prev->string[0]);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "0"
          ],
          "oracle_hint": "truth_oracle"
        }
      ]
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "test_name": "merge_tests",
      "calls_aligned_public_functions": [
        "cJSON_Parse",
        "cJSON_PrintUnformatted"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(merges[i][2], after);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/old_utils_tests.c",
      "framework": "unity",
      "test_name": "generate_merge_tests",
      "calls_aligned_public_functions": [
        "cJSON_Parse",
        "cJSON_PrintUnformatted"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_EQUAL_STRING",
          "expression": "TEST_ASSERT_EQUAL_STRING(merges[i][2], patchedtext);",
          "mentions_aligned_functions": [],
          "literal_samples": [
            "2"
          ],
          "oracle_hint": "equality_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_get_object_item_case_sensitive_should_not_crash_with_array",
      "calls_aligned_public_functions": [
        "cJSON_GetObjectItemCaseSensitive",
        "cJSON_Parse"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(found);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    },
    {
      "path": "tests/misc_tests.c",
      "framework": "unity",
      "test_name": "cjson_should_not_follow_too_deep_circular_references",
      "calls_aligned_public_functions": [
        "cJSON_AddItemToArray",
        "cJSON_CreateArray",
        "cJSON_DetachItemFromArray"
      ],
      "assertions": [
        {
          "macro": "TEST_ASSERT_NULL",
          "expression": "TEST_ASSERT_NULL(x);",
          "mentions_aligned_functions": [],
          "literal_samples": [],
          "oracle_hint": "null_oracle"
        }
      ]
    }
  ],
  "source_function_test_evidence": {
    "cJSON.c::cJSON_AddArrayToObject": [
      {
        "path": "tests/readme_examples.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "create_monitor_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "create_monitor_with_helpers_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "supports_full_hd_should_check_for_full_hd_support"
          }
        ],
        "snippet": "127: \n128:     cJSON *monitor = cJSON_CreateObject();\n129: \n130:     if (cJSON_AddStringToObject(monitor, \"name\", \"Awesome 4K\") == NULL)\n131:     {\n132:         goto end;\n133:     }\n134: \n135:     resolutions = cJSON_AddArrayToObject(monitor, \"resolutions\");\n136:     if (resolutions == NULL)\n137:     {\n138:         goto end;\n139:     }\n140: \n141:     for (index = 0; index < (sizeof(resolution_numbers) / (2 * sizeof(int))); ++index)\n142:     {\n143:         cJSON *resolution = cJSON_CreateObject();\n144: \n145:         if (cJSON_AddNumberToObject(resolution, \"width\", resolution_numbers[index][0]) == NULL)\n146:         {\n147:             goto end;\n148:         }",
        "assertion_lines": [],
        "literal_samples": [
          "\"name\"",
          "\"Awesome 4K\"",
          "\"resolutions\"",
          "\"width\"",
          "127",
          "128",
          "129",
          "130",
          "131",
          "132",
          "133",
          "134",
          "135",
          "136",
          "137",
          "138",
          "139",
          "140",
          "141",
          "0",
          "2",
          "142",
          "143",
          "144",
          "145",
          "146",
          "147",
          "148"
        ]
      },
      {
        "path": "tests/cjson_add.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_add_null_should_add_null"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_add_true"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_int_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_float_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_double_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_string_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_add_false"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_fail_with_null_pointers"
          }
        ],
        "snippet": "387:     cJSON_Delete(root);\n388: }\n389: \n390: static void cJSON_add_array_should_add_array(void)\n391: {\n392:     cJSON *root = cJSON_CreateObject();\n393:     cJSON *array = NULL;\n394: \n395:     cJSON_AddArrayToObject(root, \"array\");\n396:     TEST_ASSERT_NOT_NULL(array = cJSON_GetObjectItemCaseSensitive(root, \"array\"));\n397:     TEST_ASSERT_EQUAL_INT(array->type, cJSON_Array);\n398: \n399:     cJSON_Delete(root);\n400: }\n401: \n402: static void cjson_add_array_should_fail_with_null_pointers(void)\n403: {\n404:     cJSON *root = cJSON_CreateObject();\n405: \n406:     TEST_ASSERT_NULL(cJSON_AddArrayToObject(NULL, \"array\"));\n407:     TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, NULL));\n408: \n409:     cJSON_Delete(root);\n410: }\n411: \n412: static void cjson_add_array_should_fail_on_allocation_failure(void)\n413: {\n414:     cJSON *root = cJSON_CreateObject();\n415: \n416:     cJSON_InitHooks(&failing_hooks);\n417: \n418:     TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, \"array\"));\n419: \n420:     cJSON_InitHooks(NULL);\n421: \n422:     cJSON_Delete(root);\n423: }\n424: \n425: int CJSON_CDECL main(void)\n426: {\n427:     UNITY_BEGIN();\n428: \n429:     RUN_TEST(cjson_add_null_should_add_null);\n430:     RUN_TEST(cjson_add_null_should_fail_with_null_pointers);\n431:     RUN_TEST(cjson_add_null_should_fail_on_allocation_failure);",
        "assertion_lines": [
          "396:     TEST_ASSERT_NOT_NULL(array = cJSON_GetObjectItemCaseSensitive(root, \"array\"));",
          "397:     TEST_ASSERT_EQUAL_INT(array->type, cJSON_Array);",
          "406:     TEST_ASSERT_NULL(cJSON_AddArrayToObject(NULL, \"array\"));",
          "407:     TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, NULL));",
          "418:     TEST_ASSERT_NULL(cJSON_AddArrayToObject(root, \"array\"));"
        ],
        "literal_samples": [
          "\"array\"",
          "387",
          "388",
          "389",
          "390",
          "391",
          "392",
          "393",
          "394",
          "395",
          "396",
          "397",
          "398",
          "399",
          "400",
          "401",
          "402",
          "403",
          "404",
          "405",
          "406",
          "407",
          "408",
          "409",
          "410",
          "411",
          "412",
          "413"
        ]
      },
      {
        "path": "tests/misc_tests.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_loop_over_arrays"
          },
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_not_dereference_null_pointer"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "typecheck_functions_should_check_type"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_parse_to_deeply_nested_jsons"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_follow_too_deep_circular_references"
          },
          {
            "framework": "unity",
            "name": "cjson_set_number_value_should_set_numbers"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_detach_items"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_return_null_if_item_prev_is_null"
          }
        ],
        "snippet": "662:     const char expected_json2[] = \"{\\\"rd\\\":[{\\\"a\\\":\\\"123\\\"},{\\\"b\\\":\\\"456\\\"}]}\";\n663:     const char expected_json3[] = \"{\\\"rd\\\":[{\\\"b\\\":\\\"456\\\"}]}\";\n664:     char *str1 = NULL;\n665:     char *str2 = NULL;\n666:     char *str3 = NULL;\n667: \n668:     cJSON *root = cJSON_Parse(\"{}\");\n669: \n670:     cJSON *array = cJSON_AddArrayToObject(root, \"rd\");\n671:     cJSON *item1 = cJSON_Parse(\"{\\\"a\\\":\\\"123\\\"}\");\n672:     cJSON *item2 = cJSON_Parse(\"{\\\"b\\\":\\\"456\\\"}\");\n673: \n674:     cJSON_AddItemToArray(array, item1);\n675:     str1 = cJSON_PrintUnformatted(root);\n676:     TEST_ASSERT_EQUAL_STRING(expected_json1, str1);\n677:     free(str1);\n678: \n679:     cJSON_AddItemToArray(array, item2);\n680:     str2 = cJSON_PrintUnformatted(root);\n681:     TEST_ASSERT_EQUAL_STRING(expected_json2, str2);\n682:     free(str2);\n683: ",
        "assertion_lines": [
          "676:     TEST_ASSERT_EQUAL_STRING(expected_json1, str1);",
          "681:     TEST_ASSERT_EQUAL_STRING(expected_json2, str2);"
        ],
        "literal_samples": [
          "\"{\\\"rd\\\":[{\\\"a\\\":\\\"123\\\"},{\\\"b\\\":\\\"456\\\"}]}\"",
          "\"{\\\"rd\\\":[{\\\"b\\\":\\\"456\\\"}]}\"",
          "\"{}\"",
          "\"rd\"",
          "\"{\\\"a\\\":\\\"123\\\"}\"",
          "\"{\\\"b\\\":\\\"456\\\"}\"",
          "662",
          "123",
          "456",
          "663",
          "664",
          "665",
          "666",
          "667",
          "668",
          "669",
          "670",
          "671",
          "672",
          "673",
          "674",
          "675",
          "676",
          "677",
          "678",
          "679",
          "680",
          "681"
        ]
      }
    ],
    "cJSON.c::cJSON_AddBoolToObject": [
      {
        "path": "tests/cjson_add.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_add_null_should_add_null"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_add_true"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_int_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_float_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_double_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_string_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_add_false"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_fail_with_null_pointers"
          }
        ],
        "snippet": "199: \n200: static void cjson_add_bool_should_add_bool(void)\n201: {\n202:     cJSON *root = cJSON_CreateObject();\n203:     cJSON *true_item = NULL;\n204:     cJSON *false_item = NULL;\n205: \n206:     /* true */\n207:     cJSON_AddBoolToObject(root, \"true\", true);\n208:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));\n209:     TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);\n210: \n211:     /* false */\n212:     cJSON_AddBoolToObject(root, \"false\", false);\n213:     TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));\n214:     TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);\n215: \n216:     cJSON_Delete(root);\n217: }\n218: \n219: static void cjson_add_bool_should_fail_with_null_pointers(void)\n220: {\n221:     cJSON *root = cJSON_CreateObject();\n222: \n223:     TEST_ASSERT_NULL(cJSON_AddBoolToObject(NULL, \"false\", false));\n224:     TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, NULL, false));\n225: \n226:     cJSON_Delete(root);\n227: }\n228: \n229: static void cjson_add_bool_should_fail_on_allocation_failure(void)\n230: {\n231:     cJSON *root = cJSON_CreateObject();\n232: \n233:     cJSON_InitHooks(&failing_hooks);\n234: \n235:     TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, \"false\", false));\n236: \n237:     cJSON_InitHooks(NULL);\n238: \n239:     cJSON_Delete(root);\n240: }\n241: \n242: static void cjson_add_number_should_add_number(void)\n243: {\n244:     cJSON *root = cJSON_CreateObject();\n245:     cJSON *number = NULL;\n246: \n247:     cJSON_AddNumberToObject(root, \"number\", 42);\n248: ",
        "assertion_lines": [
          "208:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));",
          "209:     TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);",
          "213:     TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));",
          "214:     TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);",
          "223:     TEST_ASSERT_NULL(cJSON_AddBoolToObject(NULL, \"false\", false));",
          "224:     TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, NULL, false));",
          "235:     TEST_ASSERT_NULL(cJSON_AddBoolToObject(root, \"false\", false));"
        ],
        "literal_samples": [
          "\"true\"",
          "\"false\"",
          "\"number\"",
          "199",
          "200",
          "201",
          "202",
          "203",
          "204",
          "205",
          "206",
          "207",
          "208",
          "209",
          "210",
          "211",
          "212",
          "213",
          "214",
          "215",
          "216",
          "217",
          "218",
          "219",
          "220",
          "221",
          "222",
          "223"
        ]
      }
    ],
    "cJSON.c::cJSON_AddFalseToObject": [
      {
        "path": "test.c",
        "frameworks": [],
        "candidate_test_cases": [],
        "snippet": "166: \n167:     /* Our \"Video\" datatype: */\n168:     root = cJSON_CreateObject();\n169:     cJSON_AddItemToObject(root, \"name\", cJSON_CreateString(\"Jack (\\\"Bee\\\") Nimble\"));\n170:     cJSON_AddItemToObject(root, \"format\", fmt = cJSON_CreateObject());\n171:     cJSON_AddStringToObject(fmt, \"type\", \"rect\");\n172:     cJSON_AddNumberToObject(fmt, \"width\", 1920);\n173:     cJSON_AddNumberToObject(fmt, \"height\", 1080);\n174:     cJSON_AddFalseToObject (fmt, \"interlace\");\n175:     cJSON_AddNumberToObject(fmt, \"frame rate\", 24);\n176: \n177:     /* Print to text */\n178:     if (print_preallocated(root) != 0) {\n179:         cJSON_Delete(root);\n180:         exit(EXIT_FAILURE);\n181:     }\n182:     cJSON_Delete(root);\n183: \n184:     /* Our \"days of the week\" array: */\n185:     root = cJSON_CreateStringArray(strings, 7);\n186: \n187:     if (print_preallocated(root) != 0) {",
        "assertion_lines": [],
        "literal_samples": [
          "\"Video\"",
          "\"name\"",
          "\"Jack (\\\"Bee\\\") Nimble\"",
          "\"format\"",
          "\"type\"",
          "\"rect\"",
          "\"width\"",
          "\"height\"",
          "\"interlace\"",
          "\"frame rate\"",
          "\"days of the week\"",
          "166",
          "167",
          "168",
          "169",
          "170",
          "171",
          "172",
          "1920",
          "173",
          "1080",
          "174",
          "175",
          "24",
          "176",
          "177",
          "178",
          "0"
        ]
      },
      {
        "path": "tests/cjson_add.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_add_null_should_add_null"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_add_true"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_int_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_float_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_double_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_string_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_add_false"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_fail_with_null_pointers"
          }
        ],
        "snippet": "161:     cJSON_InitHooks(NULL);\n162: }\n163: \n164: static void cjson_add_false_should_add_false(void)\n165: {\n166:     cJSON *root = cJSON_CreateObject();\n167:     cJSON *false_item = NULL;\n168: \n169:     cJSON_AddFalseToObject(root, \"false\");\n170: \n171:     TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));\n172:     TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);\n173: \n174:     cJSON_Delete(root);\n175: }\n176: \n177: static void cjson_add_false_should_fail_with_null_pointers(void)\n178: {\n179:     cJSON *root = cJSON_CreateObject();\n180: \n181:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(NULL, \"false\"));\n182:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, NULL));\n183: \n184:     cJSON_Delete(root);\n185: }\n186: \n187: static void cjson_add_false_should_fail_on_allocation_failure(void)\n188: {\n189:     cJSON *root = cJSON_CreateObject();\n190: \n191:     cJSON_InitHooks(&failing_hooks);\n192: \n193:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, \"false\"));\n194: \n195:     cJSON_InitHooks(NULL);\n196: \n197:     cJSON_Delete(root);\n198: }\n199: \n200: static void cjson_add_bool_should_add_bool(void)\n201: {\n202:     cJSON *root = cJSON_CreateObject();\n203:     cJSON *true_item = NULL;\n204:     cJSON *false_item = NULL;\n205: \n206:     /* true */",
        "assertion_lines": [
          "171:     TEST_ASSERT_NOT_NULL(false_item = cJSON_GetObjectItemCaseSensitive(root, \"false\"));",
          "172:     TEST_ASSERT_EQUAL_INT(false_item->type, cJSON_False);",
          "181:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(NULL, \"false\"));",
          "182:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, NULL));",
          "193:     TEST_ASSERT_NULL(cJSON_AddFalseToObject(root, \"false\"));"
        ],
        "literal_samples": [
          "\"false\"",
          "161",
          "162",
          "163",
          "164",
          "165",
          "166",
          "167",
          "168",
          "169",
          "170",
          "171",
          "172",
          "173",
          "174",
          "175",
          "176",
          "177",
          "178",
          "179",
          "180",
          "181",
          "182",
          "183",
          "184",
          "185",
          "186",
          "187"
        ]
      }
    ],
    "cJSON.c::cJSON_AddItemToArray": [
      {
        "path": "test.c",
        "frameworks": [],
        "candidate_test_cases": [],
        "snippet": "189:         exit(EXIT_FAILURE);\n190:     }\n191:     cJSON_Delete(root);\n192: \n193:     /* Our matrix: */\n194:     root = cJSON_CreateArray();\n195:     for (i = 0; i < 3; i++)\n196:     {\n197:         cJSON_AddItemToArray(root, cJSON_CreateIntArray(numbers[i], 3));\n198:     }\n199: \n200:     /* cJSON_ReplaceItemInArray(root, 1, cJSON_CreateString(\"Replacement\")); */\n201: \n202:     if (print_preallocated(root) != 0) {\n203:         cJSON_Delete(root);\n204:         exit(EXIT_FAILURE);\n205:     }\n206:     cJSON_Delete(root);\n207: \n208:     /* Our \"gallery\" item: */\n209:     root = cJSON_CreateObject();\n210:     cJSON_AddItemToObject(root, \"Image\", img = cJSON_CreateObject());\n...\n222:         exit(EXIT_FAILURE);\n223:     }\n224:     cJSON_Delete(root);\n225: \n226:     /* Our array of \"records\": */\n227:     root = cJSON_CreateArray();\n228:     for (i = 0; i < 2; i++)\n229:     {\n230:         cJSON_AddItemToArray(root, fld = cJSON_CreateObject());\n231:         cJSON_AddStringToObject(fld, \"precision\", fields[i].precision);\n232:         cJSON_AddNumberToObject(fld, \"Latitude\", fields[i].lat);\n233:         cJSON_AddNumberToObject(fld, \"Longitude\", fields[i].lon);\n234:         cJSON_AddStringToObject(fld, \"Address\", fields[i].address);\n235:         cJSON_AddStringToObject(fld, \"City\", fields[i].city);\n236:         cJSON_AddStringToObject(fld, \"State\", fields[i].state);\n237:         cJSON_AddStringToObject(fld, \"Zip\", fields[i].zip);\n238:         cJSON_AddStringToObject(fld, \"Country\", fields[i].country);\n239:     }\n240: \n241:     /* cJSON_ReplaceItemInObject(cJSON_GetArrayItem(root, 1), ",
        "assertion_lines": [],
        "literal_samples": [
          "\"Replacement\"",
          "\"gallery\"",
          "\"Image\"",
          "\"records\"",
          "\"precision\"",
          "\"Latitude\"",
          "\"Longitude\"",
          "\"Address\"",
          "\"City\"",
          "\"State\"",
          "\"Zip\"",
          "\"Country\"",
          "189",
          "190",
          "191",
          "192",
          "193",
          "194",
          "195",
          "0",
          "3",
          "196",
          "197",
          "198",
          "199",
          "200",
          "1",
          "201"
        ]
      },
      {
        "path": "tests/readme_examples.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "create_monitor_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "create_monitor_with_helpers_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "supports_full_hd_should_check_for_full_hd_support"
          }
        ],
        "snippet": "81: \n82:     for (index = 0; index < (sizeof(resolution_numbers) / (2 * sizeof(int))); ++index)\n83:     {\n84:         resolution = cJSON_CreateObject();\n85:         if (resolution == NULL)\n86:         {\n87:             goto end;\n88:         }\n89:         cJSON_AddItemToArray(resolutions, resolution);\n90: \n91:         width = cJSON_CreateNumber(resolution_numbers[index][0]);\n92:         if (width == NULL)\n93:         {\n94:             goto end;\n95:         }\n96:         cJSON_AddItemToObject(resolution, \"width\", width);\n97: \n98:         height = cJSON_CreateNumber(resolution_numbers[index][1]);\n99:         if (height == NULL)\n100:         {\n101:             goto end;\n102:         }\n...\n147:             goto end;\n148:         }\n149: \n150:         if(cJSON_AddNumberToObject(resolution, \"height\", resolution_numbers[index][1]) == NULL)\n151:         {\n152:             goto end;\n153:         }\n154: \n155:         cJSON_AddItemToArray(resolutions, resolution);\n156:     }\n157: \n158:     string = cJSON_Print(monitor);\n159:     if (string == NULL) {\n160:         fprintf(stderr, \"Failed to print monitor.\\n\");\n161:     }\n162: \n163: end:\n164:     cJSON_Delete(monitor);\n165:     return string;\n166: }\n167: \n168: /* return 1 if the monitor supports full hd, 0 otherwise */",
        "assertion_lines": [],
        "literal_samples": [
          "\"width\"",
          "\"height\"",
          "\"Failed to print monitor.\\n\"",
          "81",
          "82",
          "0",
          "2",
          "83",
          "84",
          "85",
          "86",
          "87",
          "88",
          "89",
          "90",
          "91",
          "92",
          "93",
          "94",
          "95",
          "96",
          "97",
          "98",
          "1",
          "99",
          "100",
          "101",
          "102"
        ]
      },
      {
        "path": "tests/misc_tests.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_loop_over_arrays"
          },
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_not_dereference_null_pointer"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "typecheck_functions_should_check_type"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_parse_to_deeply_nested_jsons"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_follow_too_deep_circular_references"
          },
          {
            "framework": "unity",
            "name": "cjson_set_number_value_should_set_numbers"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_detach_items"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_return_null_if_item_prev_is_null"
          }
        ],
        "snippet": "222: \n223: static void cjson_should_not_follow_too_deep_circular_references(void)\n224: {\n225:     cJSON *o = cJSON_CreateArray();\n226:     cJSON *a = cJSON_CreateArray();\n227:     cJSON *b = cJSON_CreateArray();\n228:     cJSON *x;\n229: \n230:     cJSON_AddItemToArray(o, a);\n231:     cJSON_AddItemToArray(a, b);\n232:     cJSON_AddItemToArray(b, o);\n233: \n234:     x = cJSON_Duplicate(o, 1);\n235:     TEST_ASSERT_NULL(x);\n236:     cJSON_DetachItemFromArray(b, 0);\n237:     cJSON_Delete(o);\n238: }\n239: \n240: static void cjson_set_number_value_should_set_numbers(void)\n241: {\n242:     cJSON number[1] = {{NULL, NULL, NULL, cJSON_Number, NULL, 0, 0, NULL}};\n243: \n244:     cJSON_SetNumberValue(number, 1.5);\n245:     TEST_ASSERT_EQUAL(1, number->valueint);\n...\n326:     middle = cJSON_CreateNull();\n327:     TEST_ASSERT_NOT_NULL(middle);\n328:     end = cJSON_CreateNull();\n329:     TEST_ASSERT_NOT_NULL(end);\n330: \n331:     array = cJSON_CreateArray();\n332:     TEST_ASSERT_NOT_NULL(array);\n333: \n334:     cJSON_AddItemToArray(array, beginning);\n335:     cJSON_AddItemToArray(array, middle);\n336:     cJSON_AddItemToArray(array, end);\n337: \n338:     memset(replacements, '\\0', sizeof(replacements));\n339: \n340:     /* replace beginning */\n341:     TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, beginning, &(replacements[0])));\n342:     TEST_ASSERT_TRUE(replacements[0].prev == end);\n343:     TEST_ASSERT_TRUE(replacements[0].next == middle);\n344:     TEST_ASSERT_TRUE(middle->prev == &(replacements[0]));\n345:     TEST_ASSERT_TRUE(array->child == &(replacements[0]));\n346: \n347:     /* replace midd",
        "assertion_lines": [
          "235:     TEST_ASSERT_NULL(x);",
          "245:     TEST_ASSERT_EQUAL(1, number->valueint);",
          "327:     TEST_ASSERT_NOT_NULL(middle);",
          "329:     TEST_ASSERT_NOT_NULL(end);",
          "332:     TEST_ASSERT_NOT_NULL(array);",
          "341:     TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, beginning, &(replacements[0])));",
          "342:     TEST_ASSERT_TRUE(replacements[0].prev == end);",
          "343:     TEST_ASSERT_TRUE(replacements[0].next == middle);",
          "344:     TEST_ASSERT_TRUE(middle->prev == &(replacements[0]));",
          "345:     TEST_ASSERT_TRUE(array->child == &(replacements[0]));"
        ],
        "literal_samples": [
          "222",
          "223",
          "224",
          "225",
          "226",
          "227",
          "228",
          "229",
          "230",
          "231",
          "232",
          "233",
          "234",
          "1",
          "235",
          "236",
          "0",
          "237",
          "238",
          "239",
          "240",
          "241",
          "242",
          "243",
          "244",
          "1.5",
          "245",
          "326"
        ]
      }
    ],
    "cJSON.c::cJSON_AddItemToObject": [
      {
        "path": "test.c",
        "frameworks": [],
        "candidate_test_cases": [],
        "snippet": "161:         }\n162:     };\n163:     volatile double zero = 0.0;\n164: \n165:     /* Here we construct some JSON standards, from the JSON site. */\n166: \n167:     /* Our \"Video\" datatype: */\n168:     root = cJSON_CreateObject();\n169:     cJSON_AddItemToObject(root, \"name\", cJSON_CreateString(\"Jack (\\\"Bee\\\") Nimble\"));\n170:     cJSON_AddItemToObject(root, \"format\", fmt = cJSON_CreateObject());\n171:     cJSON_AddStringToObject(fmt, \"type\", \"rect\");\n172:     cJSON_AddNumberToObject(fmt, \"width\", 1920);\n173:     cJSON_AddNumberToObject(fmt, \"height\", 1080);\n174:     cJSON_AddFalseToObject (fmt, \"interlace\");\n175:     cJSON_AddNumberToObject(fmt, \"frame rate\", 24);\n176: \n177:     /* Print to text */\n178:     if (print_preallocated(root) != 0) {\n179:         cJSON_Delete(root);\n180:         exit(EXIT_FAILURE);\n181:     }\n182:     cJSON_Delete(root);\n183: \n...\n202:     if (print_preallocated(root) != 0) {\n203:         cJSON_Delete(root);\n204:         exit(EXIT_FAILURE);\n205:     }\n206:     cJSON_Delete(root);\n207: \n208:     /* Our \"gallery\" item: */\n209:     root = cJSON_CreateObject();\n210:     cJSON_AddItemToObject(root, \"Image\", img = cJSON_CreateObject());\n211:     cJSON_AddNumberToObject(img, \"Width\", 800);\n212:     cJSON_AddNumberToObject(img, \"Height\", 600);\n213:     cJSON_AddStringToObject(img, \"Title\", \"View from 15th Floor\");\n214:     cJSON_AddItemToObject(img, \"Thumbnail\", thm = cJSON_CreateObject());\n215:     cJSON_AddStringToObject(thm, \"Url\", \"http:/*www.example.com/image/481989943\");\n216:     cJSON_AddNumberToObject(thm, \"Height\", 125);\n217:     cJSON_AddStringToObject(",
        "assertion_lines": [],
        "literal_samples": [
          "\"Video\"",
          "\"name\"",
          "\"Jack (\\\"Bee\\\") Nimble\"",
          "\"format\"",
          "\"type\"",
          "\"rect\"",
          "\"width\"",
          "\"height\"",
          "\"interlace\"",
          "\"frame rate\"",
          "\"gallery\"",
          "\"Image\"",
          "\"Width\"",
          "\"Height\"",
          "\"Title\"",
          "\"View from 15th Floor\"",
          "\"Thumbnail\"",
          "\"Url\"",
          "\"http:/*www.example.com/image/481989943\"",
          "161",
          "162",
          "163",
          "0.0",
          "164",
          "165",
          "166",
          "167",
          "168"
        ]
      },
      {
        "path": "tests/readme_examples.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "create_monitor_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "create_monitor_with_helpers_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "supports_full_hd_should_check_for_full_hd_support"
          }
        ],
        "snippet": "65: \n66:     name = cJSON_CreateString(\"Awesome 4K\");\n67:     if (name == NULL)\n68:     {\n69:         goto end;\n70:     }\n71:     /* after creation was successful, immediately add it to the monitor,\n72:      * thereby transferring ownership of the pointer to it */\n73:     cJSON_AddItemToObject(monitor, \"name\", name);\n74: \n75:     resolutions = cJSON_CreateArray();\n76:     if (resolutions == NULL)\n77:     {\n78:         goto end;\n79:     }\n80:     cJSON_AddItemToObject(monitor, \"resolutions\", resolutions);\n81: \n82:     for (index = 0; index < (sizeof(resolution_numbers) / (2 * sizeof(int))); ++index)\n83:     {\n84:         resolution = cJSON_CreateObject();\n85:         if (resolution == NULL)\n86:         {\n87:             goto end;\n88:         }\n89:         cJSON_AddItemToArray(resolutions, resolution);\n90: \n91:         width = cJSON_CreateNumber(resolution_numbers[index][0]);\n92:         if (width == NULL)\n93:         {\n94:             goto end;\n95:         }\n96:         cJSON_AddItemToObject(resolution, \"width\", width);\n97: \n98:         height = cJSON_CreateNumber(resolution_numbers[index][1]);\n99:         if (height == NULL)\n100:         {\n101:             goto end;\n102:         }\n103:         cJSON_AddItemToObject(resolution, \"height\", height);\n104:     }\n105: \n106:     string = cJSON_Print(monitor);\n107:     if (string == NULL)\n108:     {\n109:         fprintf(stderr, \"Failed to print monitor.\\n\");\n110:     }\n111: \n112: end:\n113:     cJSON_Delete(monitor);\n114:     return string;\n115: }\n116: ",
        "assertion_lines": [],
        "literal_samples": [
          "\"Awesome 4K\"",
          "\"name\"",
          "\"resolutions\"",
          "\"width\"",
          "\"height\"",
          "\"Failed to print monitor.\\n\"",
          "65",
          "66",
          "67",
          "68",
          "69",
          "70",
          "71",
          "72",
          "73",
          "74",
          "75",
          "76",
          "77",
          "78",
          "79",
          "80",
          "81",
          "82",
          "0",
          "2",
          "83",
          "84"
        ]
      },
      {
        "path": "tests/old_utils_tests.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "json_pointer_tests"
          },
          {
            "framework": "unity",
            "name": "misc_tests"
          },
          {
            "framework": "unity",
            "name": "sort_tests"
          },
          {
            "framework": "unity",
            "name": "merge_tests"
          },
          {
            "framework": "unity",
            "name": "generate_merge_tests"
          }
        ],
        "snippet": "97:     cJSON *nums = NULL;\n98:     cJSON *num6 = NULL;\n99:     char *pointer = NULL;\n100: \n101:     printf(\"JSON Pointer construct\\n\");\n102:     object = cJSON_CreateObject();\n103:     nums = cJSON_CreateIntArray(numbers, 10);\n104:     num6 = cJSON_GetArrayItem(nums, 6);\n105:     cJSON_AddItemToObject(object, \"numbers\", nums);\n106: \n107:     pointer = cJSONUtils_FindPointerFromObjectTo(object, num6);\n108:     TEST_ASSERT_EQUAL_STRING(\"/numbers/6\", pointer);\n109:     free(pointer);\n110: \n111:     pointer = cJSONUtils_FindPointerFromObjectTo(object, nums);\n112:     TEST_ASSERT_EQUAL_STRING(\"/numbers\", pointer);\n113:     free(pointer);\n114: \n115:     pointer = cJSONUtils_FindPointerFromObjectTo(object, object);\n116:     TEST_ASSERT_EQUAL_STRING(\"\", pointer);\n117:     free(pointer);\n118: \n119:     object1 = cJSON_CreateObject();\n120:     object2 = cJSON_CreateString(\"m~n\");\n121:     cJSON_AddItemToObject(object1, \"m~n\", object2);\n122:     pointer = cJSONUtils_FindPointerFromObjectTo(object1, object2);\n123:     TEST_ASSERT_EQUAL_STRING(\"/m~0n\",pointer);\n124:     free(pointer);\n125: \n126:     object3 = cJSON_CreateObject();\n127:     object4 = cJSON_CreateString(\"m/n\");\n128:     cJSON_AddItemToObject(object3, \"m/n\", object4);\n129:     pointer = cJSONUtils_FindPointerFromObjectTo(object3, object4);\n130:     TEST_ASSERT_EQUAL_STRING(\"/m~1n\",pointer);\n131:     free(pointer);\n132: \n133:     cJSON_Delete(object);\n134:     cJSON_Delete(object1);\n135:     cJSON_Delete(object3);\n136: }\n137: \n138: static void sort_tests(void)\n139: {\n140:     /* Misc tests */\n141:     const char *random = ",
        "assertion_lines": [
          "108:     TEST_ASSERT_EQUAL_STRING(\"/numbers/6\", pointer);",
          "112:     TEST_ASSERT_EQUAL_STRING(\"/numbers\", pointer);",
          "116:     TEST_ASSERT_EQUAL_STRING(\"\", pointer);",
          "123:     TEST_ASSERT_EQUAL_STRING(\"/m~0n\",pointer);",
          "130:     TEST_ASSERT_EQUAL_STRING(\"/m~1n\",pointer);"
        ],
        "literal_samples": [
          "\"JSON Pointer construct\\n\"",
          "\"numbers\"",
          "\"/numbers/6\"",
          "\"/numbers\"",
          "\"\"",
          "\"m~n\"",
          "\"/m~0n\"",
          "\"m/n\"",
          "\"/m~1n\"",
          "97",
          "98",
          "99",
          "100",
          "101",
          "102",
          "103",
          "10",
          "104",
          "6",
          "105",
          "106",
          "107",
          "108",
          "109",
          "110",
          "111",
          "112",
          "113"
        ]
      }
    ],
    "cJSON.c::cJSON_AddItemToObjectCS": [
      {
        "path": "tests/misc_tests.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_loop_over_arrays"
          },
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_not_dereference_null_pointer"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "typecheck_functions_should_check_type"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_parse_to_deeply_nested_jsons"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_follow_too_deep_circular_references"
          },
          {
            "framework": "unity",
            "name": "cjson_set_number_value_should_set_numbers"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_detach_items"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_return_null_if_item_prev_is_null"
          }
        ],
        "snippet": "432:     TEST_ASSERT_NULL(cJSON_CreateFloatArray(NULL, 10));\n433:     TEST_ASSERT_NULL(cJSON_CreateDoubleArray(NULL, 10));\n434:     TEST_ASSERT_NULL(cJSON_CreateStringArray(NULL, 10));\n435:     cJSON_AddItemToArray(NULL, item);\n436:     cJSON_AddItemToArray(item, NULL);\n437:     cJSON_AddItemToObject(item, \"item\", NULL);\n438:     cJSON_AddItemToObject(item, NULL, item);\n439:     cJSON_AddItemToObject(NULL, \"item\", item);\n440:     cJSON_AddItemToObjectCS(item, \"item\", NULL);\n441:     cJSON_AddItemToObjectCS(item, NULL, item);\n442:     cJSON_AddItemToObjectCS(NULL, \"item\", item);\n443:     cJSON_AddItemReferenceToArray(NULL, item);\n444:     cJSON_AddItemReferenceToArray(item, NULL);\n445:     cJSON_AddItemReferenceToObject(item, \"item\", NULL);\n446:     cJSON_AddItemReferenceToObject(item, NULL, item);\n447:     cJSON_AddItemReferenceToObject(NULL, \"item\", item);\n448:     TEST_ASSERT_NULL(cJSON_DetachItemViaPointer(NULL, item));\n449:     TEST_ASSERT_NULL(cJSON_DetachItemViaPointer(item, NULL));\n450:     TEST_ASSERT_NULL(cJSON_DetachItemFromArray(NULL, 0));\n451:     cJSON_DeleteItemFromArray(NULL, 0);\n452:     TEST_ASSERT_NULL(cJSON_DetachItemFromObject(NULL, \"item\"));\n453:     TEST_ASSERT_NULL(cJSON_DetachItemFromObject(item, NULL));\n454:     TEST_ASSERT_NULL(cJSON_DetachItemFromObjectCaseSensitive(NULL, \"item\"));\n455:     TEST_ASSERT_NULL(cJSON_DetachItemFromObjectCaseSensitive(item, NULL));\n...\n588: {\n589:     cJSON *number_reference = NULL;\n590:     cJSON *number_object = cJSON_CreateObject();\n591:     cJSON *number = cJSON_CreateNumber(42);\n592:     const char key[] = \"number",
        "assertion_lines": [
          "432:     TEST_ASSERT_NULL(cJSON_CreateFloatArray(NULL, 10));",
          "433:     TEST_ASSERT_NULL(cJSON_CreateDoubleArray(NULL, 10));",
          "434:     TEST_ASSERT_NULL(cJSON_CreateStringArray(NULL, 10));",
          "448:     TEST_ASSERT_NULL(cJSON_DetachItemViaPointer(NULL, item));",
          "449:     TEST_ASSERT_NULL(cJSON_DetachItemViaPointer(item, NULL));",
          "450:     TEST_ASSERT_NULL(cJSON_DetachItemFromArray(NULL, 0));",
          "452:     TEST_ASSERT_NULL(cJSON_DetachItemFromObject(NULL, \"item\"));",
          "453:     TEST_ASSERT_NULL(cJSON_DetachItemFromObject(item, NULL));",
          "454:     TEST_ASSERT_NULL(cJSON_DetachItemFromObjectCaseSensitive(NULL, \"item\"));",
          "455:     TEST_ASSERT_NULL(cJSON_DetachItemFromObjectCaseSensitive(item, NULL));"
        ],
        "literal_samples": [
          "\"item\"",
          "432",
          "10",
          "433",
          "434",
          "435",
          "436",
          "437",
          "438",
          "439",
          "440",
          "441",
          "442",
          "443",
          "444",
          "445",
          "446",
          "447",
          "448",
          "449",
          "450",
          "0",
          "451",
          "452",
          "453",
          "454",
          "455",
          "588"
        ]
      }
    ],
    "cJSON.c::cJSON_AddNumberToObject": [
      {
        "path": "test.c",
        "frameworks": [],
        "candidate_test_cases": [],
        "snippet": "164: \n165:     /* Here we construct some JSON standards, from the JSON site. */\n166: \n167:     /* Our \"Video\" datatype: */\n168:     root = cJSON_CreateObject();\n169:     cJSON_AddItemToObject(root, \"name\", cJSON_CreateString(\"Jack (\\\"Bee\\\") Nimble\"));\n170:     cJSON_AddItemToObject(root, \"format\", fmt = cJSON_CreateObject());\n171:     cJSON_AddStringToObject(fmt, \"type\", \"rect\");\n172:     cJSON_AddNumberToObject(fmt, \"width\", 1920);\n173:     cJSON_AddNumberToObject(fmt, \"height\", 1080);\n174:     cJSON_AddFalseToObject (fmt, \"interlace\");\n175:     cJSON_AddNumberToObject(fmt, \"frame rate\", 24);\n176: \n177:     /* Print to text */\n178:     if (print_preallocated(root) != 0) {\n179:         cJSON_Delete(root);\n180:         exit(EXIT_FAILURE);\n181:     }\n182:     cJSON_Delete(root);\n183: \n184:     /* Our \"days of the week\" array: */\n185:     root = cJSON_CreateStringArray(strings, 7);\n186: \n187:     if (print_preallocated(root) != 0) {\n188:         cJSON_Delete(root);\n...\n203:         cJSON_Delete(root);\n204:         exit(EXIT_FAILURE);\n205:     }\n206:     cJSON_Delete(root);\n207: \n208:     /* Our \"gallery\" item: */\n209:     root = cJSON_CreateObject();\n210:     cJSON_AddItemToObject(root, \"Image\", img = cJSON_CreateObject());\n211:     cJSON_AddNumberToObject(img, \"Width\", 800);\n212:     cJSON_AddNumberToObject(img, \"Height\", 600);\n213:     cJSON_AddStringToObject(img, \"Title\", \"View from 15th Floor\");\n214:     cJSON_AddItemToObject(img, \"Thumbnail\", thm = cJSON_CreateObject());\n215:     cJSON_AddStringToObject(thm, \"Url\", \"http:/*www.example.com/image/481989943\");\n216:     cJSON",
        "assertion_lines": [],
        "literal_samples": [
          "\"Video\"",
          "\"name\"",
          "\"Jack (\\\"Bee\\\") Nimble\"",
          "\"format\"",
          "\"type\"",
          "\"rect\"",
          "\"width\"",
          "\"height\"",
          "\"interlace\"",
          "\"frame rate\"",
          "\"days of the week\"",
          "\"gallery\"",
          "\"Image\"",
          "\"Width\"",
          "\"Height\"",
          "\"Title\"",
          "\"View from 15th Floor\"",
          "\"Thumbnail\"",
          "\"Url\"",
          "\"http:/*www.example.com/image/481989943\"",
          "164",
          "165",
          "166",
          "167",
          "168",
          "169",
          "170",
          "171"
        ]
      },
      {
        "path": "tests/readme_examples.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "create_monitor_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "create_monitor_with_helpers_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "supports_full_hd_should_check_for_full_hd_support"
          }
        ],
        "snippet": "137:     {\n138:         goto end;\n139:     }\n140: \n141:     for (index = 0; index < (sizeof(resolution_numbers) / (2 * sizeof(int))); ++index)\n142:     {\n143:         cJSON *resolution = cJSON_CreateObject();\n144: \n145:         if (cJSON_AddNumberToObject(resolution, \"width\", resolution_numbers[index][0]) == NULL)\n146:         {\n147:             goto end;\n148:         }\n149: \n150:         if(cJSON_AddNumberToObject(resolution, \"height\", resolution_numbers[index][1]) == NULL)\n151:         {\n152:             goto end;\n153:         }\n154: \n155:         cJSON_AddItemToArray(resolutions, resolution);\n156:     }\n157: \n158:     string = cJSON_Print(monitor);\n159:     if (string == NULL) {\n160:         fprintf(stderr, \"Failed to print monitor.\\n\");\n161:     }\n162: \n163: end:",
        "assertion_lines": [],
        "literal_samples": [
          "\"width\"",
          "\"height\"",
          "\"Failed to print monitor.\\n\"",
          "137",
          "138",
          "139",
          "140",
          "141",
          "0",
          "2",
          "142",
          "143",
          "144",
          "145",
          "146",
          "147",
          "148",
          "149",
          "150",
          "1",
          "151",
          "152",
          "153",
          "154",
          "155",
          "156",
          "157",
          "158"
        ]
      },
      {
        "path": "tests/cjson_add.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_add_null_should_add_null"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_add_true"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_int_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_float_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_double_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_string_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_add_false"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_fail_with_null_pointers"
          }
        ],
        "snippet": "239:     cJSON_Delete(root);\n240: }\n241: \n242: static void cjson_add_number_should_add_number(void)\n243: {\n244:     cJSON *root = cJSON_CreateObject();\n245:     cJSON *number = NULL;\n246: \n247:     cJSON_AddNumberToObject(root, \"number\", 42);\n248: \n249:     TEST_ASSERT_NOT_NULL(number = cJSON_GetObjectItemCaseSensitive(root, \"number\"));\n250: \n251:     TEST_ASSERT_EQUAL_INT(number->type, cJSON_Number);\n252:     TEST_ASSERT_EQUAL_DOUBLE(number->valuedouble, 42);\n253:     TEST_ASSERT_EQUAL_INT(number->valueint, 42);\n254: \n255:     cJSON_Delete(root);\n256: }\n257: \n258: static void cjson_add_number_should_fail_with_null_pointers(void)\n259: {\n260:     cJSON *root = cJSON_CreateObject();\n261: \n262:     TEST_ASSERT_NULL(cJSON_AddNumberToObject(NULL, \"number\", 42));\n263:     TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, NULL, 42));\n264: \n265:     cJSON_Delete(root);\n266: }\n267: \n268: static void cjson_add_number_should_fail_on_allocation_failure(void)\n269: {\n270:     cJSON *root = cJSON_CreateObject();\n271: \n272:     cJSON_InitHooks(&failing_hooks);\n273: \n274:     TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, \"number\", 42));\n275: \n276:     cJSON_InitHooks(NULL);\n277: \n278:     cJSON_Delete(root);\n279: }\n280: \n281: static void cjson_add_string_should_add_string(void)\n282: {\n283:     cJSON *root = cJSON_CreateObject();\n284:     cJSON *string = NULL;\n285: \n286:     cJSON_AddStringToObject(root, \"string\", \"Hello World!\");\n287: ",
        "assertion_lines": [
          "249:     TEST_ASSERT_NOT_NULL(number = cJSON_GetObjectItemCaseSensitive(root, \"number\"));",
          "251:     TEST_ASSERT_EQUAL_INT(number->type, cJSON_Number);",
          "252:     TEST_ASSERT_EQUAL_DOUBLE(number->valuedouble, 42);",
          "253:     TEST_ASSERT_EQUAL_INT(number->valueint, 42);",
          "262:     TEST_ASSERT_NULL(cJSON_AddNumberToObject(NULL, \"number\", 42));",
          "263:     TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, NULL, 42));",
          "274:     TEST_ASSERT_NULL(cJSON_AddNumberToObject(root, \"number\", 42));"
        ],
        "literal_samples": [
          "\"number\"",
          "\"string\"",
          "\"Hello World!\"",
          "239",
          "240",
          "241",
          "242",
          "243",
          "244",
          "245",
          "246",
          "247",
          "42",
          "248",
          "249",
          "250",
          "251",
          "252",
          "253",
          "254",
          "255",
          "256",
          "257",
          "258",
          "259",
          "260",
          "261",
          "262"
        ]
      }
    ],
    "cJSON.c::cJSON_AddObjectToObject": [
      {
        "path": "tests/cjson_add.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_add_null_should_add_null"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_add_true"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_int_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_float_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_double_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_string_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_add_false"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_fail_with_null_pointers"
          }
        ],
        "snippet": "352:     cJSON_Delete(root);\n353: }\n354: \n355: static void cJSON_add_object_should_add_object(void)\n356: {\n357:     cJSON *root = cJSON_CreateObject();\n358:     cJSON *object = NULL;\n359: \n360:     cJSON_AddObjectToObject(root, \"object\");\n361:     TEST_ASSERT_NOT_NULL(object = cJSON_GetObjectItemCaseSensitive(root, \"object\"));\n362:     TEST_ASSERT_EQUAL_INT(object->type, cJSON_Object);\n363: \n364:     cJSON_Delete(root);\n365: }\n366: \n367: static void cjson_add_object_should_fail_with_null_pointers(void)\n368: {\n369:     cJSON *root = cJSON_CreateObject();\n370: \n371:     TEST_ASSERT_NULL(cJSON_AddObjectToObject(NULL, \"object\"));\n372:     TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, NULL));\n373: \n374:     cJSON_Delete(root);\n375: }\n376: \n377: static void cjson_add_object_should_fail_on_allocation_failure(void)\n378: {\n379:     cJSON *root = cJSON_CreateObject();\n380: \n381:     cJSON_InitHooks(&failing_hooks);\n382: \n383:     TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, \"object\"));\n384: \n385:     cJSON_InitHooks(NULL);\n386: \n387:     cJSON_Delete(root);\n388: }\n389: \n390: static void cJSON_add_array_should_add_array(void)\n391: {\n392:     cJSON *root = cJSON_CreateObject();\n393:     cJSON *array = NULL;\n394: \n395:     cJSON_AddArrayToObject(root, \"array\");\n396:     TEST_ASSERT_NOT_NULL(array = cJSON_GetObjectItemCaseSensitive(root, \"array\"));",
        "assertion_lines": [
          "361:     TEST_ASSERT_NOT_NULL(object = cJSON_GetObjectItemCaseSensitive(root, \"object\"));",
          "362:     TEST_ASSERT_EQUAL_INT(object->type, cJSON_Object);",
          "371:     TEST_ASSERT_NULL(cJSON_AddObjectToObject(NULL, \"object\"));",
          "372:     TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, NULL));",
          "383:     TEST_ASSERT_NULL(cJSON_AddObjectToObject(root, \"object\"));",
          "396:     TEST_ASSERT_NOT_NULL(array = cJSON_GetObjectItemCaseSensitive(root, \"array\"));"
        ],
        "literal_samples": [
          "\"object\"",
          "\"array\"",
          "352",
          "353",
          "354",
          "355",
          "356",
          "357",
          "358",
          "359",
          "360",
          "361",
          "362",
          "363",
          "364",
          "365",
          "366",
          "367",
          "368",
          "369",
          "370",
          "371",
          "372",
          "373",
          "374",
          "375",
          "376",
          "377"
        ]
      }
    ],
    "cJSON.c::cJSON_AddStringToObject": [
      {
        "path": "test.c",
        "frameworks": [],
        "candidate_test_cases": [],
        "snippet": "163:     volatile double zero = 0.0;\n164: \n165:     /* Here we construct some JSON standards, from the JSON site. */\n166: \n167:     /* Our \"Video\" datatype: */\n168:     root = cJSON_CreateObject();\n169:     cJSON_AddItemToObject(root, \"name\", cJSON_CreateString(\"Jack (\\\"Bee\\\") Nimble\"));\n170:     cJSON_AddItemToObject(root, \"format\", fmt = cJSON_CreateObject());\n171:     cJSON_AddStringToObject(fmt, \"type\", \"rect\");\n172:     cJSON_AddNumberToObject(fmt, \"width\", 1920);\n173:     cJSON_AddNumberToObject(fmt, \"height\", 1080);\n174:     cJSON_AddFalseToObject (fmt, \"interlace\");\n175:     cJSON_AddNumberToObject(fmt, \"frame rate\", 24);\n176: \n177:     /* Print to text */\n178:     if (print_preallocated(root) != 0) {\n179:         cJSON_Delete(root);\n180:         exit(EXIT_FAILURE);\n181:     }\n182:     cJSON_Delete(root);\n183: \n184:     /* Our \"days of the week\" array: */\n...\n205:     }\n206:     cJSON_Delete(root);\n207: \n208:     /* Our \"gallery\" item: */\n209:     root = cJSON_CreateObject();\n210:     cJSON_AddItemToObject(root, \"Image\", img = cJSON_CreateObject());\n211:     cJSON_AddNumberToObject(img, \"Width\", 800);\n212:     cJSON_AddNumberToObject(img, \"Height\", 600);\n213:     cJSON_AddStringToObject(img, \"Title\", \"View from 15th Floor\");\n214:     cJSON_AddItemToObject(img, \"Thumbnail\", thm = cJSON_CreateObject());\n215:     cJSON_AddStringToObject(thm, \"Url\", \"http:/*www.example.com/image/481989943\");\n216:     cJSON_AddNumberToObject(thm, \"Height\", 125);\n217:     cJSON_AddStringToObject(thm, \"Width\", \"100\");\n218:     cJSON_AddItemToObject(img, \"IDs\", cJSON_CreateIntArray(ids, 4))",
        "assertion_lines": [],
        "literal_samples": [
          "\"Video\"",
          "\"name\"",
          "\"Jack (\\\"Bee\\\") Nimble\"",
          "\"format\"",
          "\"type\"",
          "\"rect\"",
          "\"width\"",
          "\"height\"",
          "\"interlace\"",
          "\"frame rate\"",
          "\"days of the week\"",
          "\"gallery\"",
          "\"Image\"",
          "\"Width\"",
          "\"Height\"",
          "\"Title\"",
          "\"View from 15th Floor\"",
          "\"Thumbnail\"",
          "\"Url\"",
          "\"http:/*www.example.com/image/481989943\"",
          "\"100\"",
          "\"IDs\"",
          "163",
          "0.0",
          "164",
          "165",
          "166",
          "167"
        ]
      },
      {
        "path": "tests/readme_examples.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "create_monitor_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "create_monitor_with_helpers_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "supports_full_hd_should_check_for_full_hd_support"
          }
        ],
        "snippet": "122:         {3840, 2160}\n123:     };\n124:     char *string = NULL;\n125:     cJSON *resolutions = NULL;\n126:     size_t index = 0;\n127: \n128:     cJSON *monitor = cJSON_CreateObject();\n129: \n130:     if (cJSON_AddStringToObject(monitor, \"name\", \"Awesome 4K\") == NULL)\n131:     {\n132:         goto end;\n133:     }\n134: \n135:     resolutions = cJSON_AddArrayToObject(monitor, \"resolutions\");\n136:     if (resolutions == NULL)\n137:     {\n138:         goto end;\n139:     }\n140: \n141:     for (index = 0; index < (sizeof(resolution_numbers) / (2 * sizeof(int))); ++index)\n142:     {\n143:         cJSON *resolution = cJSON_CreateObject();",
        "assertion_lines": [],
        "literal_samples": [
          "\"name\"",
          "\"Awesome 4K\"",
          "\"resolutions\"",
          "122",
          "3840",
          "2160",
          "123",
          "124",
          "125",
          "126",
          "0",
          "127",
          "128",
          "129",
          "130",
          "131",
          "132",
          "133",
          "134",
          "135",
          "136",
          "137",
          "138",
          "139",
          "140",
          "141",
          "2",
          "142"
        ]
      },
      {
        "path": "tests/cjson_add.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_add_null_should_add_null"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_add_true"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_int_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_float_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_double_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_string_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_add_false"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_fail_with_null_pointers"
          }
        ],
        "snippet": "278:     cJSON_Delete(root);\n279: }\n280: \n281: static void cjson_add_string_should_add_string(void)\n282: {\n283:     cJSON *root = cJSON_CreateObject();\n284:     cJSON *string = NULL;\n285: \n286:     cJSON_AddStringToObject(root, \"string\", \"Hello World!\");\n287: \n288:     TEST_ASSERT_NOT_NULL(string = cJSON_GetObjectItemCaseSensitive(root, \"string\"));\n289:     TEST_ASSERT_EQUAL_INT(string->type, cJSON_String);\n290:     TEST_ASSERT_EQUAL_STRING(string->valuestring, \"Hello World!\");\n291: \n292:     cJSON_Delete(root);\n293: }\n294: \n295: static void cjson_add_string_should_fail_with_null_pointers(void)\n296: {\n297:     cJSON *root = cJSON_CreateObject();\n298: \n299:     TEST_ASSERT_NULL(cJSON_AddStringToObject(NULL, \"string\", \"string\"));\n300:     TEST_ASSERT_NULL(cJSON_AddStringToObject(root, NULL, \"string\"));\n301: \n302:     cJSON_Delete(root);\n303: }\n304: \n305: static void cjson_add_string_should_fail_on_allocation_failure(void)\n306: {\n307:     cJSON *root = cJSON_CreateObject();\n308: \n309:     cJSON_InitHooks(&failing_hooks);\n310: \n311:     TEST_ASSERT_NULL(cJSON_AddStringToObject(root, \"string\", \"string\"));\n312: \n313:     cJSON_InitHooks(NULL);\n314: \n315:     cJSON_Delete(root);\n316: }\n317: \n318: static void cjson_add_raw_should_add_raw(void)\n319: {\n320:     cJSON *root = cJSON_CreateObject();\n321:     cJSON *raw = NULL;\n322: \n323:     cJSON_AddRawToObject(root, \"raw\", \"{}\");\n324: ",
        "assertion_lines": [
          "288:     TEST_ASSERT_NOT_NULL(string = cJSON_GetObjectItemCaseSensitive(root, \"string\"));",
          "289:     TEST_ASSERT_EQUAL_INT(string->type, cJSON_String);",
          "290:     TEST_ASSERT_EQUAL_STRING(string->valuestring, \"Hello World!\");",
          "299:     TEST_ASSERT_NULL(cJSON_AddStringToObject(NULL, \"string\", \"string\"));",
          "300:     TEST_ASSERT_NULL(cJSON_AddStringToObject(root, NULL, \"string\"));",
          "311:     TEST_ASSERT_NULL(cJSON_AddStringToObject(root, \"string\", \"string\"));"
        ],
        "literal_samples": [
          "\"string\"",
          "\"Hello World!\"",
          "\"raw\"",
          "\"{}\"",
          "278",
          "279",
          "280",
          "281",
          "282",
          "283",
          "284",
          "285",
          "286",
          "287",
          "288",
          "289",
          "290",
          "291",
          "292",
          "293",
          "294",
          "295",
          "296",
          "297",
          "298",
          "299",
          "300",
          "301"
        ]
      }
    ],
    "cJSON.c::cJSON_AddTrueToObject": [
      {
        "path": "tests/cjson_add.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_add_null_should_add_null"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_null_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_add_true"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_with_null_pointers"
          },
          {
            "framework": "unity",
            "name": "cjson_add_true_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_int_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_float_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_double_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_create_string_array_should_fail_on_allocation_failure"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_add_false"
          },
          {
            "framework": "unity",
            "name": "cjson_add_false_should_fail_with_null_pointers"
          }
        ],
        "snippet": "81:     cJSON_Delete(root);\n82: }\n83: \n84: static void cjson_add_true_should_add_true(void)\n85: {\n86:     cJSON *root = cJSON_CreateObject();\n87:     cJSON *true_item = NULL;\n88: \n89:     cJSON_AddTrueToObject(root, \"true\");\n90: \n91:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));\n92:     TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);\n93: \n94:     cJSON_Delete(root);\n95: }\n96: \n97: static void cjson_add_true_should_fail_with_null_pointers(void)\n98: {\n99:     cJSON *root = cJSON_CreateObject();\n100: \n101:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(NULL, \"true\"));\n102:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, NULL));\n103: \n104:     cJSON_Delete(root);\n105: }\n106: \n107: static void cjson_add_true_should_fail_on_allocation_failure(void)\n108: {\n109:     cJSON *root = cJSON_CreateObject();\n110: \n111:     cJSON_InitHooks(&failing_hooks);\n112: \n113:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, \"true\"));\n114: \n115:     cJSON_InitHooks(NULL);\n116: \n117:     cJSON_Delete(root);\n118: }\n119: \n120: static void cjson_create_int_array_should_fail_on_allocation_failure(void)\n121: {\n122:     int numbers[] = {1, 2, 3};\n123: \n124:     cJSON_InitHooks(&failing_hooks);\n125: \n126:     TEST_ASSERT_NULL(cJSON_CreateIntArray(numbers, 3));",
        "assertion_lines": [
          "91:     TEST_ASSERT_NOT_NULL(true_item = cJSON_GetObjectItemCaseSensitive(root, \"true\"));",
          "92:     TEST_ASSERT_EQUAL_INT(true_item->type, cJSON_True);",
          "101:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(NULL, \"true\"));",
          "102:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, NULL));",
          "113:     TEST_ASSERT_NULL(cJSON_AddTrueToObject(root, \"true\"));",
          "126:     TEST_ASSERT_NULL(cJSON_CreateIntArray(numbers, 3));"
        ],
        "literal_samples": [
          "\"true\"",
          "81",
          "82",
          "83",
          "84",
          "85",
          "86",
          "87",
          "88",
          "89",
          "90",
          "91",
          "92",
          "93",
          "94",
          "95",
          "96",
          "97",
          "98",
          "99",
          "100",
          "101",
          "102",
          "103",
          "104",
          "105",
          "106",
          "107"
        ]
      }
    ],
    "cJSON.c::cJSON_CreateArray": [
      {
        "path": "test.c",
        "frameworks": [],
        "candidate_test_cases": [],
        "snippet": "186: \n187:     if (print_preallocated(root) != 0) {\n188:         cJSON_Delete(root);\n189:         exit(EXIT_FAILURE);\n190:     }\n191:     cJSON_Delete(root);\n192: \n193:     /* Our matrix: */\n194:     root = cJSON_CreateArray();\n195:     for (i = 0; i < 3; i++)\n196:     {\n197:         cJSON_AddItemToArray(root, cJSON_CreateIntArray(numbers[i], 3));\n198:     }\n199: \n200:     /* cJSON_ReplaceItemInArray(root, 1, cJSON_CreateString(\"Replacement\")); */\n201: \n202:     if (print_preallocated(root) != 0) {\n203:         cJSON_Delete(root);\n204:         exit(EXIT_FAILURE);\n205:     }\n206:     cJSON_Delete(root);\n207: \n...\n219: \n220:     if (print_preallocated(root) != 0) {\n221:         cJSON_Delete(root);\n222:         exit(EXIT_FAILURE);\n223:     }\n224:     cJSON_Delete(root);\n225: \n226:     /* Our array of \"records\": */\n227:     root = cJSON_CreateArray();\n228:     for (i = 0; i < 2; i++)\n229:     {\n230:         cJSON_AddItemToArray(root, fld = cJSON_CreateObject());\n231:         cJSON_AddStringToObject(fld, \"precision\", fields[i].precision);\n232:         cJSON_AddNumberToObject(fld, \"Latitude\", fields[i].lat);\n233:         cJSON_AddNumberToObject(fld, \"Longitude\", fields[i].lon);\n234:         cJSON_AddStringToObject(fld, \"Address\", fields[i].address);\n235:         cJSON_AddStringToObject(fld, \"City\", fields[i].city);\n236:         cJSON_AddStringToObject(fld, \"State\", fields[i].state);\n237:         cJSON_AddStringToObject(fld, \"Zip\", fields[i].zip);\n238:         cJSON_AddStringToObject(fld, \"Country\", fields[i].country);\n239:     }\n240: ",
        "assertion_lines": [],
        "literal_samples": [
          "\"Replacement\"",
          "\"records\"",
          "\"precision\"",
          "\"Latitude\"",
          "\"Longitude\"",
          "\"Address\"",
          "\"City\"",
          "\"State\"",
          "\"Zip\"",
          "\"Country\"",
          "186",
          "187",
          "0",
          "188",
          "189",
          "190",
          "191",
          "192",
          "193",
          "194",
          "195",
          "3",
          "196",
          "197",
          "198",
          "199",
          "200",
          "1"
        ]
      },
      {
        "path": "tests/readme_examples.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "create_monitor_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "create_monitor_with_helpers_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "supports_full_hd_should_check_for_full_hd_support"
          }
        ],
        "snippet": "67:     if (name == NULL)\n68:     {\n69:         goto end;\n70:     }\n71:     /* after creation was successful, immediately add it to the monitor,\n72:      * thereby transferring ownership of the pointer to it */\n73:     cJSON_AddItemToObject(monitor, \"name\", name);\n74: \n75:     resolutions = cJSON_CreateArray();\n76:     if (resolutions == NULL)\n77:     {\n78:         goto end;\n79:     }\n80:     cJSON_AddItemToObject(monitor, \"resolutions\", resolutions);\n81: \n82:     for (index = 0; index < (sizeof(resolution_numbers) / (2 * sizeof(int))); ++index)\n83:     {\n84:         resolution = cJSON_CreateObject();\n85:         if (resolution == NULL)\n86:         {\n87:             goto end;\n88:         }",
        "assertion_lines": [],
        "literal_samples": [
          "\"name\"",
          "\"resolutions\"",
          "67",
          "68",
          "69",
          "70",
          "71",
          "72",
          "73",
          "74",
          "75",
          "76",
          "77",
          "78",
          "79",
          "80",
          "81",
          "82",
          "0",
          "2",
          "83",
          "84",
          "85",
          "86",
          "87",
          "88"
        ]
      },
      {
        "path": "tests/misc_tests.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_loop_over_arrays"
          },
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_not_dereference_null_pointer"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "typecheck_functions_should_check_type"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_parse_to_deeply_nested_jsons"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_follow_too_deep_circular_references"
          },
          {
            "framework": "unity",
            "name": "cjson_set_number_value_should_set_numbers"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_detach_items"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_return_null_if_item_prev_is_null"
          }
        ],
        "snippet": "217:     }\n218:     deep_json[sizeof(deep_json) - 1] = '\\0';\n219: \n220:     TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(deep_json), \"To deep JSONs should not be parsed.\");\n221: }\n222: \n223: static void cjson_should_not_follow_too_deep_circular_references(void)\n224: {\n225:     cJSON *o = cJSON_CreateArray();\n226:     cJSON *a = cJSON_CreateArray();\n227:     cJSON *b = cJSON_CreateArray();\n228:     cJSON *x;\n229: \n230:     cJSON_AddItemToArray(o, a);\n231:     cJSON_AddItemToArray(a, b);\n232:     cJSON_AddItemToArray(b, o);\n233: \n234:     x = cJSON_Duplicate(o, 1);\n235:     TEST_ASSERT_NULL(x);\n236:     cJSON_DetachItemFromArray(b, 0);\n237:     cJSON_Delete(o);\n238: }\n239: \n240: static void cjson_set_number_value_should_set_numbers(void)\n...\n323: \n324:     beginning = cJSON_CreateNull();\n325:     TEST_ASSERT_NOT_NULL(beginning);\n326:     middle = cJSON_CreateNull();\n327:     TEST_ASSERT_NOT_NULL(middle);\n328:     end = cJSON_CreateNull();\n329:     TEST_ASSERT_NOT_NULL(end);\n330: \n331:     array = cJSON_CreateArray();\n332:     TEST_ASSERT_NOT_NULL(array);\n333: \n334:     cJSON_AddItemToArray(array, beginning);\n335:     cJSON_AddItemToArray(array, middle);\n336:     cJSON_AddItemToArray(array, end);\n337: \n338:     memset(replacements, '\\0', sizeof(replacements));\n339: \n340:     /* replace beginning */\n341:     TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, beginning, &(replacements[0])));\n342:     TEST_ASSERT_TRUE(replacements[0].prev == end);\n343:     TEST_ASSERT_TRUE(replacements[0].next == middle);\n344:     TEST_ASSERT_TRUE(middle->prev == &(replacements[0]));\n...\n380: \n381:     ",
        "assertion_lines": [
          "220:     TEST_ASSERT_NULL_MESSAGE(cJSON_Parse(deep_json), \"To deep JSONs should not be parsed.\");",
          "235:     TEST_ASSERT_NULL(x);",
          "325:     TEST_ASSERT_NOT_NULL(beginning);",
          "327:     TEST_ASSERT_NOT_NULL(middle);",
          "329:     TEST_ASSERT_NOT_NULL(end);",
          "332:     TEST_ASSERT_NOT_NULL(array);",
          "341:     TEST_ASSERT_TRUE(cJSON_ReplaceItemViaPointer(array, beginning, &(replacements[0])));",
          "342:     TEST_ASSERT_TRUE(replacements[0].prev == end);",
          "343:     TEST_ASSERT_TRUE(replacements[0].next == middle);",
          "344:     TEST_ASSERT_TRUE(middle->prev == &(replacements[0]));"
        ],
        "literal_samples": [
          "\"To deep JSONs should not be parsed.\"",
          "217",
          "218",
          "1",
          "0",
          "219",
          "220",
          "221",
          "222",
          "223",
          "224",
          "225",
          "226",
          "227",
          "228",
          "229",
          "230",
          "231",
          "232",
          "233",
          "234",
          "235",
          "236",
          "237",
          "238",
          "239",
          "240",
          "323"
        ]
      }
    ],
    "cJSON.c::cJSON_CreateObject": [
      {
        "path": "test.c",
        "frameworks": [],
        "candidate_test_cases": [],
        "snippet": "160:             \"US\"\n161:         }\n162:     };\n163:     volatile double zero = 0.0;\n164: \n165:     /* Here we construct some JSON standards, from the JSON site. */\n166: \n167:     /* Our \"Video\" datatype: */\n168:     root = cJSON_CreateObject();\n169:     cJSON_AddItemToObject(root, \"name\", cJSON_CreateString(\"Jack (\\\"Bee\\\") Nimble\"));\n170:     cJSON_AddItemToObject(root, \"format\", fmt = cJSON_CreateObject());\n171:     cJSON_AddStringToObject(fmt, \"type\", \"rect\");\n172:     cJSON_AddNumberToObject(fmt, \"width\", 1920);\n173:     cJSON_AddNumberToObject(fmt, \"height\", 1080);\n174:     cJSON_AddFalseToObject (fmt, \"interlace\");\n175:     cJSON_AddNumberToObject(fmt, \"frame rate\", 24);\n176: \n177:     /* Print to text */\n178:     if (print_preallocated(root) != 0) {\n179:         cJSON_Delete(root);\n180:         exit(EXIT_FAILURE);\n181:     }\n182:     cJSON_Delete(root);\n183: \n...\n201: \n202:     if (print_preallocated(root) != 0) {\n203:         cJSON_Delete(root);\n204:         exit(EXIT_FAILURE);\n205:     }\n206:     cJSON_Delete(root);\n207: \n208:     /* Our \"gallery\" item: */\n209:     root = cJSON_CreateObject();\n210:     cJSON_AddItemToObject(root, \"Image\", img = cJSON_CreateObject());\n211:     cJSON_AddNumberToObject(img, \"Width\", 800);\n212:     cJSON_AddNumberToObject(img, \"Height\", 600);\n213:     cJSON_AddStringToObject(img, \"Title\", \"View from 15th Floor\");\n214:     cJSON_AddItemToObject(img, \"Thumbnail\", thm = cJSON_CreateObject());\n215:     cJSON_AddStringToObject(thm, \"Url\", \"http:/*www.example.com/image/481989943\");\n216:     cJSON_AddNumberToObject(thm, \"Height\", 125);\n217: ",
        "assertion_lines": [],
        "literal_samples": [
          "\"US\"",
          "\"Video\"",
          "\"name\"",
          "\"Jack (\\\"Bee\\\") Nimble\"",
          "\"format\"",
          "\"type\"",
          "\"rect\"",
          "\"width\"",
          "\"height\"",
          "\"interlace\"",
          "\"frame rate\"",
          "\"gallery\"",
          "\"Image\"",
          "\"Width\"",
          "\"Height\"",
          "\"Title\"",
          "\"View from 15th Floor\"",
          "\"Thumbnail\"",
          "\"Url\"",
          "\"http:/*www.example.com/image/481989943\"",
          "160",
          "161",
          "162",
          "163",
          "0.0",
          "164",
          "165",
          "166"
        ]
      },
      {
        "path": "tests/readme_examples.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "create_monitor_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "create_monitor_with_helpers_should_create_a_monitor"
          },
          {
            "framework": "unity",
            "name": "supports_full_hd_should_check_for_full_hd_support"
          }
        ],
        "snippet": "52:     char *string = NULL;\n53:     cJSON *name = NULL;\n54:     cJSON *resolutions = NULL;\n55:     cJSON *resolution = NULL;\n56:     cJSON *width = NULL;\n57:     cJSON *height = NULL;\n58:     size_t index = 0;\n59: \n60:     cJSON *monitor = cJSON_CreateObject();\n61:     if (monitor == NULL)\n62:     {\n63:         goto end;\n64:     }\n65: \n66:     name = cJSON_CreateString(\"Awesome 4K\");\n67:     if (name == NULL)\n68:     {\n69:         goto end;\n70:     }\n71:     /* after creation was successful, immediately add it to the monitor,\n72:      * thereby transferring ownership of the pointer to it */\n73:     cJSON_AddItemToObject(monitor, \"name\", name);\n...\n76:     if (resolutions == NULL)\n77:     {\n78:         goto end;\n79:     }\n80:     cJSON_AddItemToObject(monitor, \"resolutions\", resolutions);\n81: \n82:     for (index = 0; index < (sizeof(resolution_numbers) / (2 * sizeof(int))); ++index)\n83:     {\n84:         resolution = cJSON_CreateObject();\n85:         if (resolution == NULL)\n86:         {\n87:             goto end;\n88:         }\n89:         cJSON_AddItemToArray(resolutions, resolution);\n90: \n91:         width = cJSON_CreateNumber(resolution_numbers[index][0]);\n92:         if (width == NULL)\n93:         {\n94:             goto end;\n95:         }\n96:         cJSON_AddItemToObject(resolution, \"width\", width);\n97: \n...\n120:         {1280, 720},\n121:         {1920, 1080},\n122:         {3840, 2160}\n123:     };\n124:     char *string = NULL;\n125:     cJSON *resolutions = NULL;\n126:     size_t index = 0;\n127: \n128:     cJSON *monitor = cJSON_CreateObject();\n129: \n130:     if (cJSON_Add",
        "assertion_lines": [],
        "literal_samples": [
          "\"Awesome 4K\"",
          "\"name\"",
          "\"resolutions\"",
          "\"width\"",
          "52",
          "53",
          "54",
          "55",
          "56",
          "57",
          "58",
          "0",
          "59",
          "60",
          "61",
          "62",
          "63",
          "64",
          "65",
          "66",
          "67",
          "68",
          "69",
          "70",
          "71",
          "72",
          "73",
          "76"
        ]
      }
    ],
    "cJSON.c::cJSON_DeleteItemFromArray": [
      {
        "path": "tests/misc_tests.c",
        "frameworks": [
          "unity"
        ],
        "candidate_test_cases": [
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_loop_over_arrays"
          },
          {
            "framework": "unity",
            "name": "cjson_array_foreach_should_not_dereference_null_pointer"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_get_object_items"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "cjson_get_object_item_case_sensitive_should_not_crash_with_array"
          },
          {
            "framework": "unity",
            "name": "typecheck_functions_should_check_type"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_parse_to_deeply_nested_jsons"
          },
          {
            "framework": "unity",
            "name": "cjson_should_not_follow_too_deep_circular_references"
          },
          {
            "framework": "unity",
            "name": "cjson_set_number_value_should_set_numbers"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_detach_items"
          },
          {
            "framework": "unity",
            "name": "cjson_detach_item_via_pointer_should_return_null_if_item_prev_is_null"
          }
        ],
        "snippet": "443:     cJSON_AddItemReferenceToArray(NULL, item);\n444:     cJSON_AddItemReferenceToArray(item, NULL);\n445:     cJSON_AddItemReferenceToObject(item, \"item\", NULL);\n446:     cJSON_AddItemReferenceToObject(item, NULL, item);\n447:     cJSON_AddItemReferenceToObject(NULL, \"item\", item);\n448:     TEST_ASSERT_NULL(cJSON_DetachItemViaPointer(NULL, item));\n449:     TEST_ASSERT_NULL(cJSON_DetachItemViaPointer(item, NULL));\n450:     TEST_ASSERT_NULL(cJSON_DetachItemFromArray(NULL, 0));\n451:     cJSON_DeleteItemFromArray(NULL, 0);\n452:     TEST_ASSERT_NULL(cJSON_DetachItemFromObject(NULL, \"item\"));\n453:     TEST_ASSERT_NULL(cJSON_DetachItemFromObject(item, NULL));\n454:     TEST_ASSERT_NULL(cJSON_DetachItemFromObjectCaseSensitive(NULL, \"item\"));\n455:     TEST_ASSERT_NULL(cJSON_DetachItemFromObjectCaseSensitive(item, NULL));\n456:     cJSON_DeleteItemFromObject(NULL, \"item\");\n457:     cJSON_DeleteItemFromObject(item, NULL);\n458:     cJSON_DeleteItemFromObjectCaseSensitive(NULL, \"item\");\n459:     cJSON_DeleteItemFromObjectCaseSensitive(item, NULL);\n460:     TEST_ASSERT_FALSE(cJSON_InsertItemInArray(array, 0, NULL));\n461:     TEST_ASSERT_FALSE(cJSON_InsertItemInArray(array, 1, item));\n462:     TEST_ASSERT_FALSE(cJSON_InsertItemInArray(NULL, 0, item));\n463:     TEST_ASSERT_FALSE(cJSON_InsertItemInArray(item, 0, NULL));\n464:     TEST_ASSERT_FALSE(cJSON_ReplaceItemViaPointer(NULL, item, item));\n...\n677:     free(str1);\n678: \n679:     cJSON_AddItemToArray(array, item2);\n680:     str2 = cJSON_PrintUnformatted(root);\n681:     TEST_ASSERT_EQUAL_STRING(expected_json2, str2);\n682:     free(str2);\n",
        "assertion_lines": [
          "448:     TEST_ASSERT_NULL(cJSON_DetachItemViaPointer(NULL, item));",
          "449:     TEST_ASSERT_NULL(cJSON_DetachItemViaPointer(item, NULL));",
          "450:     TEST_ASSERT_NULL(cJSON_DetachItemFromArray(NULL, 0));",
          "452:     TEST_ASSERT_NULL(cJSON_DetachItemFromObject(NULL, \"item\"));",
          "453:     TEST_ASSERT_NULL(cJSON_DetachItemFromObject(item, NULL));",
          "454:     TEST_ASSERT_NULL(cJSON_DetachItemFromObjectCaseSensitive(NULL, \"item\"));",
          "455:     TEST_ASSERT_NULL(cJSON_DetachItemFromObjectCaseSensitive(item, NULL));",
          "460:     TEST_ASSERT_FALSE(cJSON_InsertItemInArray(array, 0, NULL));",
          "461:     TEST_ASSERT_FALSE(cJSON_InsertItemInArray(array, 1, item));",
          "462:     TEST_ASSERT_FALSE(cJSON_InsertItemInArray(NULL, 0, item));",
          "463:     TEST_ASSERT_FALSE(cJSON_InsertItemInArray(item, 0, NULL));",
          "464:     TEST_ASSERT_FALSE(cJSON_ReplaceItemViaPointer(NULL, item, item));",
          "681:     TEST_ASSERT_EQUAL_STRING(expected_json2, str2);"
        ],
        "literal_samples": [
          "\"item\"",
          "443",
          "444",
          "445",
          "446",
          "447",
          "448",
          "449",
          "450",
          "0",
          "451",
          "452",
          "453",
          "454",
          "455",
          "456",
          "457",
          "458",
          "459",
          "460",
          "461",
          "1",
          "462",
          "463",
          "464",
          "677",
          "678",
          "679"
        ]
      }
    ]
  },
  "source_fixture_evidence": [
    {
      "path": ".travis.yml",
      "size_bytes": 630,
      "content_excerpt": "dist: trusty\nsudo: false\nlanguage: c\nenv:\n  matrix:\n    - VALGRIND=On SANITIZERS=Off\n    - VALGRIND=Off SANITIZERS=Off\n    - VALGRIND=Off SANITIZERS=On\ncompiler:\n  - gcc\n  - clang\naddons:\n  apt:\n    packages:\n      - valgrind\n      - libasan0\n      - lib32asan0\n      # currently not supported on travis:\n      # - libasan1\n      # - libasan2\n      # - libubsan0\n      - llvm\nscript:\n  - mkdir build\n  - cd build\n  - cmake .. -DENABLE_CJSON_UTILS=On -DENABLE_VALGRIND=\"${VALGRIND}\" -DENABLE_SAFE_STACK=\"${VALGRIND}\" -DENABLE_SANITIZERS=\"${SANITIZERS}\"\n  - make\n  - make test CTEST_OUTPUT_ON_FAILURE=On\n"
    },
    {
      "path": "CMakeLists.txt",
      "size_bytes": 10484,
      "content_excerpt": "set(CMAKE_LEGACY_CYGWIN_WIN32 0)\ncmake_minimum_required(VERSION 3.5)\n\nproject(cJSON\n    VERSION 1.7.19\n    LANGUAGES C)\n\ncmake_policy(SET CMP0054 NEW)  # set CMP0054 policy\n\ninclude(GNUInstallDirs)\n\nset(CJSON_VERSION_SO 1)\nset(CJSON_UTILS_VERSION_SO 1)\n\nset(custom_compiler_flags)\n\ninclude(CheckCCompilerFlag)\noption(ENABLE_CUSTOM_COMPILER_FLAGS \"Enables custom compiler flags\" ON)\nif (ENABLE_CUSTOM_COMPILER_FLAGS)\n    if ((\"${CMAKE_C_COMPILER_ID}\" STREQUAL \"Clang\") OR (\"${CMAKE_C_COMPILER_ID}\" STREQUAL \"GNU\"))\n        list(APPEND custom_compiler_flags\n            -std=c89\n            -pedantic\n            -Wall\n            -Wextra\n            -Werror\n            -Wstrict-prototypes\n            -Wwrite-strings\n            -Wshadow\n            -Winit-self\n            -Wcast-align\n            -Wformat=2\n            -Wmissing-prototypes\n            -Wstrict-overflow=2\n            -Wcast-qual\n            -Wundef\n            -Wswitch-default\n            -Wconversion\n            -Wc++-compat\n            -fstack-protector-strong\n            -Wcomma\n            -Wdouble-promotion\n            -Wparentheses\n            -Wformat-overflow\n            -Wunused-macros\n            -Wmissing-variable-declarations\n            -Wused-but-marked-unused\n            -Wswitch-enum\n        )\n    elseif(\"${CMAKE_C_COMPILER_ID}\" STREQUAL \"MSVC\")\n        # Disable warning c4001 - nonstandard extension 'single line comment' was used\n        # Define _CRT_SECURE_NO_WARNINGS to disable deprecation warnings for \"insecure\" C library functions\n        list(APPEND custom_compiler_flags\n            /GS\n            /Za\n            /sdl\n            /W4\n            /wd4001\n            /D_CRT_SECURE_NO_WARNINGS\n        )\n    endif()\nendif()\n\noption(ENABLE_SANITIZERS \"Enables AddressSanitizer and UndefinedBehav"
    },
    {
      "path": "appveyor.yml",
      "size_bytes": 2369,
      "content_excerpt": "os: Visual Studio 2015\n\n# ENABLE_CUSTOM_COMPILER_FLAGS - on by default\n# ENABLE_SANITIZERS - off by default\n# ENABLE_PUBLIC_SYMBOLS - on by default\n# BUILD_SHARED_LIBS - on by default\n# ENABLE_TARGET_EXPORT - on by default\n# ENABLE_CJSON_UTILS - off by default\n# ENABLE_CJSON_TEST -on by default\n# ENABLE_VALGRIND - off by default\n# ENABLE_FUZZING - off by default\n\nenvironment:\n  matrix:\n    - GENERATOR: \"Visual Studio 14 2015\"\n      BUILD_SHARED_LIBS: ON\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n    - GENERATOR: \"Visual Studio 14 2015\"\n      BUILD_SHARED_LIBS: OFF\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n    - GENERATOR: \"Visual Studio 12 2013\"\n      BUILD_SHARED_LIBS: ON\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n    - GENERATOR: \"Visual Studio 12 2013\"\n      BUILD_SHARED_LIBS: OFF\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n    - GENERATOR: \"Visual Studio 11 2012\"\n      BUILD_SHARED_LIBS: ON\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n    - GENERATOR: \"Visual Studio 11 2012\"\n      BUILD_SHARED_LIBS: OFF\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n    - GENERATOR: \"Visual Studio 10 2010\"\n      BUILD_SHARED_LIBS: ON\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n    - GENERATOR: \"Visual Studio 10 2010\"\n      BUILD_SHARED_LIBS: OFF\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n    - GENERATOR: \"Visual Studio 9 2008\"\n      BUILD_SHARED_LIBS: ON\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n    - GENERATOR: \"Visual Studio 9 2008\"\n      BUILD_SHARED_LIBS: OFF\n      ENABLE_CJSON_TEST: OFF\n      ENABLE_CJSON_UTILS: ON\n\n\nplatform:\n  - x86\n  - x64\nmatrix:\n  exclude:\n  - platform: x64\n    GENERATOR: \"Visual Studio 9 2008\"\n\nconfiguration:\n  - Releas"
    },
    {
      "path": "tests/inputs/test1.expected",
      "size_bytes": 474,
      "content_excerpt": "{\n\t\"glossary\":\t{\n\t\t\"title\":\t\"example glossary\",\n\t\t\"GlossDiv\":\t{\n\t\t\t\"title\":\t\"S\",\n\t\t\t\"GlossList\":\t{\n\t\t\t\t\"GlossEntry\":\t{\n\t\t\t\t\t\"ID\":\t\"SGML\",\n\t\t\t\t\t\"SortAs\":\t\"SGML\",\n\t\t\t\t\t\"GlossTerm\":\t\"Standard Generalized Markup Language\",\n\t\t\t\t\t\"Acronym\":\t\"SGML\",\n\t\t\t\t\t\"Abbrev\":\t\"ISO 8879:1986\",\n\t\t\t\t\t\"GlossDef\":\t{\n\t\t\t\t\t\t\"para\":\t\"A meta-markup language, used to create markup languages such as DocBook.\",\n\t\t\t\t\t\t\"GlossSeeAlso\":\t[\"GML\", \"XML\"]\n\t\t\t\t\t},\n\t\t\t\t\t\"GlossSee\":\t\"markup\"\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}"
    },
    {
      "path": "tests/inputs/test10.expected",
      "size_bytes": 78,
      "content_excerpt": "[\"Sunday\", \"Monday\", \"Tuesday\", \"Wednesday\", \"Thursday\", \"Friday\", \"Saturday\"]"
    },
    {
      "path": "tests/inputs/test11.expected",
      "size_bytes": 147,
      "content_excerpt": "{\n\t\"name\":\t\"Jack (\\\"Bee\\\") Nimble\",\n\t\"format\":\t{\n\t\t\"type\":\t\"rect\",\n\t\t\"width\":\t1920,\n\t\t\"height\":\t1080,\n\t\t\"interlace\":\tfalse,\n\t\t\"frame rate\":\t24\n\t}\n}"
    },
    {
      "path": "tests/inputs/test2.expected",
      "size_bytes": 268,
      "content_excerpt": "{\n\t\"menu\":\t{\n\t\t\"id\":\t\"file\",\n\t\t\"value\":\t\"File\",\n\t\t\"popup\":\t{\n\t\t\t\"menuitem\":\t[{\n\t\t\t\t\t\"value\":\t\"New\",\n\t\t\t\t\t\"onclick\":\t\"CreateNewDoc()\"\n\t\t\t\t}, {\n\t\t\t\t\t\"value\":\t\"Open\",\n\t\t\t\t\t\"onclick\":\t\"OpenDoc()\"\n\t\t\t\t}, {\n\t\t\t\t\t\"value\":\t\"Close\",\n\t\t\t\t\t\"onclick\":\t\"CloseDoc()\"\n\t\t\t\t}]\n\t\t}\n\t}\n}"
    },
    {
      "path": "tests/inputs/test3.expected",
      "size_bytes": 505,
      "content_excerpt": "{\n\t\"widget\":\t{\n\t\t\"debug\":\t\"on\",\n\t\t\"window\":\t{\n\t\t\t\"title\":\t\"Sample Konfabulator Widget\",\n\t\t\t\"name\":\t\"main_window\",\n\t\t\t\"width\":\t500,\n\t\t\t\"height\":\t500\n\t\t},\n\t\t\"image\":\t{\n\t\t\t\"src\":\t\"Images/Sun.png\",\n\t\t\t\"name\":\t\"sun1\",\n\t\t\t\"hOffset\":\t250,\n\t\t\t\"vOffset\":\t250,\n\t\t\t\"alignment\":\t\"center\"\n\t\t},\n\t\t\"text\":\t{\n\t\t\t\"data\":\t\"Click Here\",\n\t\t\t\"size\":\t36,\n\t\t\t\"style\":\t\"bold\",\n\t\t\t\"name\":\t\"text1\",\n\t\t\t\"hOffset\":\t250,\n\t\t\t\"vOffset\":\t100,\n\t\t\t\"alignment\":\t\"center\",\n\t\t\t\"onMouseUp\":\t\"sun1.opacity = (sun1.opacity / 100) * 90;\"\n\t\t}\n\t}\n}"
    },
    {
      "path": "tests/inputs/test4.expected",
      "size_bytes": 3285,
      "content_excerpt": "{\n\t\"web-app\":\t{\n\t\t\"servlet\":\t[{\n\t\t\t\t\"servlet-name\":\t\"cofaxCDS\",\n\t\t\t\t\"servlet-class\":\t\"org.cofax.cds.CDSServlet\",\n\t\t\t\t\"init-param\":\t{\n\t\t\t\t\t\"configGlossary:installationAt\":\t\"Philadelphia, PA\",\n\t\t\t\t\t\"configGlossary:adminEmail\":\t\"ksm@pobox.com\",\n\t\t\t\t\t\"configGlossary:poweredBy\":\t\"Cofax\",\n\t\t\t\t\t\"configGlossary:poweredByIcon\":\t\"/images/cofax.gif\",\n\t\t\t\t\t\"configGlossary:staticPath\":\t\"/content/static\",\n\t\t\t\t\t\"templateProcessorClass\":\t\"org.cofax.WysiwygTemplate\",\n\t\t\t\t\t\"templateLoaderClass\":\t\"org.cofax.FilesTemplateLoader\",\n\t\t\t\t\t\"templatePath\":\t\"templates\",\n\t\t\t\t\t\"templateOverridePath\":\t\"\",\n\t\t\t\t\t\"defaultListTemplate\":\t\"listTemplate.htm\",\n\t\t\t\t\t\"defaultFileTemplate\":\t\"articleTemplate.htm\",\n\t\t\t\t\t\"useJSP\":\tfalse,\n\t\t\t\t\t\"jspListTemplate\":\t\"listTemplate.jsp\",\n\t\t\t\t\t\"jspFileTemplate\":\t\"articleTemplate.jsp\",\n\t\t\t\t\t\"cachePackageTagsTrack\":\t200,\n\t\t\t\t\t\"cachePackageTagsStore\":\t200,\n\t\t\t\t\t\"cachePackageTagsRefresh\":\t60,\n\t\t\t\t\t\"cacheTemplatesTrack\":\t100,\n\t\t\t\t\t\"cacheTemplatesStore\":\t50,\n\t\t\t\t\t\"cacheTemplatesRefresh\":\t15,\n\t\t\t\t\t\"cachePagesTrack\":\t200,\n\t\t\t\t\t\"cachePagesStore\":\t100,\n\t\t\t\t\t\"cachePagesRefresh\":\t10,\n\t\t\t\t\t\"cachePagesDirtyRead\":\t10,\n\t\t\t\t\t\"searchEngineListTemplate\":\t\"forSearchEnginesList.htm\",\n\t\t\t\t\t\"searchEngineFileTemplate\":\t\"forSearchEngines.htm\",\n\t\t\t\t\t\"searchEngineRobotsDb\":\t\"WEB-INF/robots.db\",\n\t\t\t\t\t\"useDataStore\":\ttrue,\n\t\t\t\t\t\"dataStoreClass\":\t\"org.cofax.SqlDataStore\",\n\t\t\t\t\t\"redirectionClass\":\t\"org.cofax.SqlRedirection\",\n\t\t\t\t\t\"dataStoreName\":\t\"cofax\",\n\t\t\t\t\t\"dataStoreDriver\":\t\"com.microsoft.jdbc.sqlserver.SQLServerDriver\",\n\t\t\t\t\t\"dataStoreUrl\":\t\"jdbc:microsoft:sqlserver://LOCALHOST:1433;DatabaseName=goon\",\n\t\t\t\t\t\"dataStoreUser\":\t\"sa\",\n\t\t\t\t\t\"dataStorePassword\":\t\"dataStoreTestQuery\",\n\t\t\t\t\t\"dataStoreTestQuery\":\t\"SET NOCOUNT ON;select test='test';\",\n\t\t\t\t\t\"dataStoreLogFile\":\t\"/usr/local/tomcat/logs/datast"
    },
    {
      "path": "tests/inputs/test5.expected",
      "size_bytes": 900,
      "content_excerpt": "{\n\t\"menu\":\t{\n\t\t\"header\":\t\"SVG Viewer\",\n\t\t\"items\":\t[{\n\t\t\t\t\"id\":\t\"Open\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"OpenNew\",\n\t\t\t\t\"label\":\t\"Open New\"\n\t\t\t}, null, {\n\t\t\t\t\"id\":\t\"ZoomIn\",\n\t\t\t\t\"label\":\t\"Zoom In\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"ZoomOut\",\n\t\t\t\t\"label\":\t\"Zoom Out\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"OriginalView\",\n\t\t\t\t\"label\":\t\"Original View\"\n\t\t\t}, null, {\n\t\t\t\t\"id\":\t\"Quality\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"Pause\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"Mute\"\n\t\t\t}, null, {\n\t\t\t\t\"id\":\t\"Find\",\n\t\t\t\t\"label\":\t\"Find...\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"FindAgain\",\n\t\t\t\t\"label\":\t\"Find Again\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"Copy\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"CopyAgain\",\n\t\t\t\t\"label\":\t\"Copy Again\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"CopySVG\",\n\t\t\t\t\"label\":\t\"Copy SVG\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"ViewSVG\",\n\t\t\t\t\"label\":\t\"View SVG\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"ViewSource\",\n\t\t\t\t\"label\":\t\"View Source\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"SaveAs\",\n\t\t\t\t\"label\":\t\"Save As\"\n\t\t\t}, null, {\n\t\t\t\t\"id\":\t\"Help\"\n\t\t\t}, {\n\t\t\t\t\"id\":\t\"About\",\n\t\t\t\t\"label\":\t\"About Adobe CVG Viewer...\"\n\t\t\t}]\n\t}\n}"
    },
    {
      "path": "tests/inputs/test7.expected",
      "size_bytes": 347,
      "content_excerpt": "[{\n\t\t\"precision\":\t\"zip\",\n\t\t\"Latitude\":\t37.7668,\n\t\t\"Longitude\":\t-122.3959,\n\t\t\"Address\":\t\"\",\n\t\t\"City\":\t\"SAN FRANCISCO\",\n\t\t\"State\":\t\"CA\",\n\t\t\"Zip\":\t\"94107\",\n\t\t\"Country\":\t\"US\"\n\t}, {\n\t\t\"precision\":\t\"zip\",\n\t\t\"Latitude\":\t37.371991,\n\t\t\"Longitude\":\t-122.02602,\n\t\t\"Address\":\t\"\",\n\t\t\"City\":\t\"SUNNYVALE\",\n\t\t\"State\":\t\"CA\",\n\t\t\"Zip\":\t\"94085\",\n\t\t\"Country\":\t\"US\"\n\t}]"
    },
    {
      "path": "tests/inputs/test8.expected",
      "size_bytes": 228,
      "content_excerpt": "{\n\t\"Image\":\t{\n\t\t\"Width\":\t800,\n\t\t\"Height\":\t600,\n\t\t\"Title\":\t\"View from 15th Floor\",\n\t\t\"Thumbnail\":\t{\n\t\t\t\"Url\":\t\"http:/*www.example.com/image/481989943\",\n\t\t\t\"Height\":\t125,\n\t\t\t\"Width\":\t\"100\"\n\t\t},\n\t\t\"IDs\":\t[116, 943, 234, 38793]\n\t}\n}"
    },
    {
      "path": "tests/inputs/test9.expected",
      "size_bytes": 34,
      "content_excerpt": "[[0, -1, 0], [1, 0, 0], [0, 0, 1]]"
    }
  ],
  "target_project_context": {
    "cargo_toml": "[package]\nname = \"json\"\nversion = \"0.12.4\"\nauthors = [\"Maciej Hirsz <hello@maciej.codes>\"]\ndescription = \"JSON implementation in Rust\"\nrepository = \"https://github.com/maciejhirsz/json-rust\"\ndocumentation = \"https://docs.rs/json/\"\nlicense = \"MIT/Apache-2.0\"\nedition = \"2018\"\n",
    "src_lib_rs": "//! ![](https://raw.githubusercontent.com/maciejhirsz/json-rust/master/json-rust-logo-small.png)\n//!\n//! # json-rust\n//!\n//! Parse and serialize [JSON](http://json.org/) with ease.\n//!\n//! **[Changelog](https://github.com/maciejhirsz/json-rust/releases) -**\n//! **[Complete Documentation](https://docs.rs/json/) -**\n//! **[Cargo](https://crates.io/crates/json) -**\n//! **[Repository](https://github.com/maciejhirsz/json-rust)**\n//!\n//! ## Why?\n//!\n//! JSON is a very loose format where anything goes - arrays can hold mixed\n//! types, object keys can change types between API calls or not include\n//! some keys under some conditions. Mapping that to idiomatic Rust structs\n//! introduces friction.\n//!\n//! This crate intends to avoid that friction.\n//!\n//! ```rust\n//! # #[macro_use] extern crate json;\n//! # fn main() {\n//! let parsed = json::parse(r#\"\n//!\n//! {\n//!     \"code\": 200,\n//!     \"success\": true,\n//!     \"payload\": {\n//!         \"features\": [\n//!             \"awesome\",\n//!             \"easyAPI\",\n//!             \"lowLearningCurve\"\n//!         ]\n//!     }\n//! }\n//!\n//! \"#).unwrap();\n//!\n//! let instantiated = object!{\n//!     // quotes on keys are optional\n//!     \"code\": 200,\n//!     success: true,\n//!     payload: {\n//!         features: [\n//!             \"awesome\",\n//!             \"easyAPI\",\n//!             \"lowLearningCurve\"\n//!         ]\n//!     }\n//! };\n//!\n//! assert_eq!(parsed, instantiated);\n//! # }\n//! ```\n//!\n//! ## First class citizen\n//!\n//! Using macros and indexing, it's easy to work with the data.\n//!\n//! ```rust\n//! # #[macro_use] extern crate json;\n//! # fn main() {\n//! let mut data = object!{\n//!     foo: false,\n//!     bar: null,\n//!     answer: 42,\n//!     list: [null, \"world\", true]\n//! };\n//!\n//! // Partial equality is implemented for most raw types:\n//! assert!(data[\"foo\"] == false);\n//!\n//! // And it's type aware, `null` and `false` are different values:\n//! assert!(data[\"bar\"] != false);\n//!\n//! // But you can use any Rust number types:\n//! assert!(data[\"answer\"] == 42);\n//! assert!(data[\"answer\"] == 42.0);\n//! assert!(data[\"answer\"] == 42isize);\n//!\n//! // Access nested structures, arrays and objects:\n//! assert!(data[\"list\"][0].is_null());\n//! assert!(data[\"list\"][1] == \"world\");\n//! assert!(data[\"list\"][2] == true);\n//!\n//! // Error resilient - accessing properties that don't exist yield null:\n//! assert!(data[\"this\"][\"does\"][\"not\"][\"exist\"].is_null());\n//!\n//! // Mutate by assigning:\n//! data[\"list\"][0] = \"Hello\".into();\n//!\n//! // Use the `dump` method to serialize the data:\n//! assert_eq!(data.dump(), r#\"{\"foo\":false,\"bar\":null,\"answer\":42,\"list\":[\"Hello\",\"world\",true]}\"#);\n//!\n//! // Or pretty print it out:\n//! println!(\"{:#}\", data);\n//! # }\n//! ```\n//!\n//! ## Serialize with `json::stringify(value)`\n//!\n//! Primitives:\n//!\n//! ```\n//! // str slices\n//! assert_eq!(json::stringify(\"foobar\"), \"\\\"foobar\\\"\");\n//!\n//! // Owned strings\n//! assert_eq!(json::stringify(\"foobar\".to_string()), \"\\\"foobar\\\"\");\n//!\n//! // Any number types\n//! assert_eq!(json::stringify(42), \"42\");\n//!\n//! // Booleans\n//! assert_eq!(json::stringify(true), \"true\");\n//! assert_eq!(json::stringify(false), \"false\");\n//! ```\n//!\n//! Explicit `null` type `json::Null`:\n//!\n//! ```\n//! assert_eq!(json::stringify(json::Null), \"null\");\n//! ```\n//!\n//! Optional types:\n//!\n//! ```\n//! let value: Option<String> = Some(\"foo\".to_string());\n//! assert_eq!(json::stringify(value), \"\\\"foo\\\"\");\n//!\n//! let no_value: Option<String> = None;\n//! assert_eq!(json::stringify(no_value), \"null\");\n//! ```\n//!\n//! Vector:\n//!\n//! ```\n//! let data = vec![1,2,3];\n//! assert_eq!(json::stringify(data), \"[1,2,3]\");\n//! ```\n//!\n//! Vector with optional values:\n//!\n//! ```\n//! let data = vec![Some(1), None, Some(2), None, Some(3)];\n//! assert_eq!(json::stringify(data), \"[1,null,2,null,3]\");\n//! ```\n//!\n//! Pushing to arrays:\n//!\n//! ```\n//! let mut data = json::JsonValue::new_array();\n//!\n//! data.push(10);\n//! data.push(\"foo\");\n//! data.push(false);\n//!\n//! assert_eq!(data.dump(), r#\"[10,\"foo\",false]\"#);\n//! ```\n//!\n//! Putting fields on objects:\n//!\n//! ```\n//! let mut data = json::JsonValue::new_object();\n//!\n//! data[\"answer\"] = 42.into();\n//! data[\"foo\"] = \"bar\".into();\n//!\n//! assert_eq!(data.dump(), r#\"{\"answer\":42,\"foo\":\"bar\"}\"#);\n//! ```\n//!\n//! `array!` macro:\n//!\n//! ```\n//! # #[macro_use] extern crate json;\n//! # fn main() {\n//! let data = array![\"foo\", \"bar\", 100, true, null];\n//! assert_eq!(data.dump(), r#\"[\"foo\",\"bar\",100,true,null]\"#);\n//! # }\n//! ```\n//!\n//! `object!` macro:\n//!\n//! ```\n//! # #[macro_use] extern crate json;\n//! # fn main() {\n//! let data = object!{\n//!     name: \"John Doe\",\n//!     age: 30,\n//!     canJSON: true\n//! };\n//! assert_eq!(\n//!     data.dump(),\n//!     r#\"{\"name\":\"John Doe\",\"age\":30,\"canJSON\":true}\"#\n//! );\n//! # }\n//! ```\n\nuse std::result;\n\npub mod codegen;\nmod parser;\nmod value;\nmod error;\nmod util;\n\npub mod short;\npub mod object;\npub mod number;\n\npub use error::Error;\npub use value::JsonValue;\npub use value::JsonValue::Null;\n\n/// Result type used by this crate.\n///\n///\n/// *Note:* Since 0.9.0 the old `JsonResult` type is deprecated. Always use\n/// `json::Result` instead.\npub type Result<T> = result::Result<T, Error>;\n\npub mod iterators {\n    /// Iterator over members of `JsonValue::Array`.\n    pub type Members<'a> = ::std::slice::Iter<'a, super::JsonValue>;\n\n    /// Mutable iterator over members of `JsonValue::Array`.\n    pub type MembersMut<'a> = ::std::slice::IterMut<'a, super::JsonValue>;\n\n    /// Iterator over key value pairs of `JsonValue::Object`.\n    pub type Entries<'a> = super::object::Iter<'a>;\n\n    /// Mutable iterator over key value pairs of `JsonValue::Object`.\n    pub type EntriesMut<'a> = super::object::IterMut<'a>;\n}\n\n#[deprecated(since=\"0.9.0\", note=\"use `json::Error` instead\")]\npub use Error as JsonError;\n\n#[deprecated(since=\"0.9.0\", note=\"use `json::Result` instead\")]\npub use crate::Result as JsonResult;\n\npub use parser::parse;\n\npub type Array = Vec<JsonValue>;\n\n/// Convenience for `JsonValue::from(value)`\npub fn from<T>(value: T) -> JsonValue where T: Into<JsonValue> {\n    value.into()\n}\n\n/// Pretty prints out the value as JSON string.\npub fn stringify<T>(root: T) -> String where T: Into<JsonValue> {\n    let root: JsonValue = root.into();\n    root.dump()\n}\n\n/// Pretty prints out the value as JSON string. Second argument is a\n/// number of spaces to indent new blocks with.\npub fn stringify_pretty<T>(root: T, spaces: u16) -> String where T: Into<JsonValue> {\n    let root: JsonValue = root.into();\n    root.pretty(spaces)\n}\n\n/// Helper macro for creating instances of `JsonValue::Array`.\n///\n/// ```\n/// # #[macro_use] extern crate json;\n/// # fn main() {\n/// let data = array![\"foo\", 42, false];\n///\n/// assert_eq!(data[0], \"foo\");\n/// assert_eq!(data[1], 42);\n/// assert_eq!(data[2], false);\n///\n/// assert_eq!(data.dump(), r#\"[\"foo\",42,false]\"#);\n/// # }\n/// ```\n#[macro_export]\nmacro_rules! array {\n    [] => ($crate::JsonValue::new_array());\n\n  ",
    "note": "Use Cargo.toml package/lib names and public exports when writing Rust integration tests."
  },
  "target_crate_import_hint": {
    "package_name": "json",
    "lib_name": "",
    "crate_name_for_rust_code": "json",
    "integration_test_note": "In tests/cp2rs_3b_public.rs, import the target crate as `json` unless Cargo.toml/lib.rs evidence shows a different public crate name."
  },
  "target_public_api_signatures": [
    {
      "uuid": "src/codegen.rs::DumpGenerator::consume",
      "signature": "pub fn consume(self) -> String"
    },
    {
      "uuid": "src/codegen.rs::DumpGenerator::new",
      "signature": "pub fn new() -> Self"
    },
    {
      "uuid": "src/codegen.rs::PrettyGenerator::consume",
      "signature": "pub fn consume(self) -> String"
    },
    {
      "uuid": "src/codegen.rs::PrettyGenerator::new",
      "signature": "pub fn new(spaces: u16) -> Self"
    },
    {
      "uuid": "src/codegen.rs::PrettyWriterGenerator::new",
      "signature": "pub fn new(writer: &'a mut W, spaces: u16) -> Self"
    },
    {
      "uuid": "src/codegen.rs::WriterGenerator::new",
      "signature": "pub fn new(writer: &'a mut W) -> Self"
    },
    {
      "uuid": "src/error.rs::Error::wrong_type",
      "signature": "pub fn wrong_type(expected: &str) -> Self"
    },
    {
      "uuid": "src/lib.rs::from",
      "signature": "pub fn from<T>(value: T) -> JsonValue where T: Into<JsonValue>"
    },
    {
      "uuid": "src/lib.rs::stringify",
      "signature": "pub fn stringify<T>(root: T) -> String where T: Into<JsonValue>"
    },
    {
      "uuid": "src/lib.rs::stringify_pretty",
      "signature": "pub fn stringify_pretty<T>(root: T, spaces: u16) -> String where T: Into<JsonValue>"
    },
    {
      "uuid": "src/number.rs::Number::as_fixed_point_i64",
      "signature": "pub fn as_fixed_point_i64(&self, point: u16) -> Option<i64>"
    },
    {
      "uuid": "src/number.rs::Number::as_fixed_point_u64",
      "signature": "pub fn as_fixed_point_u64(&self, point: u16) -> Option<u64>"
    },
    {
      "uuid": "src/number.rs::Number::as_parts",
      "signature": "pub fn as_parts(&self) -> (bool, u64, i16)"
    },
    {
      "uuid": "src/number.rs::Number::from_parts",
      "signature": "pub fn from_parts(positive: bool, mut mantissa: u64, mut exponent: i16) -> Self"
    },
    {
      "uuid": "src/number.rs::Number::from_parts_unchecked",
      "signature": "pub unsafe fn from_parts_unchecked(positive: bool, mantissa: u64, exponent: i16) -> Self"
    },
    {
      "uuid": "src/number.rs::Number::is_empty",
      "signature": "pub fn is_empty(&self) -> bool"
    },
    {
      "uuid": "src/number.rs::Number::is_nan",
      "signature": "pub fn is_nan(&self) -> bool"
    },
    {
      "uuid": "src/number.rs::Number::is_sign_positive",
      "signature": "pub fn is_sign_positive(&self) -> bool"
    },
    {
      "uuid": "src/number.rs::Number::is_zero",
      "signature": "pub fn is_zero(&self) -> bool"
    },
    {
      "uuid": "src/object.rs::Iter::empty",
      "signature": "pub fn empty() -> Self"
    },
    {
      "uuid": "src/object.rs::IterMut::empty",
      "signature": "pub fn empty() -> Self"
    },
    {
      "uuid": "src/object.rs::Object::clear",
      "signature": "pub fn clear(&mut self)"
    },
    {
      "uuid": "src/object.rs::Object::dump",
      "signature": "pub fn dump(&self) -> String"
    },
    {
      "uuid": "src/object.rs::Object::get",
      "signature": "pub fn get(&self, key: &str) -> Option<&JsonValue>"
    },
    {
      "uuid": "src/object.rs::Object::get_mut",
      "signature": "pub fn get_mut(&mut self, key: &str) -> Option<&mut JsonValue>"
    },
    {
      "uuid": "src/object.rs::Object::insert",
      "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)"
    },
    {
      "uuid": "src/object.rs::Object::is_empty",
      "signature": "pub fn is_empty(&self) -> bool"
    },
    {
      "uuid": "src/object.rs::Object::iter",
      "signature": "pub fn iter(&self) -> Iter"
    },
    {
      "uuid": "src/object.rs::Object::iter_mut",
      "signature": "pub fn iter_mut(&mut self) -> IterMut"
    },
    {
      "uuid": "src/object.rs::Object::len",
      "signature": "pub fn len(&self) -> usize"
    },
    {
      "uuid": "src/object.rs::Object::new",
      "signature": "pub fn new() -> Self"
    },
    {
      "uuid": "src/object.rs::Object::override_last",
      "signature": "pub fn override_last(&mut self, value: JsonValue)"
    },
    {
      "uuid": "src/object.rs::Object::pretty",
      "signature": "pub fn pretty(&self, spaces: u16) -> String"
    },
    {
      "uuid": "src/object.rs::Object::remove",
      "signature": "pub fn remove(&mut self, key: &str) -> Option<JsonValue>"
    },
    {
      "uuid": "src/object.rs::Object::with_capacity",
      "signature": "pub fn with_capacity(capacity: usize) -> Self"
    },
    {
      "uuid": "src/parser.rs::Parser::new",
      "signature": "pub fn new(source: &'a str) -> Self"
    },
    {
      "uuid": "src/parser.rs::parse",
      "signature": "pub fn parse(source: &str) -> Result<JsonValue>"
    },
    {
      "uuid": "src/short.rs::Short::as_str",
      "signature": "pub fn as_str(&self) -> &str"
    },
    {
      "uuid": "src/short.rs::Short::from_slice",
      "signature": "pub unsafe fn from_slice(slice: &str) -> Self"
    },
    {
      "uuid": "src/util/diyfp.rs::DiyFp::from_f64",
      "signature": "pub unsafe fn from_f64(d: f64) -> Self"
    },
    {
      "uuid": "src/util/diyfp.rs::DiyFp::new",
      "signature": "pub fn new(f: u64, e: isize) -> Self"
    },
    {
      "uuid": "src/util/diyfp.rs::DiyFp::normalize",
      "signature": "pub fn normalize(self) -> DiyFp"
    },
    {
      "uuid": "src/util/diyfp.rs::DiyFp::normalize_boundary",
      "signature": "pub fn normalize_boundary(self) -> DiyFp"
    },
    {
      "uuid": "src/util/diyfp.rs::DiyFp::normalized_boundaries",
      "signature": "pub fn normalized_boundaries(self) -> (DiyFp, DiyFp)"
    },
    {
      "uuid": "src/util/diyfp.rs::get_cached_power",
      "signature": "pub fn get_cached_power(e: isize) -> (DiyFp, isize)"
    },
    {
      "uuid": "src/util/grisu2.rs::convert",
      "signature": "pub fn convert(float: f64) -> (u64, i16)"
    },
    {
      "uuid": "src/util/print_dec.rs::write",
      "signature": "pub unsafe fn write<W: io::Write>(wr: &mut W, positive: bool, mut n: u64, exponent: i16) -> io::Result<()>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::array_remove",
      "signature": "pub fn array_remove(&mut self, index: usize) -> JsonValue"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_bool",
      "signature": "pub fn as_bool(&self) -> Option<bool>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_f32",
      "signature": "pub fn as_f32(&self) -> Option<f32>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_f64",
      "signature": "pub fn as_f64(&self) -> Option<f64>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_fixed_point_i64",
      "signature": "pub fn as_fixed_point_i64(&self, point: u16) -> Option<i64>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_fixed_point_u64",
      "signature": "pub fn as_fixed_point_u64(&self, point: u16) -> Option<u64>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_i16",
      "signature": "pub fn as_i16(&self) -> Option<i16>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_i32",
      "signature": "pub fn as_i32(&self) -> Option<i32>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_i64",
      "signature": "pub fn as_i64(&self) -> Option<i64>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_i8",
      "signature": "pub fn as_i8(&self) -> Option<i8>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_isize",
      "signature": "pub fn as_isize(&self) -> Option<isize>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_number",
      "signature": "pub fn as_number(&self) -> Option<Number>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_str",
      "signature": "pub fn as_str(&self) -> Option<&str>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_u16",
      "signature": "pub fn as_u16(&self) -> Option<u16>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_u32",
      "signature": "pub fn as_u32(&self) -> Option<u32>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_u64",
      "signature": "pub fn as_u64(&self) -> Option<u64>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_u8",
      "signature": "pub fn as_u8(&self) -> Option<u8>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_usize",
      "signature": "pub fn as_usize(&self) -> Option<usize>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::clear",
      "signature": "pub fn clear(&mut self)"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::contains",
      "signature": "pub fn contains<T>(&self, item: T) -> bool where T: PartialEq<JsonValue>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::dump",
      "signature": "pub fn dump(&self) -> String"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::entries",
      "signature": "pub fn entries(&self) -> Entries"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::entries_mut",
      "signature": "pub fn entries_mut(&mut self) -> EntriesMut"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::has_key",
      "signature": "pub fn has_key(&self, key: &str) -> bool"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::insert",
      "signature": "pub fn insert<T>(&mut self, key: &str, value: T) -> Result<()>\r\n    where T: Into<JsonValue>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_array",
      "signature": "pub fn is_array(&self) -> bool"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_boolean",
      "signature": "pub fn is_boolean(&self) -> bool"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_empty",
      "signature": "pub fn is_empty(&self) -> bool"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_null",
      "signature": "pub fn is_null(&self) -> bool"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_number",
      "signature": "pub fn is_number(&self) -> bool"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_object",
      "signature": "pub fn is_object(&self) -> bool"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_string",
      "signature": "pub fn is_string(&self) -> bool"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::len",
      "signature": "pub fn len(&self) -> usize"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::members",
      "signature": "pub fn members(&self) -> Members"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::members_mut",
      "signature": "pub fn members_mut(&mut self) -> MembersMut"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::new_array",
      "signature": "pub fn new_array() -> JsonValue"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::new_object",
      "signature": "pub fn new_object() -> JsonValue"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::pop",
      "signature": "pub fn pop(&mut self) -> JsonValue"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::pretty",
      "signature": "pub fn pretty(&self, spaces: u16) -> String"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::push",
      "signature": "pub fn push<T>(&mut self, value: T) -> Result<()>\r\n    where T: Into<JsonValue>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::remove",
      "signature": "pub fn remove(&mut self, key: &str) -> JsonValue"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::take",
      "signature": "pub fn take(&mut self) -> JsonValue"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::take_string",
      "signature": "pub fn take_string(&mut self) -> Option<String>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::to_writer",
      "signature": "pub fn to_writer<W: Write>(&self, writer: &mut W)"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::write",
      "signature": "pub fn write<W: Write>(&self, writer: &mut W) -> io::Result<()>"
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::write_pretty",
      "signature": "pub fn write_pretty<W: Write>(&self, writer: &mut W, spaces: u16) -> io::Result<()>"
    }
  ],
  "target_aligned_api_context": [
    {
      "uuid": "src/value/mod.rs::JsonValue::as_str",
      "name": "as_str",
      "owner_type": "JsonValue",
      "signature": "pub fn as_str(&self) -> Option<&str>",
      "body_excerpt": "pub fn as_str(&self) -> Option<&str> {\r\n        match *self {\r\n            JsonValue::Short(ref value)  => Some(value),\r\n            JsonValue::String(ref value) => Some(value),\r\n            _                            => None\r\n        }\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.as_str(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::as_f64",
      "name": "as_f64",
      "owner_type": "JsonValue",
      "signature": "pub fn as_f64(&self) -> Option<f64>",
      "body_excerpt": "pub fn as_f64(&self) -> Option<f64> {\r\n        self.as_number().map(|value| value.into())\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.as_f64(...)."
    },
    {
      "uuid": "src/parser.rs::parse",
      "name": "parse",
      "owner_type": "",
      "signature": "pub fn parse(source: &str) -> Result<JsonValue>",
      "body_excerpt": "pub fn parse(source: &str) -> Result<JsonValue> {\r\n    Parser::new(source).parse()\r\n}",
      "call_hint": "Call as a free function if exported, e.g. parse(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::pretty",
      "name": "pretty",
      "owner_type": "JsonValue",
      "signature": "pub fn pretty(&self, spaces: u16) -> String",
      "body_excerpt": "pub fn pretty(&self, spaces: u16) -> String {\r\n        let mut gen = PrettyGenerator::new(spaces);\r\n        gen.write_json(self).expect(\"Can't fail\");\r\n        gen.consume()\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.pretty(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::dump",
      "name": "dump",
      "owner_type": "JsonValue",
      "signature": "pub fn dump(&self) -> String",
      "body_excerpt": "pub fn dump(&self) -> String {\r\n        let mut gen = DumpGenerator::new();\r\n        gen.write_json(self).expect(\"Can't fail\");\r\n        gen.consume()\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.dump(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::len",
      "name": "len",
      "owner_type": "JsonValue",
      "signature": "pub fn len(&self) -> usize",
      "body_excerpt": "pub fn len(&self) -> usize {\r\n        match *self {\r\n            JsonValue::Array(ref vec) => {\r\n                vec.len()\r\n            },\r\n            JsonValue::Object(ref object) => {\r\n                object.len()\r\n            },\r\n            _ => 0\r\n        }\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.len(...)."
    },
    {
      "uuid": "src/object.rs::Object::get",
      "name": "get",
      "owner_type": "Object",
      "signature": "pub fn get(&self, key: &str) -> Option<&JsonValue>",
      "body_excerpt": "pub fn get(&self, key: &str) -> Option<&JsonValue> {\r\n        if self.store.len() == 0 {\r\n            return None;\r\n        }\r\n\r\n        let key = key.as_bytes();\r\n        let hash = hash_key(key);\r\n\r\n        let mut node = unsafe { self.store.get_unchecked(0) };\r\n\r\n        loop {\r\n            if hash == node.key.hash && key == node.key.as_bytes() {\r\n                return Some(&node.value);\r\n            } else if hash < node.key.hash {\r\n                if node.left == 0 {\r\n                    return None;\r\n                }\r\n                node = unsafe { self.store.get_unchecked(node.left) };\r\n            } else {\r\n                if node.right == 0 {\r\n                    return None;\r\n                }\r\n                node = unsafe { self.store.get_unchecked(node.right) };\r\n            }\r\n        }\r\n    }",
      "call_hint": "Call as a method on a Object value/reference, e.g. value.get(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::has_key",
      "name": "has_key",
      "owner_type": "JsonValue",
      "signature": "pub fn has_key(&self, key: &str) -> bool",
      "body_excerpt": "pub fn has_key(&self, key: &str) -> bool {\r\n        match *self {\r\n            JsonValue::Object(ref object) => object.get(key).is_some(),\r\n            _                             => false\r\n        }\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.has_key(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::push",
      "name": "push",
      "owner_type": "JsonValue",
      "signature": "pub fn push<T>(&mut self, value: T) -> Result<()>\r\n    where T: Into<JsonValue>",
      "body_excerpt": "pub fn push<T>(&mut self, value: T) -> Result<()>\r\n    where T: Into<JsonValue> {\r\n        match *self {\r\n            JsonValue::Array(ref mut vec) => {\r\n                vec.push(value.into());\r\n                Ok(())\r\n            },\r\n            _ => Err(Error::wrong_type(\"Array\"))\r\n        }\r\n    }",
      "call_hint": "Call as a mutable method on a mutable JsonValue value, e.g. value.push(...). For generic Into<T> parameters, pass a concrete value directly when possible instead of pre-calling .into()."
    },
    {
      "uuid": "src/object.rs::Object::insert",
      "name": "insert",
      "owner_type": "Object",
      "signature": "pub fn insert(&mut self, key: &str, value: JsonValue)",
      "body_excerpt": "pub fn insert(&mut self, key: &str, value: JsonValue) {\r\n        self.insert_index(key, value);\r\n    }",
      "call_hint": "Call as a mutable method on a mutable Object value, e.g. value.insert(...)."
    },
    {
      "uuid": "src/object.rs::Object::remove",
      "name": "remove",
      "owner_type": "Object",
      "signature": "pub fn remove(&mut self, key: &str) -> Option<JsonValue>",
      "body_excerpt": "pub fn remove(&mut self, key: &str) -> Option<JsonValue> {\r\n        if self.store.len() == 0 {\r\n            return None;\r\n        }\r\n\r\n        let key = key.as_bytes();\r\n        let hash = hash_key(key);\r\n        let mut index = 0;\r\n\r\n        {\r\n            let mut node = unsafe { self.store.get_unchecked(0) };\r\n\r\n            // Try to find the node\r\n            loop {\r\n                if hash == node.key.hash && key == node.key.as_bytes() {\r\n                    break;\r\n                } else if hash < node.key.hash {\r\n                    if node.left == 0 {\r\n                        return None;\r\n                    }\r\n                    index = node.left;\r\n                    node = unsafe { self.store.get_unchecked(node.left) };\r\n                } else {\r\n                    if node.right == 0 {\r\n                        return None;\r\n                    }\r\n                    index = ",
      "call_hint": "Call as a mutable method on a mutable Object value, e.g. value.remove(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::array_remove",
      "name": "array_remove",
      "owner_type": "JsonValue",
      "signature": "pub fn array_remove(&mut self, index: usize) -> JsonValue",
      "body_excerpt": "pub fn array_remove(&mut self, index: usize) -> JsonValue {\r\n        match *self {\r\n            JsonValue::Array(ref mut vec) => {\r\n                if index < vec.len() {\r\n                    vec.remove(index)\r\n                } else {\r\n                    JsonValue::Null\r\n                }\r\n            },\r\n            _ => JsonValue::Null\r\n        }\r\n    }",
      "call_hint": "Call as a mutable method on a mutable JsonValue value, e.g. value.array_remove(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::insert",
      "name": "insert",
      "owner_type": "JsonValue",
      "signature": "pub fn insert<T>(&mut self, key: &str, value: T) -> Result<()>\r\n    where T: Into<JsonValue>",
      "body_excerpt": "pub fn insert<T>(&mut self, key: &str, value: T) -> Result<()>\r\n    where T: Into<JsonValue> {\r\n        match *self {\r\n            JsonValue::Object(ref mut object) => {\r\n                object.insert(key, value.into());\r\n                Ok(())\r\n            },\r\n            _ => Err(Error::wrong_type(\"Object\"))\r\n        }\r\n    }",
      "call_hint": "Call as a mutable method on a mutable JsonValue value, e.g. value.insert(...). For generic Into<T> parameters, pass a concrete value directly when possible instead of pre-calling .into()."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::new_array",
      "name": "new_array",
      "owner_type": "JsonValue",
      "signature": "pub fn new_array() -> JsonValue",
      "body_excerpt": "pub fn new_array() -> JsonValue {\r\n        JsonValue::Array(Vec::new())\r\n    }",
      "call_hint": "Call as an associated function if exported, e.g. JsonValue::new_array(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::new_object",
      "name": "new_object",
      "owner_type": "JsonValue",
      "signature": "pub fn new_object() -> JsonValue",
      "body_excerpt": "pub fn new_object() -> JsonValue {\r\n        JsonValue::Object(Object::new())\r\n    }",
      "call_hint": "Call as an associated function if exported, e.g. JsonValue::new_object(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_boolean",
      "name": "is_boolean",
      "owner_type": "JsonValue",
      "signature": "pub fn is_boolean(&self) -> bool",
      "body_excerpt": "pub fn is_boolean(&self) -> bool {\r\n        match *self {\r\n            JsonValue::Boolean(_) => true,\r\n            _                     => false\r\n        }\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.is_boolean(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_null",
      "name": "is_null",
      "owner_type": "JsonValue",
      "signature": "pub fn is_null(&self) -> bool",
      "body_excerpt": "pub fn is_null(&self) -> bool {\r\n        match *self {\r\n            JsonValue::Null => true,\r\n            _               => false,\r\n        }\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.is_null(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_number",
      "name": "is_number",
      "owner_type": "JsonValue",
      "signature": "pub fn is_number(&self) -> bool",
      "body_excerpt": "pub fn is_number(&self) -> bool {\r\n        match *self {\r\n            JsonValue::Number(_) => true,\r\n            _                    => false,\r\n        }\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.is_number(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_string",
      "name": "is_string",
      "owner_type": "JsonValue",
      "signature": "pub fn is_string(&self) -> bool",
      "body_excerpt": "pub fn is_string(&self) -> bool {\r\n        match *self {\r\n            JsonValue::Short(_)  => true,\r\n            JsonValue::String(_) => true,\r\n            _                    => false,\r\n        }\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.is_string(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_array",
      "name": "is_array",
      "owner_type": "JsonValue",
      "signature": "pub fn is_array(&self) -> bool",
      "body_excerpt": "pub fn is_array(&self) -> bool {\r\n        match *self {\r\n            JsonValue::Array(_) => true,\r\n            _                   => false,\r\n        }\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.is_array(...)."
    },
    {
      "uuid": "src/value/mod.rs::JsonValue::is_object",
      "name": "is_object",
      "owner_type": "JsonValue",
      "signature": "pub fn is_object(&self) -> bool",
      "body_excerpt": "pub fn is_object(&self) -> bool {\r\n        match *self {\r\n            JsonValue::Object(_) => true,\r\n            _                    => false,\r\n        }\r\n    }",
      "call_hint": "Call as a method on a JsonValue value/reference, e.g. value.is_object(...)."
    }
  ],
  "required_adapter_shape": {
    "adapter_schema_version": "3b.adapter.v1",
    "name": "llm_synthesized_<src>_to_<tgt>_public_v1",
    "status": "loaded",
    "adapter_role": "repo_specific_behavior_recipe",
    "generation_status": "llm_synthesized_v1",
    "recorder": "adapter_declared_trace_events_v1",
    "replay_generator": "rust_inline_harness_v1",
    "target_language": "rust",
    "target_test_command": [
      "cargo",
      "test",
      "--test",
      "cp2rs_3b_public"
    ],
    "public_operations": {
      "operation_name": {
        "description": "Behavior scenario derived from source tests.",
        "source_functions": [
          "source uuid from 3A"
        ],
        "target_functions": [
          "target uuid from 3A or support public target uuid"
        ],
        "normalization": "Observable behavior comparison rule grounded in source test evidence.",
        "evidence": [
          "source test path or fixture"
        ]
      }
    },
    "trace_events": [
      {
        "id": "stable_trace_id_that_is_also_a_valid_rust_test_fn_name",
        "operation": "operation_name",
        "evidence": "source test or fixture evidence",
        "input": {
          "case": "short description"
        },
        "expected": {
          "observable_behavior": "short oracle summary"
        },
        "oracle_source": "source_test_assertion|source_fixture|source_test_property",
        "oracle_confidence": "high|medium|low"
      }
    ],
    "rust_test_harness": "Complete Rust integration test source for tests/cp2rs_3b_public.rs. It must define exactly one #[test] fn for each trace_events[].id, using the id as the function name."
  }
}
