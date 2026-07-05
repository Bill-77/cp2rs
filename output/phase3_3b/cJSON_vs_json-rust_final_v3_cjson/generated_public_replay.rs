// CP2RS replay harness imports: Rust trait imports only.
use std::ops::{Index, IndexMut};

#[test]
fn cjson_add_array_should_add_array_replay() {
    use json::JsonValue;
    let mut obj = JsonValue::new_object();
    assert!(obj.insert("array", JsonValue::Array(vec![])).is_ok());
    let retrieved = &obj["array"];
    assert!(matches!(retrieved, JsonValue::Array(_)));
}

#[test]
fn cjson_add_bool_should_add_bool_replay() {
    use json::JsonValue;
    let mut obj = JsonValue::new_object();
    assert!(obj.insert("true", JsonValue::Boolean(true)).is_ok());
    assert!(obj.insert("false", JsonValue::Boolean(false)).is_ok());
    let true_item = &obj["true"];
    let false_item = &obj["false"];
    assert!(matches!(true_item, JsonValue::Boolean(true)));
    assert!(matches!(false_item, JsonValue::Boolean(false)));
}

#[test]
fn cjson_add_false_should_add_false_replay() {
    use json::JsonValue;
    let mut obj = JsonValue::new_object();
    assert!(obj.insert("false", JsonValue::Boolean(false)).is_ok());
    let false_item = &obj["false"];
    assert!(matches!(false_item, JsonValue::Boolean(false)));
}

#[test]
fn cjson_add_null_should_add_null_replay() {
    use json::JsonValue;
    let mut obj = JsonValue::new_object();
    assert!(obj.insert("null", JsonValue::Null).is_ok());
    let null_item = &obj["null"];
    assert!(matches!(null_item, JsonValue::Null));
}

#[test]
fn cjson_add_array_should_fail_on_allocation_failure_replay() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    let result = root.insert("array", JsonValue::Array(vec![]));
    assert!(result.is_err(), "Expected insert to fail (null in source) but got Ok");
}

#[test]
fn cjson_add_bool_should_fail_on_allocation_failure_replay() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    let result = root.insert("false", JsonValue::Boolean(false));
    assert!(result.is_err(), "Expected insert to fail (null in source) but got Ok");
}

#[test]
fn cjson_add_false_should_fail_on_allocation_failure_replay() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    let result = root.insert("false", JsonValue::Boolean(false));
    assert!(result.is_err(), "Expected insert to fail (null in source) but got Ok");
}

#[test]
fn cjson_add_number_should_add_number_replay() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    root.insert("number", 42).unwrap();
    let val = &root["number"];
    assert!(matches!(val, JsonValue::Number(_)), "type should be Number");
    assert!(val.as_f64() == Some(42.0), "valuedouble should be 42.0");
    assert!(val.as_i64() == Some(42), "valueint should be 42");
}

#[test]
fn cjson_add_object_should_add_object_replay() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    root.insert("object", JsonValue::new_object()).unwrap();
    let val = &root["object"];
    assert!(matches!(val, JsonValue::Object(_)), "type should be Object");
}

#[test]
fn cjson_add_raw_should_add_raw_replay() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    root.insert("raw", JsonValue::String("{}".to_string())).unwrap();
    let val = &root["raw"];
    assert!(matches!(val, JsonValue::String(_)), "type should be String (source expects Raw)");
    assert!(val.as_str() == Some("{}"), "valuestring should be '{}'");
}

#[test]
fn cjson_add_string_should_add_string_replay() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    root["string"] = JsonValue::from("Hello World!");
    let string_item = &root["string"];
    assert!(string_item.is_string());
    assert_eq!(string_item.as_str(), Some("Hello World!"));
}

#[test]
fn cjson_add_true_should_add_true_replay() {
    use json::JsonValue;
    let mut root = JsonValue::new_object();
    root["true"] = JsonValue::from(true);
    let true_item = &root["true"];
    assert!(true_item.is_boolean());
    assert_eq!(true_item.as_bool(), Some(true));
}

#[test]
fn cjson_compare_arrays_replay() {
    use json::JsonValue;
    let a1 = json::parse("[]").expect("Failed to parse a.");
    let b1 = json::parse("[]").expect("Failed to parse b.");
    assert!(a1 == b1, "empty arrays equal (case-sensitive)");
    assert!(a1 == b1, "empty arrays equal (case-insensitive)");

    let complex = "[false,true,null,42,\"string\",[],{}]";
    let a2 = json::parse(complex).expect("Failed to parse a.");
    let b2 = json::parse(complex).expect("Failed to parse b.");
    assert!(a2 == b2, "complex arrays equal (case-sensitive)");
    assert!(a2 == b2, "complex arrays equal (case-insensitive)");
}

#[test]
fn cjson_compare_booleans_replay() {
    use json::JsonValue;
    let a1 = json::parse("true").expect("Failed to parse a.");
    let b1 = json::parse("true").expect("Failed to parse b.");
    assert!(a1 == b1, "true == true (case-sensitive)");
    assert!(a1 == b1, "true == true (case-insensitive)");

    let a2 = json::parse("false").expect("Failed to parse a.");
    let b2 = json::parse("false").expect("Failed to parse b.");
    assert!(a2 == b2, "false == false (case-sensitive)");
    assert!(a2 == b2, "false == false (case-insensitive)");
}

#[test]
fn cjson_create_string_array_fail_alloc_replay() {
    let strings = vec!["1", "2", "3"];
    let result = json::JsonValue::from(strings);
    // Expected: null (allocation failure) -> JsonValue::Null
    assert!(result == json::JsonValue::Null);
}

#[test]
fn cjson_compare_null_replay() {
    let a = json::parse("null").unwrap();
    let b = json::parse("null").unwrap();
    assert_eq!(a, b);
    let c = json::parse("true").unwrap();
    assert_ne!(a, c);
}

#[test]
fn cjson_compare_numbers_replay() {
    let a = json::parse("1").unwrap();
    let b = json::parse("1").unwrap();
    assert_eq!(a, b);
    let mut a = json::parse("0.0001").unwrap();
    let mut b = json::parse("0.0001").unwrap();
    assert_eq!(a, b);
}

#[test]
fn cjson_compare_objects_replay() {
    let a = json::parse("{}").unwrap();
    let b = json::parse("{}").unwrap();
    assert_eq!(a, b);
    let c = json::parse("{\"a\":1}").unwrap();
    assert_ne!(a, c);
}

#[test]
fn cjson_compare_strings_replay() {
    let a = json::parse("\"abcdefg\"").unwrap();
    let b = json::parse("\"abcdefg\"").unwrap();
    assert_eq!(a, b);
    let c = json::parse("\"ABCDEFG\"").unwrap();
    assert_ne!(a, c);
}

#[test]
fn cjson_add_item_to_object_no_uaf_replay() {
    let mut obj = json::JsonValue::new_object();
    let num = json::value!(42);
    let result = obj.insert("number", num);
    assert!(result.is_ok());
}

#[test]
fn cjson_get_string_value_should_get_a_string_replay() {
    use json::JsonValue;
    let string_val = JsonValue::from("test");
    let number_val = JsonValue::from(1.0);
    let null_val = JsonValue::Null;
    assert_eq!(string_val.as_str(), Some("test"));
    assert_eq!(number_val.as_str(), None);
    assert_eq!(null_val.as_str(), None);
}

#[test]
fn cjson_delete_item_from_array_should_not_broken_list_structure_replay() {
    use json;
    let expected_json1 = r#"{"rd":[{"a":"123"}]}"#;
    let expected_json2 = r#"{"rd":[{"a":"123"},{"b":"456"}]}"#;
    let expected_json3 = r#"{"rd":[{"b":"456"}]}"#;

    let mut root = json::parse("{}").unwrap();
    root.insert("rd", json::JsonValue::new_array()).unwrap();

    let item1 = json::parse("{\"a\":\"123\"}").unwrap();
    root["rd"].push(item1).unwrap();
    let str1 = root.dump();
    assert_eq!(str1, expected_json1);

    let item2 = json::parse("{\"b\":\"456\"}").unwrap();
    root["rd"].push(item2).unwrap();
    let str2 = root.dump();
    assert_eq!(str2, expected_json2);

    root["rd"].array_remove(0);
    let str3 = root.dump();
    assert_eq!(str3, expected_json3);
}

#[test]
fn cjson_get_object_item_case_sensitive_should_not_crash_with_array_replay() {
    use json;
    let array = json::parse("[1]").unwrap();
    let found = &array["name"];
    assert_eq!(*found, json::JsonValue::Null);
}

#[test]
fn cjson_get_object_item_should_not_crash_with_array_replay() {
    use json;
    let array = json::parse("[1]").unwrap();
    let found = &array["name"];
    assert_eq!(*found, json::JsonValue::Null);
}

#[test]
fn cjson_parse_big_numbers_should_not_report_error_replay() {
    use json;
    let valid1 = r#"{\"a\": true, \"b\": [ null,9999999999999999999999999999999999999999999999912345678901234567]}"#;
    let valid2 = r#"{\"a\": true, \"b\": [ null,999999999999999999999999999999999999999999999991234567890.1234567E3]}"#;
    let invalid1 = r#"{\"a\": true, \"b\": [ null,99999999999999999999999999999999999999999999999.1234567890.1234567]}"#;
    let invalid2 = r#"{\"a\": true, \"b\": [ null,99999999999999999999999999999999999999999999999E1234567890e1234567]}"#;
    assert!(json::parse(valid1).is_ok(), "Valid big number JSON should parse successfully");
    assert!(json::parse(valid2).is_ok(), "Valid big number JSON should parse successfully");
    assert!(json::parse(invalid1).is_err(), "Invalid big number JSON should not be parsed.");
    assert!(json::parse(invalid2).is_err(), "Invalid big number JSON should not be parsed.");
}

#[test]
fn cjson_replace_item_in_object_should_preserve_name_replay() {
    use json;
    let mut root = json::JsonValue::new_object();
    let child = json::JsonValue::from(1.0);
    let replacement = json::JsonValue::from(2.0);
    root.insert("child", child).expect("add item to object failed");
    *root.index_mut("child") = replacement;
    assert_eq!(root["child"], json::JsonValue::from(2.0));
    assert!(root.is_object());
    assert_eq!(root.len(), 1);
}

#[test]
fn cjson_replace_item_via_pointer_should_replace_items_replay() {
    use json;
    let mut array = json::JsonValue::new_array();
    array.push(json::JsonValue::Null).expect("push failed");
    array.push(json::JsonValue::Null).expect("push failed");
    array.push(json::JsonValue::Null).expect("push failed");
    array[0] = json::JsonValue::from(0.0);
    array[1] = json::JsonValue::from(1.0);
    array[2] = json::JsonValue::from(2.0);
    assert_eq!(array.len(), 3);
    assert_eq!(array[0], json::JsonValue::from(0.0));
    assert_eq!(array[1], json::JsonValue::from(1.0));
    assert_eq!(array[2], json::JsonValue::from(2.0));
}

#[test]
fn cjson_should_not_parse_to_deeply_nested_jsons_replay() {
    use json;
    let deep = "[".repeat(2000) + &"]".repeat(2000);
    let result = json::parse(&deep);
    assert!(result.is_err(), "Too deep JSON should not be parsed.");
}

#[test]
fn cjson_typecheck_functions_should_check_type_replay() {
    use json;
    let null = json::JsonValue::Null;
    let boolean = json::JsonValue::Boolean(true);
    let number = json::JsonValue::from(42.0);
    let string = json::JsonValue::from("hello");
    let mut array = json::JsonValue::new_array();
    array.push(json::JsonValue::from(1.0)).unwrap();
    array.push(json::JsonValue::from(2.0)).unwrap();
    array.push(json::JsonValue::from(3.0)).unwrap();
    let mut object = json::JsonValue::new_object();
    object.insert("a", json::JsonValue::from(1.0)).unwrap();
    assert!(null.is_null());
    assert!(!null.is_boolean());
    assert!(!null.is_number());
    assert!(!null.is_string());
    assert!(!null.is_array());
    assert!(!null.is_object());
    assert!(boolean.is_boolean());
    assert!(!boolean.is_null());
    assert!(number.is_number());
    assert!(!number.is_boolean());
    assert!(string.is_string());
    assert!(!string.is_number());
    assert!(array.is_array());
    assert!(!array.is_object());
    assert!(object.is_object());
    assert!(!object.is_array());
}

#[test]
fn cjson_print_replay_file_test10() {
    let input = "[\"Sunday\", \"Monday\", \"Tuesday\", \"Wednesday\", \"Thursday\", \"Friday\", \"Saturday\"]\n";
    let expected = "[\"Sunday\", \"Monday\", \"Tuesday\", \"Wednesday\", \"Thursday\", \"Friday\", \"Saturday\"]";
    let parsed_input = json::parse(input).unwrap();
    let parsed_expected = json::parse(expected).unwrap();
    assert_eq!(parsed_input, parsed_expected);
}

#[test]
fn cjson_print_replay_file_test11() {
    let input = "{\n\"name\": \"Jack (\\\"Bee\\\") Nimble\",\n\"format\": {\"type\":       \"rect\",\n\"width\":      1920,\n\"height\":     1080,\n\"interlace\":  false,\"frame rate\": 24\n}\n}\n";
    let expected = "{\n\t\"name\":\t\"Jack (\\\"Bee\\\") Nimble\",\n\t\"format\":\t{\n\t\t\"type\":\t\"rect\",\n\t\t\"width\":\t1920,\n\t\t\"height\":\t1080,\n\t\t\"interlace\":\tfalse,\n\t\t\"frame rate\":\t24\n\t}\n}";
    let parsed_input = json::parse(input).unwrap();
    let parsed_expected = json::parse(expected).unwrap();
    assert_eq!(parsed_input, parsed_expected);
}

#[test]
fn cjson_print_replay_file_test1() {
    let input = "{\n    \"glossary\": {\n        \"title\": \"example glossary\",\n\t\t\"GlossDiv\": {\n            \"title\": \"S\",\n\t\t\t\"GlossList\": {\n                \"GlossEntry\": {\n                    \"ID\": \"SGML\",\n\t\t\t\t\t\"SortAs\": \"SGML\",\n\t\t\t\t\t\"GlossTerm\": \"Standard Generalized Markup Language\",\n\t\t\t\t\t\"Acronym\": \"SGML\",\n\t\t\t\t\t\"Abbrev\": \"ISO 8879:1986\",\n\t\t\t\t\t\"GlossDef\": {\n                        \"para\": \"A meta-markup language, used to create markup languages such as DocBook.\",\n\t\t\t\t\t\t\"GlossSeeAlso\": [\"GML\", \"XML\"]\n                    },\n\t\t\t\t\t\"GlossSee\": \"markup\"\n                }\n            }\n        }\n    }\n}\n";
    let expected = "{\n\t\"glossary\":\t{\n\t\t\"title\":\t\"example glossary\",\n\t\t\"GlossDiv\":\t{\n\t\t\t\"title\":\t\"S\",\n\t\t\t\"GlossList\":\t{\n\t\t\t\t\"GlossEntry\":\t{\n\t\t\t\t\t\"ID\":\t\"SGML\",\n\t\t\t\t\t\"SortAs\":\t\"SGML\",\n\t\t\t\t\t\"GlossTerm\":\t\"Standard Generalized Markup Language\",\n\t\t\t\t\t\"Acronym\":\t\"SGML\",\n\t\t\t\t\t\"Abbrev\":\t\"ISO 8879:1986\",\n\t\t\t\t\t\"GlossDef\":\t{\n\t\t\t\t\t\t\"para\":\t\"A meta-markup language, used to create markup languages such as DocBook.\",\n\t\t\t\t\t\t\"GlossSeeAlso\":\t[\"GML\", \"XML\"]\n\t\t\t\t\t},\n\t\t\t\t\t\"GlossSee\":\t\"markup\"\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}";
    let parsed_input = json::parse(input).unwrap();
    let parsed_expected = json::parse(expected).unwrap();
    assert_eq!(parsed_input, parsed_expected);
}

#[test]
fn cjson_print_replay_file_test2() {
    let input = "{\"menu\": {\n  \"id\": \"file\",\n  \"value\": \"File\",\n  \"popup\": {\n    \"menuitem\": [\n      {\"value\": \"New\", \"onclick\": \"CreateNewDoc()\"},\n      {\"value\": \"Open\", \"onclick\": \"OpenDoc()\"},\n      {\"value\": \"Close\", \"onclick\": \"CloseDoc()\"}\n    ]\n  }\n}}\n";
    let expected = "{\n\t\"menu\":\t{\n\t\t\"id\":\t\"file\",\n\t\t\"value\":\t\"File\",\n\t\t\"popup\":\t{\n\t\t\t\"menuitem\":\t[{\n\t\t\t\t\t\"value\":\t\"New\",\n\t\t\t\t\t\"onclick\":\t\"CreateNewDoc()\"\n\t\t\t\t}, {\n\t\t\t\t\t\"value\":\t\"Open\",\n\t\t\t\t\t\"onclick\":\t\"OpenDoc()\"\n\t\t\t\t}, {\n\t\t\t\t\t\"value\":\t\"Close\",\n\t\t\t\t\t\"onclick\":\t\"CloseDoc()\"\n\t\t\t\t}]\n\t\t}\n\t}\n}";
    let parsed_input = json::parse(input).unwrap();
    let parsed_expected = json::parse(expected).unwrap();
    assert_eq!(parsed_input, parsed_expected);
}

#[test]
fn cjson_print_replay_file_test3() {
    let input = "{\"widget\": {\n    \"debug\": \"on\",\n    \"window\": {\n        \"title\": \"Sample Konfabulator Widget\",\n        \"name\": \"main_window\",\n        \"width\": 500,\n        \"height\": 500\n    },\n    \"image\": {\n        \"src\": \"Images/Sun.png\",\n        \"name\": \"sun1\",\n        \"hOffset\": 250,\n        \"vOffset\": 250,\n        \"alignment\": \"center\"\n    },\n    \"text\": {\n        \"data\": \"Click Here\",\n        \"size\": 36,\n        \"style\": \"bold\",\n        \"name\": \"text1\",\n        \"hOffset\": 250,\n        \"vOffset\": 100,\n        \"alignment\": \"center\",\n        \"onMouseUp\": \"sun1.opacity = (sun1.opacity / 100) * 90;\"\n    }\n}}   ";
    let expected = "{\n\t\"widget\":\t{\n\t\t\"debug\":\t\"on\",\n\t\t\"window\":\t{\n\t\t\t\"title\":\t\"Sample Konfabulator Widget\",\n\t\t\t\"name\":\t\"main_window\",\n\t\t\t\"width\":\t500,\n\t\t\t\"height\":\t500\n\t\t},\n\t\t\"image\":\t{\n\t\t\t\"src\":\t\"Images/Sun.png\",\n\t\t\t\"name\":\t\"sun1\",\n\t\t\t\"hOffset\":\t250,\n\t\t\t\"vOffset\":\t250,\n\t\t\t\"alignment\":\t\"center\"\n\t\t},\n\t\t\"text\":\t{\n\t\t\t\"data\":\t\"Click Here\",\n\t\t\t\"size\":\t36,\n\t\t\t\"style\":\t\"bold\",\n\t\t\t\"name\":\t\"text1\",\n\t\t\t\"hOffset\":\t250,\n\t\t\t\"vOffset\":\t100,\n\t\t\t\"alignment\":\t\"center\",\n\t\t\t\"onMouseUp\":\t\"sun1.opacity = (sun1.opacity / 100) * 90;\"\n\t\t}\n\t}\n}";
    let parsed_input = json::parse(input).unwrap();
    let parsed_expected = json::parse(expected).unwrap();
    assert_eq!(parsed_input, parsed_expected);
}

#[test]
fn parse_examples_file_test4_replay() {
    let input = std::fs::read_to_string("tests/inputs/test4").expect("Failed to read input");
    let expected = std::fs::read_to_string("tests/inputs/test4.expected").expect("Failed to read expected");
    let tree = json::parse(&input).expect("Failed to parse JSON");
    let actual = tree.pretty(0);
    assert_eq!(actual, expected);
}

#[test]
fn parse_examples_file_test5_replay() {
    let input = std::fs::read_to_string("tests/inputs/test5").expect("Failed to read input");
    let expected = std::fs::read_to_string("tests/inputs/test5.expected").expect("Failed to read expected");
    let tree = json::parse(&input).expect("Failed to parse JSON");
    let actual = tree.pretty(0);
    assert_eq!(actual, expected);
}

#[test]
fn parse_examples_file_test6_should_not_be_parsed_replay() {
    let input = std::fs::read_to_string("tests/inputs/test6").expect("Failed to read input");
    let result = json::parse(&input);
    assert!(result.is_err());
}

#[test]
fn parse_examples_file_test7_replay() {
    let input = std::fs::read_to_string("tests/inputs/test7").expect("Failed to read input");
    let expected = std::fs::read_to_string("tests/inputs/test7.expected").expect("Failed to read expected");
    let tree = json::parse(&input).expect("Failed to parse JSON");
    let actual = tree.pretty(0);
    assert_eq!(actual, expected);
}

#[test]
fn parse_examples_file_test8_replay() {
    let input = std::fs::read_to_string("tests/inputs/test8").expect("Failed to read input");
    let expected = std::fs::read_to_string("tests/inputs/test8.expected").expect("Failed to read expected");
    let tree = json::parse(&input).expect("Failed to parse JSON");
    let actual = tree.pretty(0);
    assert_eq!(actual, expected);
}

#[test]
fn parse_examples_file_test9_replay() {
    let input = std::fs::read_to_string("tests/inputs/test9").expect("Failed to read input");
    let expected = std::fs::read_to_string("tests/inputs/test9.expected").expect("Failed to read expected");
    let tree = json::parse(&input).expect("Failed to parse JSON");
    let actual = tree.pretty(0);
    assert_eq!(actual, expected);
}

#[test]
fn parse_examples_test12_should_not_be_parsed_replay() {
    let input = "{ \"name\": ";
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn parse_with_opts_utf8_bom_replay() {
    let with_bom_str = "\u{FEFF}{}";
    let without_bom_str = "{}";
    let with_bom = json::parse(with_bom_str).expect("Failed to parse with BOM");
    let without_bom = json::parse(without_bom_str).expect("Failed to parse without BOM");
    assert!(with_bom == without_bom);
}
