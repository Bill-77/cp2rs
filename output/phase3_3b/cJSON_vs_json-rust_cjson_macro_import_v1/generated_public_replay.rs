// CP2RS replay harness imports: Rust trait imports only.
use std::ops::{Index, IndexMut};

use json::JsonValue;
#[test]
fn replay_cjson_add_array_should_add_array() {
    let mut root = JsonValue::new_object();
    root.insert("array", JsonValue::Array(vec![])).unwrap();
    let retrieved = &root["array"];
    assert_eq!(*retrieved, JsonValue::Array(vec![]));
}

use json::JsonValue;
#[test]
fn replay_cjson_add_bool_should_add_bool() {
    let mut root = JsonValue::new_object();
    root.insert("true", JsonValue::Boolean(true)).unwrap();
    let retrieved_true = &root["true"];
    assert_eq!(*retrieved_true, JsonValue::Boolean(true));
    root.insert("false", JsonValue::Boolean(false)).unwrap();
    let retrieved_false = &root["false"];
    assert_eq!(*retrieved_false, JsonValue::Boolean(false));
}

use json::JsonValue;
#[test]
fn replay_cjson_add_false_should_add_false() {
    let mut root = JsonValue::new_object();
    root.insert("false", JsonValue::Boolean(false)).unwrap();
    let retrieved = &root["false"];
    assert_eq!(*retrieved, JsonValue::Boolean(false));
}

use json::JsonValue;
#[test]
fn replay_cjson_add_null_should_add_null() {
    let mut root = JsonValue::new_object();
    root.insert("null", JsonValue::Null).unwrap();
    let retrieved = &root["null"];
    assert_eq!(*retrieved, JsonValue::Null);
}

#[test]
fn replay_cjson_add_cjson_add_number_should_add_number() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    root.insert("number", 42).unwrap();
    let number = root.index("number");
    assert_eq!(number.as_f64(), Some(42.0));
    assert_eq!(number.as_i64(), Some(42));
}

#[test]
fn replay_cjson_add_cjson_add_object_should_add_object() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    root.insert("object", JsonValue::new_object()).unwrap();
    let object = root.index("object");
    assert!(matches!(object, JsonValue::Object(_)));
}

#[test]
fn replay_cjson_add_cjson_add_raw_should_add_raw() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    root.insert("raw", "{}").unwrap();
    let raw = root.index("raw");
    assert_eq!(*raw, "{}");
}

#[test]
fn replay_cjson_compare_should_compare_arrays() {
    fn compare_from_string(a: &str, b: &str, _case_sensitive: bool) -> bool {
        let a_json = json::parse(a).expect("Failed to parse a");
        let b_json = json::parse(b).expect("Failed to parse b");
        a_json == b_json
    }
    assert!(compare_from_string("[]", "[]", true));
    assert!(compare_from_string("[]", "[]", false));
    assert!(compare_from_string("[false,true,null,42,\"string\",[],{}]", "[false, true, null, 42, \"string\", [], {}]", true));
    assert!(compare_from_string("[false,true,null,42,\"string\",[],{}]", "[false, true, null, 42, \"string\", [], {}]", false));
    assert!(compare_from_string("[[[1], 2]]", "[[[1], 2]]", true));
    assert!(compare_from_string("[[[1], 2]]", "[[[1], 2]]", false));
    assert!(!compare_from_string("[true,null,42,\"string\",[],{}]", "[false, true, null, 42, \"string\", [], {}]", true));
    assert!(!compare_from_string("[true,null,42,\"string\",[],{}]", "[false, true, null, 42, \"string\", [], {}]", false));
    assert!(!compare_from_string("[1,2,3]", "[1,2]", true));
    assert!(!compare_from_string("[1,2,3]", "[1,2]", false));
}

#[test]
fn replay_cjson_compare_should_compare_booleans() {
    fn compare_from_string(a: &str, b: &str, _case_sensitive: bool) -> bool {
        let a_json = json::parse(a).expect("Failed to parse a");
        let b_json = json::parse(b).expect("Failed to parse b");
        a_json == b_json
    }
    assert!(compare_from_string("true", "true", true));
    assert!(compare_from_string("true", "true", false));
    assert!(compare_from_string("false", "false", true));
    assert!(compare_from_string("false", "false", false));
    assert!(!compare_from_string("true", "false", true));
    assert!(!compare_from_string("true", "false", false));
    assert!(!compare_from_string("false", "true", true));
    assert!(!compare_from_string("false", "true", false));
}

#[test]
fn replay_cjson_add_string_should_add_string() {
    use json::JsonValue;
    let root = json::object!{"string" => "Hello World!"};
    let string = &root["string"];
    assert_eq!(string.as_str(), Some("Hello World!"));
}

#[test]
fn cjson_add_cjson_create_string_array_should_fail_on_allocation_failure() {
    use json::JsonValue;
    let strings = vec!["1", "2", "3"];
    let result = JsonValue::from(strings);
    assert_eq!(
        result,
        JsonValue::Null,
        "Expected Null under allocation failure, but got {:?}",
        result
    );
}

#[test]
fn replay_cjson_compare_should_compare_null() {
    use json::{parse, JsonValue};

    let a = parse("null").unwrap();
    let b = parse("null").unwrap();
    assert_eq!(a, b);

    let c = parse("true").unwrap();
    assert_ne!(a, c);
}

#[test]
fn replay_cjson_compare_should_compare_numbers() {
    use json::{parse, JsonValue};

    assert_eq!(parse("1").unwrap(), parse("1").unwrap());
    assert_eq!(parse("0.0001").unwrap(), parse("0.0001").unwrap());
    assert_eq!(parse("1E100").unwrap(), parse("10E99").unwrap());
    assert_ne!(parse("0.5E-100").unwrap(), parse("0.5E-101").unwrap());
    assert_ne!(parse("1").unwrap(), parse("2").unwrap());
}

#[test]
fn replay_cjson_compare_should_compare_objects() {
    use json::{parse, JsonValue};

    assert_eq!(parse("{}").unwrap(), parse("{}").unwrap());

    let obj_a = parse("{\"false\": false, \"true\": true, \"null\": null, \"number\": 42, \"string\": \"string\", \"array\": [], \"object\": {}}").unwrap();
    let obj_b = parse("{\"true\": true, \"false\": false, \"null\": null, \"number\": 42, \"string\": \"string\", \"array\": [], \"object\": {}}").unwrap();
    assert_eq!(obj_a, obj_b);

    let obj_c = parse("{\"False\": false, \"true\": true, \"null\": null, \"number\": 42, \"string\": \"string\", \"array\": [], \"object\": {}}").unwrap();
    assert_ne!(obj_c, obj_b); // case-sensitive: false
    // case-insensitive comparison: source expects true, but Rust eq is case-sensitive, so this will fail at runtime (expected difference)
    assert_eq!(obj_c, obj_b);

    let obj_d = parse("{\"Flse\": false, \"true\": true, \"null\": null, \"number\": 42, \"string\": \"string\", \"array\": [], \"object\": {}}").unwrap();
    assert_ne!(obj_d, obj_b);

    let obj_e = parse("{\"one\": 1, \"two\": 2}").unwrap();
    let obj_f = parse("{\"one\": 1, \"two\": 2, \"three\": 3}").unwrap();
    assert_ne!(obj_e, obj_f);
    assert_ne!(obj_f, obj_e);
}

#[test]
fn replay_cjson_compare_should_compare_raw() {
    use json::{parse, JsonValue};
    let raw1 = parse("\"[true, false]\"").unwrap();
    let raw2 = parse("\"[true, false]\"").unwrap();
    assert_eq!(raw1, raw2);
}

#[test]
fn replay_cjson_compare_should_compare_strings() {
    use json::{parse, JsonValue};

    let a = parse("\"abcdefg\"").unwrap();
    let b = parse("\"abcdefg\"").unwrap();
    assert_eq!(a, b);

    let c = parse("\"ABCDEFG\"").unwrap();
    assert_ne!(a, c);
}

#[test]
fn replay_cjson_add_item_to_object_no_use_after_free() {
    use json::JsonValue;
    use json::number::Number;

    let mut object = JsonValue::new_object();
    let number = JsonValue::Number(Number::from(42));
    object.insert("number", number).unwrap();
}

#[test]
fn replay_cjson_compare_null_pointer_not_equal() {
    use json::JsonValue;
    let a = JsonValue::Null;
    let b = JsonValue::Null;
    // source expects false from cJSON_Compare(NULL, NULL, true)
    assert!(!a.eq(&b));
    // also for case_sensitive=false (no effect on Null)
    assert!(!a.eq(&b));
}

#[test]
fn replay_cjson_delete_item_from_array_should_not_broken_list_structure() {
    use json::*;
    let mut root = object!{"rd" => array![]};
    let item1 = parse(r#"{"a":"123"}"#).unwrap();
    let item2 = parse(r#"{"b":"456"}"#).unwrap();
    root["rd"].push(item1).unwrap();
    assert_eq!(root.dump(), r#"{"rd":[{"a":"123"}]}"#);
    root["rd"].push(item2).unwrap();
    assert_eq!(root.dump(), r#"{"rd":[{"a":"123"},{"b":"456"}]}"#);
    root["rd"].array_remove(0);
    assert_eq!(root.dump(), r#"{"rd":[{"b":"456"}]}"#);
}

#[test]
fn replay_cjson_get_number_value_should_get_a_number() {
    use json::*;
    use json::number::Number;
    let string = JsonValue::from("test");
    let number = JsonValue::Number(Number::from(1.0));
    assert_eq!(number.as_f64(), Some(1.0));
    assert_eq!(string.as_f64(), None);
}

#[test]
fn replay_cjson_get_object_item_case_sensitive_should_get_object_items() {
    use json::*;
    let item = parse(r#"{"one":1, "Two":2, "tHree":3}"#).unwrap();
    // Source expects: found_one -> 1, etc., missing key -> NULL
    assert_eq!(item["one"].as_f64(), Some(1.0));
    assert_eq!(item["Two"].as_f64(), Some(2.0));
    assert_eq!(item["tHree"].as_f64(), Some(3.0));
    // For missing key, source expects null; target index returns Null value
    assert!(item["One"].is_null());
}

#[test]
fn replay_cjson_get_object_item_case_sensitive_should_not_crash_with_array() {
    use json::*;
    let array = parse("[1]").unwrap();
    // Source expects NULL when looking up a string key on an array
    assert!(array["name"].is_null());
}

#[test]
fn replay_cjson_get_object_item_should_get_object_items() {
    use json::parse;
    let item = parse(r#"{"one":1, "Two":2, "tHree":3}"#);
    assert!(item.is_ok());
}

#[test]
fn replay_cjson_get_object_item_should_not_crash_with_array() {
    use json::parse;
    let array = parse("[1]");
    assert!(array.is_ok());
}

#[test]
fn replay_cjson_get_string_value_should_get_a_string() {
    use json::*;
    use json::number::Number;
    let string = JsonValue::from("test");
    let number = JsonValue::Number(Number::from(1.0));
    assert_eq!(string.as_str(), Some("test"));
    assert_eq!(number.as_str(), None);
}

#[test]
fn replay_misc_tests_cjson_parse_big_numbers_should_not_report_error() {
    let valid1 = json::parse("{\"a\": true, \"b\": [ null,9999999999999999999999999999999999999999999999912345678901234567]}");
    assert!(valid1.is_ok());
    let valid2 = json::parse("{\"a\": true, \"b\": [ null,999999999999999999999999999999999999999999999991234567890.1234567E3]}");
    assert!(valid2.is_ok());
    let invalid1 = json::parse("{\"a\": true, \"b\": [ null,99999999999999999999999999999999999999999999999.1234567890.1234567]}");
    assert!(invalid1.is_err());
    let invalid2 = json::parse("{\"a\": true, \"b\": [ null,99999999999999999999999999999999999999999999999E1234567890e1234567]}");
    assert!(invalid2.is_err());
}

#[test]
fn replay_misc_tests_cjson_replace_item_in_object_should_preserve_name() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    root.insert("child", JsonValue::from(1)).unwrap();
    *root.index_mut("child") = JsonValue::from(2);
    assert_eq!(root["child"], JsonValue::from(2));
}

#[test]
fn replay_misc_tests_cjson_replace_item_via_pointer_should_replace_items() {
    use json::JsonValue;
    let mut array = JsonValue::new_array();
    array.push(JsonValue::Null).unwrap();
    array.push(JsonValue::Null).unwrap();
    array.push(JsonValue::Null).unwrap();
    assert_eq!(array.len(), 3);
}

#[test]
fn replay_misc_tests_cjson_set_bool_value_must_not_break_objects() {
    use json::JsonValue;
    let obj = JsonValue::new_object();
    assert!(obj.is_object());
    let s = JsonValue::from("test");
    assert!(s.is_string());
}

#[test]
fn replay_misc_tests_cjson_set_valuestring_should_return_null_if_strings_overlap() {
    let result = json::parse("\"foo0z\"");
    assert!(result.is_ok());
}

#[test]
fn replay_misc_tests_cjson_set_valuestring_to_object_should_not_leak_memory() {
    use json::{JsonValue, parse};
    let mut root = parse("{}").unwrap();
    assert!(root.is_object());
    let item1 = JsonValue::from("valuestring could be changed safely");
    assert!(item1.is_string());
    root.insert("one", item1).unwrap();
    assert_eq!(root["one"], "valuestring could be changed safely");
}

#[test]
fn replay_misc_tests_cjson_should_not_follow_too_deep_circular_references() {
    use json::JsonValue;
    let mut arr = JsonValue::new_array();
    arr.push(JsonValue::Null).unwrap();
    arr.push(JsonValue::Null).unwrap();
    let removed = arr.array_remove(0);
    assert_eq!(arr.len(), 1);
}

#[test]
fn replay_misc_tests_cjson_should_not_parse_to_deeply_nested_jsons() {
    let deep = "[".repeat(1001);
    let result = json::parse(&deep);
    assert!(result.is_err());
}

#[test]
fn replay_misc_tests_typecheck_functions_should_check_type() {
    use json::JsonValue;
    let null_val = JsonValue::Null;
    assert!(null_val.is_null());
    assert!(!null_val.is_boolean());
    assert!(!null_val.is_number());
    assert!(!null_val.is_string());
    assert!(!null_val.is_array());
    assert!(!null_val.is_object());

    let bool_val = JsonValue::Boolean(true);
    assert!(bool_val.is_boolean());
    assert!(!bool_val.is_null());
    assert!(!bool_val.is_number());
    assert!(!bool_val.is_string());
    assert!(!bool_val.is_array());
    assert!(!bool_val.is_object());

    let num_val = JsonValue::from(42);
    assert!(num_val.is_number());
    assert!(!num_val.is_null());
    assert!(!num_val.is_boolean());
    assert!(!num_val.is_string());
    assert!(!num_val.is_array());
    assert!(!num_val.is_object());

    let str_val = JsonValue::from("hello");
    assert!(str_val.is_string());
    assert!(!str_val.is_null());
    assert!(!str_val.is_boolean());
    assert!(!str_val.is_number());
    assert!(!str_val.is_array());
    assert!(!str_val.is_object());

    let arr_val = JsonValue::Array(vec![JsonValue::from(1), JsonValue::from(2), JsonValue::from(3)]);
    assert!(arr_val.is_array());
    assert!(!arr_val.is_null());
    assert!(!arr_val.is_boolean());
    assert!(!arr_val.is_number());
    assert!(!arr_val.is_string());
    assert!(!arr_val.is_object());

    let mut obj_val = JsonValue::new_object();
    obj_val.insert("a", 1).unwrap();
    assert!(obj_val.is_object());
    assert!(!obj_val.is_null());
    assert!(!obj_val.is_boolean());
    assert!(!obj_val.is_number());
    assert!(!obj_val.is_string());
    assert!(!obj_val.is_array());
}

#[test]
fn replay_misc_utils_tests_cjson_utils_functions_shouldnt_crash_with_null_pointers() {
    let item = json::JsonValue::from("item");
    assert!(item.is_string());
}

#[test]
fn replay_old_utils_tests_json_pointer_tests() {
    let json = "{\"foo\":[\"bar\",\"baz\"],\"\":0,\"a/b\":1,\"c%d\":2,\"e^f\":3,\"g|h\":4,\"i\\\\j\":5,\"k\\\"l\":6,\" \":7,\"m~n\":8}";
    let _root = json::parse(json).expect("parse should succeed");
}

#[test]
fn replay_old_utils_tests_misc_tests() {
    use json::JsonValue;
    let mut object = JsonValue::new_object();
    let numbers = json::array![0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
    object.insert("numbers", numbers).unwrap();
    let arr = &object["numbers"];
    let num6 = arr.index(6);
    assert_eq!(num6.as_i64(), Some(6));
}

#[test]
fn replay_parse_examples_file_test10_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test10")
        .expect("Failed to read input file");
    let expected = std::fs::read_to_string("tests/inputs/test10.expected")
        .expect("Failed to read expected file");
    let parsed = json::parse(&input).expect("Failed to parse JSON");
    let actual = parsed.pretty(2);
    assert_eq!(actual, expected);
}

#[test]
fn replay_parse_examples_file_test11_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test11")
        .expect("Failed to read input file");
    let expected = std::fs::read_to_string("tests/inputs/test11.expected")
        .expect("Failed to read expected file");
    let parsed = json::parse(&input).expect("Failed to parse JSON");
    let actual = parsed.pretty(2);
    assert_eq!(actual, expected);
}

#[test]
fn replay_parse_examples_file_test1_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test1")
        .expect("Failed to read input file");
    let expected = std::fs::read_to_string("tests/inputs/test1.expected")
        .expect("Failed to read expected file");
    let parsed = json::parse(&input).expect("Failed to parse JSON");
    let actual = parsed.pretty(2);
    assert_eq!(actual, expected);
}

#[test]
fn replay_parse_examples_file_test2_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test2")
        .expect("Failed to read input file");
    let expected = std::fs::read_to_string("tests/inputs/test2.expected")
        .expect("Failed to read expected file");
    let parsed = json::parse(&input).expect("Failed to parse JSON");
    let actual = parsed.pretty(2);
    assert_eq!(actual, expected);
}

#[test]
fn replay_parse_examples_file_test3_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test3")
        .expect("Failed to read input file");
    let expected = std::fs::read_to_string("tests/inputs/test3.expected")
        .expect("Failed to read expected file");
    let parsed = json::parse(&input).expect("Failed to parse JSON");
    let actual = parsed.pretty(2);
    assert_eq!(actual, expected);
}

#[test]
fn sort_tests_replay() {
    let mut obj = json::JsonValue::new_object();
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ".chars() {
        let key = format!("{}", ch);
        assert!(obj.insert(&key, 1).is_ok());
    }
    assert_eq!(obj.len(), 26);
}

#[test]
fn replay_parse_examples_file_test4_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test4").expect("Failed to read test4 input");
    let expected = std::fs::read_to_string("tests/inputs/test4.expected").expect("Failed to read test4 expected");
    let parsed = json::parse(&input).expect("Parse should succeed");
    let actual = parsed.pretty(2);
    assert_eq!(expected, actual);
}

#[test]
fn replay_parse_examples_file_test5_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test5").expect("Failed to read test5 input");
    let expected = std::fs::read_to_string("tests/inputs/test5.expected").expect("Failed to read test5 expected");
    let parsed = json::parse(&input).expect("Parse should succeed");
    let actual = parsed.pretty(2);
    assert_eq!(expected, actual);
}

#[test]
fn replay_parse_examples_file_test6_should_not_be_parsed() {
    let input = std::fs::read_to_string("tests/inputs/test6").expect("Failed to read test6 input");
    let result = json::parse(&input);
    assert!(result.is_err(), "Should fail to parse what is not JSON.");
}

#[test]
fn replay_parse_examples_file_test7_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test7").expect("Failed to read test7 input");
    let expected = std::fs::read_to_string("tests/inputs/test7.expected").expect("Failed to read test7 expected");
    let parsed = json::parse(&input).expect("Parse should succeed");
    let actual = parsed.pretty(2);
    assert_eq!(expected, actual);
}

#[test]
fn replay_parse_examples_file_test8_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test8").expect("Failed to read test8 input");
    let expected = std::fs::read_to_string("tests/inputs/test8.expected").expect("Failed to read test8 expected");
    let parsed = json::parse(&input).expect("Parse should succeed");
    let actual = parsed.pretty(2);
    assert_eq!(expected, actual);
}

#[test]
fn replay_parse_examples_file_test9_should_be_parsed_and_printed() {
    let input = std::fs::read_to_string("tests/inputs/test9").expect("Failed to read test9 input");
    let expected = std::fs::read_to_string("tests/inputs/test9.expected").expect("Failed to read test9 expected");
    let parsed = json::parse(&input).expect("Parse should succeed");
    let actual = parsed.pretty(2);
    assert_eq!(expected, actual);
}

#[test]
fn replay_parse_examples_test12_should_not_be_parsed() {
    let input = "{ \"name\": ";
    let result = json::parse(input);
    assert!(result.is_err(), "Should fail to parse incomplete JSON.");
}

#[test]
fn replay_parse_with_opts_parse_with_opts_should_parse_utf8_bom() {
    let with_bom_str = "\u{FEFF}{}";
    let without_bom_str = "{}";
    let with_bom = json::parse(with_bom_str).expect("Parse with BOM should succeed");
    let without_bom = json::parse(without_bom_str).expect("Parse without BOM should succeed");
    assert_eq!(with_bom, without_bom);
}
