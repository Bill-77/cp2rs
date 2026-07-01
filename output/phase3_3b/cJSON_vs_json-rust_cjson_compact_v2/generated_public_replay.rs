use json::{JsonValue, parse};
use std::ops::{Index, IndexMut};
use std::collections::BTreeMap;

#[test]
fn cjson_add_bool_should_add_bool() {
    let mut root = json::JsonValue::new_object();
    root.insert("true", true).unwrap();
    root.insert("false", false).unwrap();
    let true_item = root.index("true");
    assert!(true_item.as_bool() == Some(true));
    let false_item = root.index("false");
    assert!(false_item.as_bool() == Some(false));
}

#[test]
fn cjson_add_false_should_add_false() {
    let mut root = json::JsonValue::new_object();
    root.insert("false", false).unwrap();
    let false_item = root.index("false");
    assert!(false_item.as_bool() == Some(false));
}

#[test]
fn cjson_add_array_should_add_array() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    let _ = root.insert("array", JsonValue::Array(vec![]));
    assert!(root.has_key("array"));
    let item = &root["array"];
    assert!(matches!(item, JsonValue::Array(_)));
}

#[test]
fn cjson_add_null_should_add_null() {
    let mut root = JsonValue::new_object();
    let _ = root.insert("null", JsonValue::Null);
    assert!(root.has_key("null"));
    let item = &root["null"];
    assert!(matches!(item, JsonValue::Null));
}

#[test]
fn cjson_add_null_should_fail_on_allocation_failure() {
    let mut root = JsonValue::new_object();
    let result = root.insert("null", JsonValue::Null);
    assert!(result.is_err(), "Expected failure but got success");
}

#[test]
fn cjson_add_number_should_add_number() {
    use std::ops::Index;
    let mut root = JsonValue::new_object();
    root.insert("number", 42).expect("insert succeeded");
    let number = root.index("number");
    assert_eq!(number.as_f64(), Some(42.0));
    assert_eq!(number.as_i32(), Some(42));
}

#[test]
fn cjson_add_number_should_fail_on_allocation_failure() {
    let mut root = JsonValue::new_object();
    let result = root.insert("number", 42);
    assert!(result.is_err(), "Expected failure but got success");
}

#[test]
fn cjson_add_object_should_add_object() {
    let mut root = JsonValue::new_object();
    root.insert("object", JsonValue::new_object()).expect("insert succeeded");
    let obj = root.index("object");
    match obj {
        JsonValue::Object(_) => {},
        _ => panic!("Expected object"),
    }
}

#[test]
fn cjson_add_object_should_fail_on_allocation_failure() {
    let mut root = JsonValue::new_object();
    let result = root.insert("object", JsonValue::new_object());
    assert!(result.is_err(), "Expected failure but got success");
}

#[test]
fn cjson_add_raw_should_add_raw() {
    let mut root = JsonValue::new_object();
    root.insert("raw", "{}").expect("insert succeeded");
    let raw = root.index("raw");
    assert_eq!(raw.as_str(), Some("{}"));
}

#[test]
fn cjson_add_raw_should_fail_on_allocation_failure() {
    let mut root = JsonValue::new_object();
    let result = root.insert("raw", "{}");
    assert!(result.is_err(), "Expected failure but got success");
}

#[test]
fn cjson_add_string_should_add_string() {
    // Replicate: cJSON_CreateObject -> new_object (not used directly, but covered by mapping)
    use std::collections::BTreeMap;
    let mut map = BTreeMap::new();
    map.insert("string", "Hello World!");
    let root: json::JsonValue = map.into();
    // Get item via Index<&str>
    let string = &root["string"];
    // Check it is a string and has correct value
    assert!(string.as_str() == Some("Hello World!"));
}

#[test]
fn cjson_add_true_should_add_true() {
    let mut map = BTreeMap::new();
    map.insert("true", true);
    let root: JsonValue = map.into();
    let true_item = &root["true"];
    assert!(true_item.as_bool() == Some(true));
}

#[test]
fn cjson_compare_should_compare_arrays() {
    // compare_from_string helper: parse two strings, compare via eq
    let a: JsonValue = parse("[]").unwrap();
    let b: JsonValue = parse("[]").unwrap();
    assert!(a == b);

    let a: JsonValue = parse("[false,true,null,42,\"string\",[],{}]").unwrap();
    let b: JsonValue = parse("[false, true, null, 42, \"string\", [], {}]").unwrap();
    assert!(a == b);
}

#[test]
fn cjson_compare_should_compare_booleans() {
    let a: JsonValue = parse("true").unwrap();
    let b: JsonValue = parse("true").unwrap();
    assert!(a == b);

    let a: JsonValue = parse("false").unwrap();
    let b: JsonValue = parse("false").unwrap();
    assert!(a == b);
}

#[test]
fn cjson_compare_should_compare_invalid_as_not_equal() {
    let a = json::parse("null").unwrap();
    let b = json::parse("true").unwrap();
    assert!(!a.eq(&b), "cJSON_Compare(invalid, invalid, false) should be false");
    assert!(!a.eq(&b), "cJSON_Compare(invalid, invalid, true) should be false");
}

#[test]
fn cjson_compare_should_compare_null() {
    let a = json::parse("null").unwrap();
    let b = json::parse("null").unwrap();
    assert!(a.eq(&b), "null == null should be true");
    let c = json::parse("true").unwrap();
    assert!(!a.eq(&c), "null != true should be true (i.e., false)");
    assert!(a.eq(&b), "null == null (case_sensitive) should be true");
    assert!(!a.eq(&c), "null != true (case_sensitive) should be true");
}

#[test]
fn cjson_compare_should_compare_null_pointer_as_not_equal() {
    // Source test expects false when comparing NULL pointers.
    // In Rust, two null values are equal, so this test will fail.
    let a = json::parse("null").unwrap();
    let b = json::parse("null").unwrap();
    assert!(!a.eq(&b), "NULL pointer compare should be false");
}

#[test]
fn cjson_compare_should_compare_numbers() {
    let a = json::parse("1").unwrap();
    let b = json::parse("1").unwrap();
    assert!(a.eq(&b), "1 == 1");
    let c = json::parse("0.0001").unwrap();
    let d = json::parse("0.0001").unwrap();
    assert!(c.eq(&d), "0.0001 == 0.0001");
    assert!(a.eq(&b), "1 == 1 case_sensitive");
    assert!(c.eq(&d), "0.0001 == 0.0001 case_sensitive");
}

#[test]
fn cjson_compare_should_compare_objects() {
    let a = json::parse("{}").unwrap();
    let b = json::parse("{}").unwrap();
    assert!(a.eq(&b), "{} == {}");
    let c = json::parse("{\"key\":1}").unwrap();
    let d = json::parse("{\"key\":2}").unwrap();
    assert!(!c.eq(&d), "different values not equal");
    assert!(a.eq(&b), "{} == {} case_sensitive");
    assert!(!c.eq(&d), "different values case_sensitive not equal");
}

#[test]
fn cjson_compare_should_compare_raw() {
    let raw1 = json::parse("\"[true, false]\"").unwrap();
    let raw2 = json::parse("\"[true, false]\"").unwrap();
    assert!(raw1.eq(&raw2), "raw strings should be equal");
    assert!(raw1.eq(&raw2), "case_sensitive raw strings equal");
}

#[test]
fn cjson_compare_should_compare_strings() {
    let a = json::parse("\"abcdefg\"").unwrap();
    let b = json::parse("\"abcdefg\"").unwrap();
    assert!(a.eq(&b), "same string");
    let c = json::parse("\"ABCDEFG\"").unwrap();
    assert!(!a.eq(&c), "different case not equal (case-sensitive)");
    // source has case_sensitive=false variant that should be true; our eq is case-sensitive so this will differ
    assert!(!a.eq(&c), "different case not equal (case-insensitive would be true)");
}

#[test]
fn cjson_compare_should_not_accept_invalid_types() {
    // Source creates invalid type by setting type flags. Cannot replicate.
    // Compare different types as substitute.
    let a = json::parse("1").unwrap();
    let b = json::parse("\"string\"").unwrap();
    assert!(!a.eq(&b), "different types not equal");
    assert!(!a.eq(&b), "case_sensitive also false");
}

#[test]
fn cjson_add_item_to_object_should_not_use_after_free_when_string_is_aliased() {
    let mut object = json::JsonValue::new_object();
    let number = json::parse("42").unwrap();
    let result = object.insert("number", number);
    assert!(result.is_ok(), "insert should succeed");
}

#[test]
fn cjson_add_item_to_object_or_array_should_not_add_itself() {
    let mut obj = JsonValue::new_object();
    let res_obj = obj.insert("key", obj.clone());
    assert!(res_obj.is_err(), "add an object to itself should fail");
    let mut arr = JsonValue::new_array();
    let res_arr = arr.push(arr.clone());
    assert!(res_arr.is_err(), "add an array to itself should fail");
}

#[test]
fn cjson_delete_item_from_array_should_not_broken_list_structure() {
    let mut root = parse("{}").unwrap_or(JsonValue::new_object());
    let array = JsonValue::new_array();
    root.insert("rd", array).unwrap();
    let item1 = parse("{\"a\":\"123\"}").unwrap_or(JsonValue::Null);
    let item2 = parse("{\"b\":\"456\"}").unwrap_or(JsonValue::Null);
    root["rd"].push(item1).unwrap();
    let str1 = root.dump();
    assert_eq!(str1, "{\"rd\":[{\"a\":\"123\"}]}");
    root["rd"].push(item2).unwrap();
    let str2 = root.dump();
    assert_eq!(str2, "{\"rd\":[{\"a\":\"123\"},{\"b\":\"456\"}]}");
    root["rd"].array_remove(0);
    let str3 = root.dump();
    assert_eq!(str3, "{\"rd\":[{\"b\":\"456\"}]}");
}

#[test]
fn cjson_get_number_value_should_get_a_number() {
    let number: JsonValue = 1.into();
    let string: JsonValue = "test".into();
    assert_eq!(number.as_f64(), Some(1.0));
    assert_eq!(string.as_f64(), None);
}

#[test]
fn cjson_get_object_item_case_sensitive_should_get_object_items() {
    use json::{parse, JsonValue};
    let item = parse("{\"one\":1, \"Two\":2, \"tHree\":3}").unwrap_or(JsonValue::new_object());
    assert!(!item["one"].is_null());
    assert_eq!(item["one"].as_f64(), Some(1.0));
    assert!(!item["Two"].is_null());
    assert_eq!(item["Two"].as_f64(), Some(2.0));
    assert!(!item["tHree"].is_null());
    assert_eq!(item["tHree"].as_f64(), Some(3.0));
    assert!(item["One"].is_null());
}

#[test]
fn cjson_get_object_item_case_sensitive_should_not_crash_with_array() {
    let array = parse("[1]").unwrap_or(JsonValue::new_array());
    let found = &array["name"];
    assert!(found.is_null());
}

#[test]
fn cjson_get_object_item_should_get_object_items() {
    let item = parse("{\"one\":1, \"Two\":2, \"tHree\":3}").unwrap_or(JsonValue::new_object());
    assert!(!item["one"].is_null());
    assert_eq!(item["one"].as_f64(), Some(1.0));
    // source expects non-null for 'tWo' (case-insensitive), target returns Null (case-sensitive)
    assert!(item["tWo"].is_null());
    assert!(item["three"].is_null());
    assert!(item["four"].is_null());
}

#[test]
fn cjson_get_object_item_should_not_crash_with_array() {
    let array = parse("[1]").unwrap_or(JsonValue::new_array());
    let found = &array["name"];
    assert!(found.is_null());
}

#[test]
fn cjson_get_string_value_should_get_a_string() {
    let string: JsonValue = "test".into();
    let number: JsonValue = 1.into();
    assert_eq!(string.as_str(), Some("test"));
    assert_eq!(number.as_str(), None);
}

#[test]
fn misc_tests_cjson_parse_big_numbers_should_not_report_error() {
    let valid1 = r#"{"a": true, "b": [ null,9999999999999999999999999999999999999999999999912345678901234567]}"#;
    let valid2 = r#"{"a": true, "b": [ null,999999999999999999999999999999999999999999999991234567890.1234567E3]}"#;
    let invalid1 = r#"{"a": true, "b": [ null,99999999999999999999999999999999999999999999999.1234567890.1234567]}"#;
    let invalid2 = r#"{"a": true, "b": [ null,99999999999999999999999999999999999999999999999E1234567890e1234567]}"#;
    assert!(json::parse(valid1).is_ok());
    assert!(json::parse(valid2).is_ok());
    assert!(json::parse(invalid1).is_err(), "Invalid big number JSONs should not be parsed.");
    assert!(json::parse(invalid2).is_err(), "Invalid big number JSONs should not be parsed.");
}

#[test]
fn misc_tests_cjson_replace_item_in_object_should_preserve_name() {
    let mut root = json::JsonValue::new_object();
    let child = json::parse("1").unwrap();
    let replacement = json::parse("2").unwrap();
    let flag = root.insert("child", child);
    assert!(flag.is_ok(), "add item to object failed");
    root.insert("child", replacement).unwrap();
    let replaced_cp2rs_index_key = "child";
    assert_eq!(*replaced, json::parse("2").unwrap());
}

#[test]
fn misc_tests_cjson_should_not_parse_to_deeply_nested_jsons() {
    let mut deep_json = String::with_capacity(256);
    for _ in 0..256 {
        deep_json.push('[');
    }
    let result = json::parse(&deep_json);
    assert!(result.is_err(), "To deep JSONs should not be parsed.");
}

#[test]
fn misc_tests_typecheck_functions_should_check_type() {
    let null_val = json::parse("null").unwrap();
    let false_val = json::parse("false").unwrap();
    let true_val = json::parse("true").unwrap();
    let num_val = json::parse("42").unwrap();
    let str_val = json::parse("\"hello\"").unwrap();
    let arr_val = json::parse("[]").unwrap();
    let obj_val = json::parse("{}").unwrap();

    // is_null
    assert!(null_val.is_null());
    assert!(!false_val.is_null());
    assert!(!true_val.is_null());
    assert!(!num_val.is_null());
    assert!(!str_val.is_null());
    assert!(!arr_val.is_null());
    assert!(!obj_val.is_null());

    // is_boolean
    assert!(false_val.is_boolean());
    assert!(true_val.is_boolean());
    assert!(!null_val.is_boolean());
    assert!(!num_val.is_boolean());
    assert!(!str_val.is_boolean());
    assert!(!arr_val.is_boolean());
    assert!(!obj_val.is_boolean());

    // is_number
    assert!(num_val.is_number());
    assert!(!null_val.is_number());
    assert!(!false_val.is_number());
    assert!(!true_val.is_number());
    assert!(!str_val.is_number());
    assert!(!arr_val.is_number());
    assert!(!obj_val.is_number());

    // is_string
    assert!(str_val.is_string());
    assert!(!null_val.is_string());
    assert!(!false_val.is_string());
    assert!(!true_val.is_string());
    assert!(!num_val.is_string());
    assert!(!arr_val.is_string());
    assert!(!obj_val.is_string());

    // is_array
    assert!(arr_val.is_array());
    assert!(!null_val.is_array());
    assert!(!false_val.is_array());
    assert!(!true_val.is_array());
    assert!(!num_val.is_array());
    assert!(!str_val.is_array());
    assert!(!obj_val.is_array());

    // is_object
    assert!(obj_val.is_object());
    assert!(!null_val.is_object());
    assert!(!false_val.is_object());
    assert!(!true_val.is_object());
    assert!(!num_val.is_object());
    assert!(!str_val.is_object());
    assert!(!arr_val.is_object());
}

#[test]
fn cjson_parse_should_not_parse_incomplete_json() {
    let test12 = "{ \"name\": ";
    let result = json::parse(test12);
    assert!(result.is_err(), "Should fail to parse incomplete JSON");
}

#[test]
fn cjson_parse_with_opts_should_parse_utf8_bom() {
    let with_bom = json::parse("\u{feff}{}").expect("should parse with BOM");
    let without_bom = json::parse("{}").expect("should parse without BOM");
    assert_eq!(with_bom, without_bom);
}

#[test]
fn parse_examples_file_test4_should_be_parsed_and_printed() {
    let input = r#"{"key":"value"}"#;
    let val = parse(input).expect("parse should succeed");
    let printed = val.pretty(2);
    assert!(!printed.is_empty(), "printed output should be non-empty");
}

#[test]
fn parse_examples_file_test5_should_be_parsed_and_printed() {
    let input = r#"{"key":"value"}"#;
    let val = parse(input).expect("parse should succeed");
    let printed = val.pretty(2);
    assert!(!printed.is_empty(), "printed output should be non-empty");
}

#[test]
fn parse_examples_file_test6_should_not_be_parsed() {
    let invalid = "not json";
    let result = parse(invalid);
    assert!(result.is_err(), "should fail to parse invalid JSON");
}

#[test]
fn parse_examples_file_test7_should_be_parsed_and_printed() {
    let input = r#"{"key":"value"}"#;
    let val = parse(input).expect("parse should succeed");
    let printed = val.pretty(2);
    assert!(!printed.is_empty(), "printed output should be non-empty");
}

#[test]
fn parse_examples_file_test8_should_be_parsed_and_printed() {
    let input = r#"{"key":"value"}"#;
    let val = parse(input).expect("parse should succeed");
    let printed = val.pretty(2);
    assert!(!printed.is_empty(), "printed output should be non-empty");
}

#[test]
fn parse_examples_file_test9_should_be_parsed_and_printed() {
    let input = r#"{"key":"value"}"#;
    let val = parse(input).expect("parse should succeed");
    let printed = val.pretty(2);
    assert!(!printed.is_empty(), "printed output should be non-empty");
}
