use json::{parse, JsonValue};

#[test]
fn parse_valid_object_type_checks() {
    let val = parse(r#"{"a": true}"#).unwrap();
    assert!(val.is_object());
    assert!(!val.is_array());
    assert!(!val.is_null());
    assert!(!val.is_number());
    assert!(!val.is_string());
    assert!(!val.is_boolean());
}

#[test]
fn parse_invalid_returns_err() {
    let res = parse("not json");
    assert!(res.is_err());
}

#[test]
fn parse_empty_string() {
    let res = parse("");
    assert!(res.is_err());
}

#[test]
fn parse_incomplete_json() {
    let res = parse("{ \"name\": ");
    assert!(res.is_err());
}

#[test]
fn parse_require_null_terminated() {
    let res = parse("{}x");
    assert!(res.is_err());
}

#[test]
fn get_string_value() {
    let val = parse("\"test\"").unwrap();
    assert_eq!(val.as_str(), Some("test"));
}

#[test]
fn get_number_value() {
    let val = parse("1").unwrap();
    assert_eq!(val.as_f64(), Some(1.0));
}

#[test]
fn get_object_item_case_sensitive() {
    let val = parse("{\"one\":1, \"Two\":2, \"tHree\":3}").unwrap();
    // Use indexing
    assert_eq!(val["one"].as_f64(), Some(1.0));
    assert_eq!(val["Two"].as_f64(), Some(2.0));
    assert_eq!(val["tHree"].as_f64(), Some(3.0));
    assert!(val["One"].is_null());
    // Also use Object::get directly to satisfy target_functions declaration
    if let JsonValue::Object(obj) = &val {
        assert_eq!(obj.get("one").and_then(|v| v.as_f64()), Some(1.0));
        assert_eq!(obj.get("Two").and_then(|v| v.as_f64()), Some(2.0));
        assert!(obj.get("One").is_none());
    } else {
        panic!("expected object");
    }
}

#[test]
fn has_object_item() {
    let val = parse("{\"one\":1}").unwrap();
    assert!(val.has_key("one"));
    assert!(!val.has_key("One"));
}

#[test]
fn add_bool_to_object() {
    let mut obj = JsonValue::new_object();
    obj.insert("true", true).unwrap();
    obj.insert("false", false).unwrap();
    assert_eq!(obj["true"], JsonValue::Boolean(true));
    assert_eq!(obj["false"], JsonValue::Boolean(false));
}

#[test]
fn add_number_to_object() {
    let mut obj = JsonValue::new_object();
    obj.insert("number", 42).unwrap();
    assert_eq!(obj["number"].as_f64(), Some(42.0));
}

#[test]
fn add_string_to_object() {
    let mut obj = JsonValue::new_object();
    obj.insert("string", "Hello World!").unwrap();
    assert_eq!(obj["string"].as_str(), Some("Hello World!"));
}

#[test]
fn add_object_to_object() {
    let mut obj = JsonValue::new_object();
    obj.insert("obj", JsonValue::new_object()).unwrap();
    assert!(obj["obj"].is_object());
}

#[test]
fn add_array_to_object() {
    let mut obj = JsonValue::new_object();
    obj.insert("arr", JsonValue::new_array()).unwrap();
    assert!(obj["arr"].is_array());
}

#[test]
fn add_item_to_object() {
    let mut obj = JsonValue::new_object();
    obj.insert("name", "Awesome 4K").unwrap();
    assert_eq!(obj["name"].as_str(), Some("Awesome 4K"));
}

#[test]
fn add_item_to_object_cs() {
    let mut obj = JsonValue::new_object();
    obj.insert("number", 42).unwrap();
    assert_eq!(obj["number"].as_f64(), Some(42.0));
}

#[test]
fn create_array_push_items() {
    let mut arr = JsonValue::new_array();
    arr.push(JsonValue::Null).unwrap();
    arr.push(JsonValue::Null).unwrap();
    arr.push(JsonValue::Null).unwrap();
    assert_eq!(arr.len(), 3);
}

#[test]
fn get_array_size() {
    let mut arr = JsonValue::new_array();
    arr.push(1).unwrap();
    arr.push(2).unwrap();
    arr.push(3).unwrap();
    assert_eq!(arr.len(), 3);
}

#[test]
fn delete_item_from_array() {
    let mut root = parse("{}").unwrap();
    root.insert("rd", JsonValue::new_array()).unwrap();
    let item1 = parse("{\"a\":\"123\"}").unwrap();
    let item2 = parse("{\"b\":\"456\"}").unwrap();
    root["rd"].push(item1).unwrap();
    root["rd"].push(item2).unwrap();
    root["rd"].array_remove(0);
    assert_eq!(root.dump(), "{\"rd\":[{\"b\":\"456\"}]}");
}

#[test]
fn detach_item_from_array() {
    let mut arr = JsonValue::new_array();
    arr.push(10).unwrap();
    arr.push(20).unwrap();
    let removed = arr.array_remove(0);
    assert_eq!(removed.as_f64(), Some(10.0));
    assert_eq!(arr.len(), 1);
}

#[test]
fn print_unformatted() {
    let mut obj = JsonValue::new_object();
    obj.insert("x", 1).unwrap();
    assert_eq!(obj.dump(), "{\"x\":1}");
}

#[test]
fn print_pretty_basic() {
    let mut obj = JsonValue::new_object();
    obj.insert("x", 1).unwrap();
    let pretty_str = obj.pretty(4);
    assert!(pretty_str.chars().any(|c| c == '\n'));
    assert!(pretty_str.chars().any(|c| c == ' '));
}

#[test]
fn replace_item_in_object() {
    let mut obj = JsonValue::new_object();
    obj.insert("child", 1).unwrap();
    obj.insert("child", 2).unwrap();
    assert_eq!(obj["child"].as_f64(), Some(2.0));
}

#[test]
fn object_remove() {
    let mut obj = JsonValue::new_object();
    obj.insert("key", "value").unwrap();
    assert!(obj.has_key("key"));
    let removed = obj.remove("key");
    assert!(!obj.has_key("key"));
    assert_eq!(removed.as_str(), Some("value"));
}
