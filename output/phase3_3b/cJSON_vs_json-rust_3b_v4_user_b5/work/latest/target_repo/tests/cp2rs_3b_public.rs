#[cfg(test)]
mod tests {
    use json::{JsonValue, parse, from as json_from};
    use json::object::Object;
    fn get_object_mut<'a>(j: &'a mut JsonValue) -> &'a mut Object {
        match j {
            JsonValue::Object(ref mut o) => o,
            _ => panic!()
        }
    }
    fn get_object_ref<'a>(j: &'a JsonValue) -> &'a Object {
        match j {
            JsonValue::Object(ref o) => o,
            _ => panic!()
        }
    }
    #[test]
    fn test_parse_valid() {
        let result = parse("123");
        assert!(result.is_ok());
        let v = result.unwrap();
        assert!(v.is_number());
    }
    #[test]
    fn test_parse_invalid() {
        let result = parse("abc");
        assert!(result.is_err());
    }
    #[test]
    fn test_parse_opts_handle_null() {
        let result = parse("");
        assert!(result.is_err());
    }
    #[test]
    fn test_parse_opts_empty_string() {
        let result = parse("");
        assert!(result.is_err());
    }
    #[test]
    fn test_parse_opts_require_null_terminated() {
        let result = parse("{}x");
        assert!(result.is_err());
    }
    #[test]
    fn test_parse_opts_incomplete_json() {
        let result = parse("{");
        assert!(result.is_err());
    }
    #[test]
    fn test_get_string_value() {
        let s = json_from("hello");
        assert_eq!(s.as_str(), Some("hello"));
        let n = json_from(42);
        assert_eq!(n.as_str(), None);
        let null = JsonValue::Null;
        assert_eq!(null.as_str(), None);
    }
    #[test]
    fn test_get_number_value() {
        let n = json_from(3.14);
        assert!(n.as_f64().is_some());
        assert!((n.as_f64().unwrap() - 3.14).abs() < 1e-10);
        let s = json_from("hello");
        assert!(s.as_f64().is_none());
        let null = JsonValue::Null;
        assert!(null.as_f64().is_none());
    }
    #[test]
    fn test_create_and_add_bool() {
        let mut obj = JsonValue::new_object();
        {
            let o = get_object_mut(&mut obj);
            o.insert("key", JsonValue::Boolean(true));
        }
        let o = get_object_ref(&obj);
        let item = o.get("key").unwrap();
        assert!(item.is_boolean());
        assert_eq!(item.as_bool(), Some(true));
    }
    #[test]
    fn test_create_and_add_number() {
        let mut obj = JsonValue::new_object();
        let num_val = json_from(42);
        {
            let o = get_object_mut(&mut obj);
            o.insert("num", num_val);
        }
        let o = get_object_ref(&obj);
        let item = o.get("num").unwrap();
        assert!(item.is_number());
        assert_eq!(item.as_f64(), Some(42.0));
    }
    #[test]
    fn test_create_and_add_string() {
        let mut obj = JsonValue::new_object();
        let str_val = json_from("test");
        {
            let o = get_object_mut(&mut obj);
            o.insert("str", str_val);
        }
        let o = get_object_ref(&obj);
        let item = o.get("str").unwrap();
        assert!(item.is_string());
        assert_eq!(item.as_str(), Some("test"));
    }
    #[test]
    fn test_create_and_add_true() {
        let mut obj = JsonValue::new_object();
        {
            let o = get_object_mut(&mut obj);
            o.insert("true_key", JsonValue::Boolean(true));
        }
        let o = get_object_ref(&obj);
        let item = o.get("true_key").unwrap();
        assert!(item.is_boolean());
        assert_eq!(item.as_bool(), Some(true));
    }
    #[test]
    fn test_create_and_add_false() {
        let mut obj = JsonValue::new_object();
        {
            let o = get_object_mut(&mut obj);
            o.insert("false_key", JsonValue::Boolean(false));
        }
        let o = get_object_ref(&obj);
        let item = o.get("false_key").unwrap();
        assert!(item.is_boolean());
        assert_eq!(item.as_bool(), Some(false));
    }
    #[test]
    fn test_create_and_add_object() {
        let mut obj = JsonValue::new_object();
        let nested = JsonValue::new_object();
        {
            let o = get_object_mut(&mut obj);
            o.insert("nested", nested);
        }
        let o = get_object_ref(&obj);
        let item = o.get("nested").unwrap();
        assert!(item.is_object());
    }
    #[test]
    fn test_create_and_add_array() {
        let mut obj = JsonValue::new_object();
        let arr = JsonValue::new_array();
        {
            let o = get_object_mut(&mut obj);
            o.insert("arr", arr);
        }
        let o = get_object_ref(&obj);
        let item = o.get("arr").unwrap();
        assert!(item.is_array());
    }
    #[test]
    fn test_replace_item_in_object() {
        let mut obj = JsonValue::new_object();
        let first = json_from("first");
        let second = json_from(2);
        {
            let o = get_object_mut(&mut obj);
            o.insert("key", first);
            o.insert("key", second);
        }
        let o = get_object_ref(&obj);
        let item = o.get("key").unwrap();
        assert!(item.is_number());
        assert_eq!(item.as_f64(), Some(2.0));
    }
    #[test]
    fn test_delete_item_from_array() {
        let _ = parse("42");
        let mut arr = JsonValue::new_array();
        arr.push(json_from(1)).unwrap();
        arr.push(json_from(2)).unwrap();
        arr.push(json_from(3)).unwrap();
        let removed = arr.array_remove(1);
        assert_eq!(removed.as_f64(), Some(2.0));
        assert_eq!(arr.len(), 2);
        let dump_str = arr.dump();
        assert_eq!(dump_str, "[1,3]");
    }
    #[test]
    fn test_typecheck_functions() {
        let bool_val = json_from(true);
        assert!(bool_val.is_boolean());
        assert!(!bool_val.is_null());
        assert!(!bool_val.is_number());
        assert!(!bool_val.is_string());
        assert!(!bool_val.is_array());
        assert!(!bool_val.is_object());
        let null_val = JsonValue::Null;
        assert!(null_val.is_null());
        let num_val = json_from(1);
        assert!(num_val.is_number());
        let str_val = json_from("hi");
        assert!(str_val.is_string());
        let arr_val = JsonValue::new_array();
        assert!(arr_val.is_array());
        let obj_val = JsonValue::new_object();
        assert!(obj_val.is_object());
    }
    #[test]
    fn test_create_array_reference() {
        let mut arr = JsonValue::new_array();
        arr.push(json_from(99)).unwrap();
        assert!(arr.is_array());
        assert_eq!(arr.len(), 1);
        let removed = arr.array_remove(0);
        assert!(removed.is_number());
        assert_eq!(removed.as_f64(), Some(99.0));
    }
    #[test]
    fn test_create_object_reference() {
        let mut obj = JsonValue::new_object();
        let num_val = json_from(42);
        {
            let o = get_object_mut(&mut obj);
            o.insert("key", num_val);
        }
        assert!(obj.is_object());
        let o = get_object_ref(&obj);
        let item = o.get("key").unwrap();
        assert!(item.is_number());
        assert_eq!(item.as_f64(), Some(42.0));
    }
    #[test]
    fn test_circular_reference_detection() {
        let mut arr = JsonValue::new_array();
        arr.push(json_from(10)).unwrap();
        arr.push(json_from(20)).unwrap();
        let removed = arr.array_remove(1);
        assert_eq!(removed.as_f64(), Some(20.0));
        assert_eq!(arr.len(), 1);
    }
    #[test]
    fn test_delete_item_from_object() {
        let mut obj = JsonValue::new_object();
        {
            let o = get_object_mut(&mut obj);
            o.insert("key", json_from("value"));
        }
        let removed = obj.remove("key");
        assert_eq!(removed.as_str(), Some("value"));
        assert!(!obj.has_key("key"));
    }
    #[test]
    fn test_detach_item_from_object_case_sensitive() {
        let mut obj = JsonValue::new_object();
        {
            let o = get_object_mut(&mut obj);
            o.insert("key", json_from("value"));
        }
        let detached = obj.remove("key");
        assert_eq!(detached.as_str(), Some("value"));
        assert!(!obj.has_key("key"));
    }
    #[test]
    fn test_has_object_item() {
        let mut obj = JsonValue::new_object();
        {
            let o = get_object_mut(&mut obj);
            o.insert("key", json_from(1));
        }
        assert!(obj.has_key("key"));
        assert!(!obj.has_key("nonexistent"));
    }
    #[test]
    fn test_print() {
        let result = parse("{\"a\":1}").unwrap();
        let printed = result.pretty(2);
        let expected = "{\n  \"a\": 1\n}";
        assert_eq!(printed, expected);
    }
    #[test]
    fn test_replace_item_in_object_case_sensitive() {
        let mut obj = JsonValue::new_object();
        {
            let o = get_object_mut(&mut obj);
            o.insert("key", json_from(1));
        }
        obj.insert("key", json_from("two")).unwrap();
        let o_ref = get_object_ref(&obj);
        let item = o_ref.get("key").unwrap();
        assert_eq!(item.as_str(), Some("two"));
    }
    #[test]
    fn test_delete_item_from_object_case_sensitive() {
        let mut null_val = JsonValue::Null;
        let result = null_val.remove("item");
        assert!(result.is_null());
    }
    #[test]
    fn test_detach_item_from_object() {
        let mut null_val = JsonValue::Null;
        let result = null_val.remove("item");
        assert!(result.is_null());
    }
}
