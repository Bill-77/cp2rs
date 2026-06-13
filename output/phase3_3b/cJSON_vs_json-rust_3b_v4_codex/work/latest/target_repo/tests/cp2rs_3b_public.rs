#[cfg(test)]
extern crate json;

use json::JsonValue;

#[test]
fn test_parse_handle_null() {
    assert!(json::parse("").is_err());
    assert!(json::parse("{").is_err());
}

#[test]
fn test_parse_handle_empty_string() {
    assert!(json::parse("").is_err());
}

#[test]
fn test_parse_require_null() {
    assert!(json::parse("{}x").is_err());
}

#[test]
fn test_create_object_add_bool() {
    let mut obj = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = obj {
        object.insert("true", true.into());
        object.insert("false", false.into());
    }
    if let JsonValue::Object(ref object) = obj {
        let true_item = object.get("true").expect("key true not found");
        assert!(true_item.is_boolean());
        assert!(true_item == true);
        let false_item = object.get("false").expect("key false not found");
        assert!(false_item.is_boolean());
        assert!(false_item == false);
    }
}

#[test]
fn test_create_object_add_number() {
    let mut obj = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = obj {
        object.insert("number", 42.0.into());
    }
    if let JsonValue::Object(ref object) = obj {
        let num = object.get("number").expect("key number not found");
        assert!(num.is_number());
        assert_eq!(num.as_f64(), Some(42.0));
    }
}

#[test]
fn test_create_object_add_string() {
    let mut obj = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = obj {
        object.insert("string", "Hello World!".into());
    }
    if let JsonValue::Object(ref object) = obj {
        let s = object.get("string").expect("key string not found");
        assert!(s.is_string());
        assert_eq!(s.as_str(), Some("Hello World!"));
    }
}

#[test]
fn test_create_object_add_true_false() {
    let mut obj = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = obj {
        object.insert("true", true.into());
        object.insert("false", false.into());
    }
    if let JsonValue::Object(ref object) = obj {
        let true_item = object.get("true").expect("key true not found");
        assert!(true_item.is_boolean());
        assert!(true_item == true);
        let false_item = object.get("false").expect("key false not found");
        assert!(false_item.is_boolean());
        assert!(false_item == false);
    }
}

#[test]
fn test_create_object_add_array_object() {
    let mut obj = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = obj {
        object.insert("array", JsonValue::new_array());
        object.insert("object", JsonValue::new_object());
    }
    if let JsonValue::Object(ref object) = obj {
        let arr = object.get("array").expect("key array not found");
        assert!(arr.is_array());
        let obj2 = object.get("object").expect("key object not found");
        assert!(obj2.is_object());
    }
}

#[test]
fn test_array_add_and_detach() {
    let mut arr = JsonValue::new_array();
    arr.push(42).unwrap();
    arr.push(24).unwrap();
    assert_eq!(arr.len(), 2);
    let removed = arr.array_remove(0);
    assert_eq!(removed.as_f64(), Some(42.0));
    assert_eq!(arr.len(), 1);
}

#[test]
fn test_delete_from_array() {
    let mut root = json::parse("{}").unwrap();
    let mut item1 = JsonValue::new_object();
    if let JsonValue::Object(ref mut obj) = item1 {
        obj.insert("a", "123".into());
    }
    let mut item2 = JsonValue::new_object();
    if let JsonValue::Object(ref mut obj) = item2 {
        obj.insert("b", "456".into());
    }
    let mut array = JsonValue::new_array();
    array.push(item1).unwrap();
    let mut expected1 = JsonValue::new_array();
    let mut exp_item1 = JsonValue::new_object();
    if let JsonValue::Object(ref mut o) = exp_item1 {
        o.insert("a", "123".into());
    }
    expected1.push(exp_item1).unwrap();
    assert_eq!(array.dump(), expected1.dump());
    array.push(item2).unwrap();
    let mut expected2 = JsonValue::new_array();
    let mut exp_item1b = JsonValue::new_object();
    if let JsonValue::Object(ref mut o) = exp_item1b {
        o.insert("a", "123".into());
    }
    expected2.push(exp_item1b).unwrap();
    let mut exp_item2 = JsonValue::new_object();
    if let JsonValue::Object(ref mut o) = exp_item2 {
        o.insert("b", "456".into());
    }
    expected2.push(exp_item2).unwrap();
    assert_eq!(array.dump(), expected2.dump());
    array.array_remove(0);
    let mut expected3 = JsonValue::new_array();
    let mut exp_item2b = JsonValue::new_object();
    if let JsonValue::Object(ref mut o) = exp_item2b {
        o.insert("b", "456".into());
    }
    expected3.push(exp_item2b).unwrap();
    assert_eq!(array.dump(), expected3.dump());
    if let JsonValue::Object(ref mut root_obj) = root {
        root_obj.insert("rd", array);
    }
}

#[test]
fn test_get_string_value() {
    let string_val: JsonValue = "test".into();
    let number_val: JsonValue = 1.into();
    assert_eq!(string_val.as_str(), Some("test"));
    assert_eq!(number_val.as_str(), None);
}

#[test]
fn test_get_number_value() {
    let string_val: JsonValue = "test".into();
    let number_val: JsonValue = 1.into();
    assert_eq!(number_val.as_f64(), Some(1.0));
    assert_eq!(string_val.as_f64(), None);
}

#[test]
fn test_typecheck_functions() {
    let null_val = JsonValue::Null;
    let bool_val = JsonValue::Boolean(true);
    let num_val = JsonValue::Number(42.into());
    let string_val: JsonValue = "hello".into();
    let array_val = JsonValue::new_array();
    let obj_val = JsonValue::new_object();

    assert!(null_val.is_null());
    assert!(!null_val.is_boolean());
    assert!(!null_val.is_number());
    assert!(!null_val.is_string());
    assert!(!null_val.is_array());
    assert!(!null_val.is_object());

    assert!(bool_val.is_boolean());
    assert!(!bool_val.is_null());

    assert!(num_val.is_number());
    assert!(!num_val.is_string());

    assert!(string_val.is_string());
    assert!(!string_val.is_number());

    assert!(array_val.is_array());
    assert!(!array_val.is_object());

    assert!(obj_val.is_object());
    assert!(!obj_val.is_array());
}

#[test]
fn test_replace_item_in_object() {
    let mut root = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = root {
        object.insert("child", JsonValue::Number(1.into()));
    }
    if let JsonValue::Object(ref mut object) = root {
        object.insert("child", JsonValue::Number(2.into()));
    }
    if let JsonValue::Object(ref object) = root {
        let child = object.get("child").expect("key child not found");
        assert!(child.is_number());
        assert_eq!(child.as_f64(), Some(2.0));
    }
}

#[test]
fn test_add_item_to_object_cs() {
    let mut obj = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = obj {
        object.insert("number", 42.0.into());
    }
    if let JsonValue::Object(ref object) = obj {
        let num = object.get("number").expect("key number not found");
        assert!(num.is_number());
        assert_eq!(num.as_f64(), Some(42.0));
    }
}

#[test]
fn test_delete_item_from_object() {
    let mut obj = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = obj {
        object.insert("key", "value".into());
        object.remove("key");
        assert!(object.get("key").is_none());
        // Also test case-sensitive variant (same mapping)
        object.insert("Key", "value2".into());
        object.remove("Key");
        assert!(object.get("Key").is_none());
    }
}

#[test]
fn test_has_object_item() {
    let mut obj = JsonValue::new_object();
    assert!(!obj.has_key("foo")); // empty object
    if let JsonValue::Object(ref mut o) = obj {
        o.insert("foo", 1.into());
    }
    assert!(obj.has_key("foo"));
    assert!(!obj.has_key("bar"));
    // Test on non-object types
    let null_val = JsonValue::Null;
    assert!(!null_val.has_key("foo"));
    let arr = JsonValue::new_array();
    assert!(!arr.has_key("foo"));
}

#[test]
fn test_print_pretty() {
    let mut root = JsonValue::new_object();
    if let JsonValue::Object(ref mut o) = root {
        o.insert("foo", 1.into());
        o.insert("bar", "hello".into());
    }
    let printed = root.pretty(2);
    let expected = "{\n  \"foo\": 1,\n  \"bar\": \"hello\"\n}";
    assert_eq!(printed, expected);
}

#[test]
fn test_detach_item_from_object() {
    let mut obj = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = obj {
        object.insert("detach", 42.0.into());
    }
    // Detach by key, expect Some(value)
    if let JsonValue::Object(ref mut object) = obj {
        let detached = object.remove("detach");
        assert!(detached.is_some());
        let val = detached.unwrap();
        assert!(val.is_number());
        assert_eq!(val.as_f64(), Some(42.0));
        // After detach, key should be gone
        assert!(object.get("detach").is_none());
    }
}

#[test]
fn test_detach_item_from_object_null_checks() {
    let mut obj = JsonValue::new_object();
    // Missing key returns None
    if let JsonValue::Object(ref mut object) = obj {
        assert!(object.remove("nonexistent").is_none());
        // Empty key (simulating NULL string) returns None
        assert!(object.remove("").is_none());
    }
    // Empty object returns None
    let mut empty_obj = JsonValue::new_object();
    if let JsonValue::Object(ref mut object) = empty_obj {
        assert!(object.remove("anything").is_none());
    }
}

#[test]
fn test_replace_item_in_object_case_sensitive() {
    // Normal replace on object (case-sensitive key)
    let mut obj = JsonValue::new_object();
    // Insert initial value using JsonValue::insert
    obj.insert("key", "old").unwrap();
    // Replace via insert
    obj.insert("key", "new").unwrap();
    assert_eq!(obj["key"].as_str(), Some("new"));

    // Replace with uppercase key (case-sensitive)
    obj.insert("KEY", "upper").unwrap();
    assert_eq!(obj["KEY"].as_str(), Some("upper"));
    // Original lowercase key unchanged
    assert_eq!(obj["key"].as_str(), Some("new"));

    // Test error case: calling insert on non-object (simulates NULL object)
    let mut null_val = JsonValue::Null;
    let result = null_val.insert("key", 1);
    assert!(result.is_err());
}
