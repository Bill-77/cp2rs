use std::collections::BTreeMap;
use std::ops::IndexMut;
use json::JsonValue;

#[test]
fn main_charreaderallowdropnulltest_issue178() {
    let doc = "[,,,]";
    let result = json::parse(doc);
    assert!(result.is_ok());
    let root = result.unwrap();
    let _size = root.len();
}#[test]
fn main_charreaderallowspecialfloatstest_specialfloat() {
    let doc1 = "{\"a\": NaN}";
    let result1 = json::parse(doc1);
    assert!(result1.is_err());
    let err1 = result1.unwrap_err();
    assert!(err1.to_string().contains("Syntax error: value, object or array expected.") || err1.to_string().contains("value"));
    let doc2 = "{\"a\": Infinity}";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
    let err2 = result2.unwrap_err();
    assert!(err2.to_string().contains("Syntax error: value, object or array expected.") || err2.to_string().contains("value"));
}#[test]
fn main_charreaderfailifextratest_commentafterbool() {
    let doc = " true /*trailing\ncomment*/";
    let result = json::parse(doc);
    assert!(result.is_ok());
    let root = result.unwrap();
    assert_eq!(root.as_bool(), Some(true));
}#[test]
fn main_charreaderallownumerickeystest_allownumerickeys() {
    let doc = r#"{15:true,-16:true,12.01:true}"#;
    let root = json::parse(doc).expect("parse should succeed");
    assert_eq!(root.len(), 3);
    assert_eq!(root["15"].as_bool(), Some(true));
    assert_eq!(root["-16"].as_bool(), Some(true));
    assert_eq!(root["12.01"].as_bool(), Some(true));
}#[test]
fn main_charreaderallowsinglequotestest_issue182() {
    let doc1 = r#"{'a':true,"b":true}"#;
    let root1 = json::parse(doc1).expect("parse should succeed");
    assert_eq!(root1.len(), 2);
    assert_eq!(root1["a"].as_bool(), Some(true));
    assert_eq!(root1["b"].as_bool(), Some(true));
    let doc2 = r#"{'a': 'x', "b":'y'}"#;
    let root2 = json::parse(doc2).expect("parse should succeed");
    assert_eq!(root2.len(), 2);
    assert_eq!(root2["a"].as_str(), Some("x"));
    assert_eq!(root2["b"].as_str(), Some("y"));
}#[test]
fn main_charreaderallowspecialfloatstest_issue209() {
    let doc = r#"{"a":NaN,"b":Infinity,"c":-Infinity,"d":+Infinity}"#;
    let root = json::parse(doc).expect("parse should succeed");
    assert_eq!(root.len(), 4);
    let n = root["a"].as_f64();
    assert!(n.map(f64::is_nan).unwrap_or(false));
    assert_eq!(root["b"].as_f64(), Some(f64::INFINITY));
    assert_eq!(root["c"].as_f64(), Some(f64::NEG_INFINITY));
    assert_eq!(root["d"].as_f64(), Some(f64::INFINITY));
}#[test]
fn main_charreaderallowzeroestest_issue176() {
    let doc1 = r#"{'a':true,"b":true}"#;
    let root1 = json::parse(doc1).expect("parse should succeed");
    assert_eq!(root1.len(), 2);
    assert_eq!(root1["a"].as_bool(), Some(true));
    assert_eq!(root1["b"].as_bool(), Some(true));
    let doc2 = r#"{'a': 'x', "b":'y'}"#;
    let root2 = json::parse(doc2).expect("parse should succeed");
    assert_eq!(root2.len(), 2);
    assert_eq!(root2["a"].as_str(), Some("x"));
    assert_eq!(root2["b"].as_str(), Some("y"));
}#[test]
fn main_charreaderfailifextratest_commentafterarray() {
    let doc = r#"[ "property" , "value" ] //trailing
//comment
"#;
    let root = json::parse(doc).expect("parse should succeed");
    assert_eq!(root[1].as_str(), Some("value"));
}#[test]
fn main_charreaderfailifextratest_commentafterobject() {
    let doc = r#"{ "property" : "value" } //trailing
//comment
"#;
    let root = json::parse(doc).expect("parse should succeed");
    assert_eq!(root["property"].as_str(), Some("value"));
}#[test]
fn main_charreaderfailifextratest_issue107() {
    let doc = "1:2:3";
    let result = json::parse(doc);
    assert!(result.is_err(), "Expected parse failure due to extra data");
    // Source also expects error message: "* Line 1, Column 2\n  Extra non-whitespace after JSON value.\n"
    // and root.asInt() == 1, but Rust parse does not provide a value on error.
    // These assertions cannot be replicated with the target public API.
}#[test]
fn main_charreaderfailifextratest_parsecomment() {
    let doc1 = " true //comment1\n//comment2\r//comment3\r\n";
    let result1 = json::parse(doc1);
    assert!(result1.is_ok());
    let val1 = result1.unwrap();
    assert_eq!(val1.as_bool(), Some(true));
    let doc2 = " true //com\rment";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
}#[test]
fn main_charreadertest_parsechinesewithoneerror() {
    let doc = "{ \"pr佐藤erty\" :: \"value\" }";
    let result = json::parse(doc);
    assert!(result.is_err());
}#[test]
fn main_charreadertest_parsewithdetailerror() {
    let doc = "{ \"property\" : \"v\\alue\" }";
    let result = json::parse(doc);
    assert!(result.is_err());
}#[test]
fn main_charreaderfailifextratest_issue164() {
    let doc = r#" "property" : "value" }"#;
    let result = json::parse(doc);
    assert!(result.is_ok(), "first parse should succeed");
    let root = result.unwrap();
    assert_eq!(root.as_str(), Some("property"));
    let result2 = json::parse(doc);
    assert!(result2.is_err(), "second parse should fail");
}#[test]
fn main_charreadertest_parsecomment() {
    let doc1 = "//comment1\n { //comment2\n \"property\" : \"value\" //comment3\n } //comment4\n";
    let result = json::parse(doc1);
    assert!(result.is_ok(), "parse with comments should succeed");
    let root = result.unwrap();
    assert_eq!(root["property"].as_str(), Some("value"));
    let doc2 = "{ \"property\" //comment\n : \"value\" }";
    let result2 = json::parse(doc2);
    assert!(result2.is_err(), "parse with comment inside member name should fail");
}#[test]
fn main_charreadertest_parsenumber() {
    let doc = "[111111111111111111111]";
    let result = json::parse(doc);
    assert!(result.is_ok(), "parse should succeed");
    let root = result.unwrap();
    let val = root[0].as_f64().unwrap();
    let expected = 1.1111111111111111e20;
    assert!((val - expected).abs() < 1e5, "value should match expected double");
}#[test]
fn main_charreadertest_parsestring() {
    let doc1 = "[\"\"]";
    let result = json::parse(doc1);
    assert!(result.is_ok(), "parse empty string array should succeed");
    let root = result.unwrap();
    assert_eq!(root[0].as_str(), Some(""));
    let doc2 = "[\"\\u8A2a\"]";
    let result2 = json::parse(doc2);
    assert!(result2.is_ok(), "parse unicode escape should succeed");
    let root2 = result2.unwrap();
    assert_eq!(root2[0].as_str(), Some("訪"));
}#[test]
fn main_charreaderstrictmodetest_dupkeys() {
    let doc = r#"({ "property" : "value", "key" : "val1", "key" : "val2" })"#;
    let result = json::parse(doc);
    assert!(result.is_err());
    let err_str = result.unwrap_err().to_string();
    let expected = "* Line 1, Column 41\n  Duplicate key: 'key'\n";
    assert_eq!(err_str, expected);
}#[test]
fn main_charreadertest_parsearraywitherrors() {
    // first subtest
    let doc1 = "[ \"value\" ";
    let result1 = json::parse(doc1);
    assert!(result1.is_err());
    let err1 = result1.unwrap_err().to_string();
    assert_eq!(err1, "* Line 1, Column 11\n  Missing ',' or ']' in array declaration\n");
    // second subtest
    let doc2 = r#"[ "value1" "value2" ]"#;
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
    let err2 = result2.unwrap_err().to_string();
    assert_eq!(err2, "* Line 1, Column 12\n  Missing ',' or ']' in array declaration\n");
}#[test]
fn main_charreadertest_parseobjectwitherrors() {
    // first subtest
    let doc1 = r#"({ "property" : "value" )"#;
    let result1 = json::parse(doc1);
    assert!(result1.is_err());
    let err1 = result1.unwrap_err().to_string();
    assert_eq!(err1, "* Line 1, Column 24\n  Missing ',' or '}' in object declaration\n");
    // second subtest
    let doc2 = r#"({ "property" : "value" ,)"#;
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
    let err2 = result2.unwrap_err().to_string();
    assert_eq!(err2, "* Line 1, Column 25\n  Missing '}' or object member name\n");
}#[test]
fn main_charreadertest_parsewithnoerrors() {
    let doc = r#"{ "property" : "value" }"#;
    let result = json::parse(doc);
    assert!(result.is_ok());
}#[test]
fn main_charreadertest_parsewithnoerrorstestingoffsets() {
    let doc = r#"{ "property" : ["value", "value2"], "obj" : { "nested" : -6.2e+15, "num" : +123, "bool" : true}, "null" : null, "false" : false }"#;
    let result = json::parse(doc);
    assert!(result.is_ok());
}#[test]
fn main_charreadertest_parsewithoneerror() {
    let doc = r#"{ "property" :: "value" }"#;
    let result = json::parse(doc);
    assert!(result.is_err());
    let expected_err = "* Line 1, Column 15\n  Syntax error: value, object or array expected.\n";
    assert_eq!(result.unwrap_err().to_string(), expected_err);
}#[test]
fn main_charreadertest_parsewithstacklimit() {
    let doc = r#"{ "property" : "value" }"#;
    // Part 1: stackLimit=2 (ignored in target)
    let root = json::parse(doc).unwrap();
    assert!(root.has_key("property"));
    assert_eq!(root["property"].as_str(), Some("value"));
    // Part 2: source expects exception with stackLimit=1; target cannot enforce, so assert error
    let result2 = json::parse(doc);
    assert!(result2.is_err());
}#[test]
fn main_escapesequencetest_charreaderparseescapesequence() {
    let doc = "[\"\\\"\",\"\\/\",\"\\\\\",\"\\b\",\"\\f\",\"\\n\",\"\\r\",\"\\t\",\"\\u0278\",\"\\ud852\\udf62\"]";
    let result = json::parse(doc);
    assert!(result.is_ok());
}#[test]
fn main_escapesequencetest_readerparseescapesequence() {
    let doc = "[\"\\\"\",\"\\/\",\"\\\\\",\"\\b\",\"\\f\",\"\\n\",\"\\r\",\"\\t\",\"\\u0278\",\"\\ud852\\udf62\"]\n";
    let result = json::parse(doc);
    assert!(result.is_ok());
}#[test]
fn main_escapesequencetest_writeescapesequence() {
    let root = json::parse("[\"\\\"\",\"\\\\\",\"\\b\",\"\\f\",\"\\n\",\"\\r\",\"\\t\",\"\\u0278\",\"\\ud852\\udf62\"]").unwrap();
    let result = root.dump();
    let expected = "[\"\\\"\",\"\\\\\",\"\\b\",\"\\f\",\"\\n\",\"\\r\",\"\\t\",\"\\u0278\",\"\\ud852\\udf62\"]\n";
    assert_eq!(result, expected);
}#[test]
fn main_fastwritertest_dropnullplaceholders() {
    let null_val = json::parse("null").unwrap();
    assert_eq!(null_val.dump(), "null\n");
    // dropNullPlaceholders not available in target; attempt to replicate second expectation
    assert_eq!(null_val.dump(), "\n");
}#[test]
fn main_fastwritertest_enableyamlcompatibility() {
    let root = json::parse("{\"hello\":\"world\"}").unwrap();
    assert_eq!(root.dump(), "{\"hello\":\"world\"}\n");
    // enableYAMLCompatibility not available; attempt second expectation
    assert_eq!(root.dump(), "{\"hello\": \"world\"}\n");
}#[test]
fn main_fastwritertest_omitendinglinefeed() {
    let null_val = json::parse("null").unwrap();
    assert_eq!(null_val.dump(), "null\n");
    // omitEndingLineFeed not available; attempt second expectation
    assert_eq!(null_val.dump(), "null");
}#[test]
fn main_fastwritertest_writearrays() {
    let expected = "{\n\"property1\":[\"value1\",\"value2\"],\n\"property2\":[]\n}\n";
    let mut map = BTreeMap::new();
    map.insert("property1", JsonValue::from(vec!["value1", "value2"]));
    map.insert("property2", JsonValue::from(Vec::<&str>::new()));
    let root = JsonValue::from(map);
    let result = root.dump();
    assert_eq!(expected, result);
}#[test]
fn main_iteratortest_constness() {
    let expected = " 9,10,11,";
    let mut map = BTreeMap::new();
    for i in 9..12 {
        let key = format!("{:>2}", i);
        let val = JsonValue::from(key.as_str());
        map.insert(key, val);
    }
    let value = JsonValue::from(map);
    let mut out = String::new();
    for (_k, v) in value.entries() {
        out.push_str(v.as_str().unwrap());
        out.push(',');
    }
    assert_eq!(expected, out);
}#[test]
fn main_iteratortest_decrement() {
    let mut map = BTreeMap::new();
    map.insert("k1".to_string(), JsonValue::from("a"));
    map.insert("k2".to_string(), JsonValue::from("b"));
    let json = JsonValue::from(map);
    let values: Vec<&str> = json.entries().map(|(_, v)| v.as_str().unwrap()).collect();
    let reversed: Vec<&str> = values.into_iter().rev().collect();
    assert_eq!(reversed, vec!["b", "a"]);
}#[test]
fn main_iteratortest_distance() {
    let mut map = BTreeMap::new();
    map.insert("k1", JsonValue::from("a"));
    map.insert("k2", JsonValue::from("b"));
    let json = JsonValue::from(map);
    let mut i = 0i64;
    for (dist, _) in json.members().enumerate() {
        assert_eq!(i, dist as i64);
        i += 1;
    }
    let empty = JsonValue::from(BTreeMap::<&str, JsonValue>::new());
    assert_eq!(0, empty.members().count());
}#[test]
fn main_fastwritertest_writenestedobjects() {
    let mut child_map = BTreeMap::new();
    child_map.insert("nested".to_string(), JsonValue::from(Some(123)));
    child_map.insert("bool".to_string(), JsonValue::from(Some(true)));
    let child = JsonValue::from(child_map);
    let mut root_map = BTreeMap::new();
    root_map.insert("object1".to_string(), child);
    root_map.insert("object2".to_string(), JsonValue::from(BTreeMap::<String, JsonValue>::new()));
    let root = JsonValue::from(root_map);
    let result = root.dump();
    let expected = "{\"object1\":{\"bool\":true,\"nested\":123},\"object2\":{}}\n";
    assert_eq!(result, expected);
}#[test]
fn main_fastwritertest_writenumericvalue() {
    let mut map = BTreeMap::new();
    map.insert("emptyValue".to_string(), JsonValue::from(None::<bool>));
    map.insert("false".to_string(), JsonValue::from(Some(false)));
    map.insert("null".to_string(), JsonValue::from("null"));
    map.insert("number".to_string(), JsonValue::from(Some(-6.2e15f64)));
    map.insert("real".to_string(), JsonValue::from(Some(1.256f64)));
    map.insert("uintValue".to_string(), JsonValue::from(Some(17u32)));
    let root = JsonValue::from(map);
    let result = root.dump();
    let expected = "{\"emptyValue\":null,\"false\":false,\"null\":\"null\",\"number\":-6200000000000000.0,\"real\":1.256,\"uintValue\":17}\n";
    assert_eq!(result, expected);
}#[test]
fn main_iteratortest_reverseiterator() {
    let mut json = json::parse(r#"{"k1":"a","k2":"b"}"#).unwrap();
    let mut values: Vec<Option<&str>> = Vec::new();
    for v in json.members_mut() {
        values.push(v.as_str());
    }
    values.reverse();
    assert_eq!(values, vec![Some("b"), Some("a")]);
}#[test]
fn main_membertemplateas_behavessameasnamedas() {
    let jstr = json::JsonValue::from("hello world");
    assert_eq!(jstr.as_str(), Some("hello world"));
}#[test]
fn main_membertemplateis_behavessameasnamedis() {
    let values = [
        json::parse("true").unwrap(),
        json::parse("142").unwrap(),
        json::parse("40.63").unwrap(),
        json::parse("\"hello world\"").unwrap(),
    ];
    for (i, v) in values.iter().enumerate() {
        assert_eq!(v.is_boolean(), i == 0);
        assert_eq!(v.is_number(), i == 1 || i == 2);
        assert_eq!(v.is_string(), i == 3);
    }
}#[test]
fn main_parsewithstructurederrorstest_singleerror() {
    let result = json::parse("{ 1 : 2 }");
    assert!(result.is_err());
}#[test]
fn main_parsewithstructurederrorstest_success() {
    let result = json::parse("{}");
    assert!(result.is_ok());
    let root = result.unwrap();
    assert_eq!(root.len(), 0);
}#[test]
fn main_readertest_allowdroppednullplaceholders() {
    let mut root = json::parse("[1,,2]").unwrap();
    assert_eq!(root.len(), 3);
    let mut iter = root.members_mut();
    assert_eq!(iter.next().unwrap().as_i32(), Some(1));
    assert!(iter.next().unwrap().is_null());
    assert_eq!(iter.next().unwrap().as_i32(), Some(2));
    assert!(iter.next().is_none());
}#[test]
fn main_readertest_allownumerickeystest() {
    let result = json::parse("{ 123: \"a\" }");
    assert!(result.is_err());
}#[test]
fn main_readertest_parsearray() {
    let result = json::parse("[ ");
    assert!(result.is_err());
}#[test]
fn main_readertest_parsechinesewithoneerror() {
    let result = json::parse("{ \"中国\": ");
    assert!(result.is_err());
}#[test]
fn main_readertest_parsecomment() {
    let input = r#"({ /*commentBeforeValue*/ ": " }//commentAfterValue)"#;
    assert!(json::parse(input).is_err());
}#[test]
fn main_readertest_parseobject() {
    let input = r#"({ " : " })"#;
    assert!(json::parse(input).is_err());
}#[test]
fn main_readertest_parsespecialfloat() {
    let input = r#"({ " : Infi })"#;
    assert!(json::parse(input).is_err());
}#[test]
fn main_readertest_parsestring() {
    let input = r#"([ " ])"#;
    assert!(json::parse(input).is_err());
}#[test]
fn main_readertest_parsewithdetailerror() {
    let input = r#"({ " : " })"#;
    assert!(json::parse(input).is_err());
}#[test]
fn main_readertest_parsewithnoerrors() {
    let input = r#"({ " : " })"#;
    assert!(json::parse(input).is_err());
}#[test]
fn main_readertest_parsewithnoerrorstestingoffsets() {
    let input = r#"({)"#;
    assert!(json::parse(input).is_err());
}#[test]
fn main_readertest_parsewithoneerror() {
    let input = r#"({ " :: " })"#;
    assert!(json::parse(input).is_err());
}#[test]
fn main_readertest_streamparsewithnoerrors() {
    let input = r#"({ " : " })"#;
    assert!(json::parse(input).is_err());
}#[test]
fn main_readertest_strictmodeparsenumber() {
    assert!(json::parse("123").is_err());
}#[test]
fn main_streamwritertest_dropnullplaceholders() {
    let v = json::parse("null").unwrap();
    assert_eq!(json::stringify(v.clone()), "null");
    assert!(json::stringify(v).is_empty());
}#[test]
fn main_streamwritertest_enableyamlcompatibility() {
    let root = json::parse("{\"hello\":\"world\"}").unwrap();
    assert_eq!(json::stringify(root.clone()), "{\"hello\":\"world\"}");
    assert_eq!(json::stringify(root), "{\"hello\": \"world\"}");
}#[test]
fn main_streamwritertest_escapecontrolcharacters() {
    let root = json::parse("{\"test\":\"\\n\"}").unwrap();
    assert!(json::stringify(root).contains("\\n"));
}#[test]
fn main_streamwritertest_escapetabcharacterwindows() {
    let root = json::parse("{\"test\":\"\\t\"}").unwrap();
    assert!(json::stringify(root).contains("\\t"));
}#[test]
fn main_streamwritertest_indentation() {
    let root = json::parse("{\"hello\":\"world\"}").unwrap();
    assert_eq!(json::stringify(root.clone()), "{\"hello\":\"world\"}");
    assert_eq!(json::stringify(root), "{\n\t\"hello\" : \"world\"\n}");
}#[test]
fn main_streamwritertest_multilinearray() {
    let arr21 = json::parse("[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]").unwrap();
    let expected21 = "[\n\t0,\n\t1,\n\t2,\n\t3,\n\t4,\n\t5,\n\t6,\n\t7,\n\t8,\n\t9,\n\t10,\n\t11,\n\t12,\n\t13,\n\t14,\n\t15,\n\t16,\n\t17,\n\t18,\n\t19,\n\t20\n]";
    assert_eq!(json::stringify(arr21), expected21);
    let arr10 = json::parse("[0,1,2,3,4,5,6,7,8,9]").unwrap();
    let expected10 = "[ 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 ]";
    assert_eq!(json::stringify(arr10), expected10);
}#[test]
fn main_streamwritertest_unicode() {
    let root = json::parse("{\"test\":\"\\u00e9\"}").unwrap();
    assert!(json::stringify(root).contains("\\u00e9"));
}#[test]
fn main_streamwritertest_writearrays() {
    let expected = "{\n\t\"property1\" : \n\t[\n\t\t\"value1\",\n\t\t\"value2\"\n\t],\n\t\"property2\" : []\n}";
    let root = json::parse(expected).unwrap();
    assert_eq!(json::stringify(root), expected);
}#[test]
fn main_streamwritertest_writenestedobjects() {
    let expected = "{\n\t\"object1\" : \n\t{\n\t\t\"bool\" : true,\n\t\t\"nested\" : 123\n\t},\n\t\"object2\" : {}\n}";
    let root = json::parse(expected).unwrap();
    assert_eq!(json::stringify(root), expected);
}#[test]
fn main_streamwritertest_writezeroes() {
    use json::{stringify, JsonValue};
    let root = JsonValue::from("hi");
    let out = stringify(root);
    let expected = "\"hi\"";
    assert_eq!(expected.len(), out.len(), "length mismatch");
    assert_eq!(expected, out, "content mismatch");
}#[test]
fn main_styledstreamwritertest_writearrays() {
    let mut map = BTreeMap::new();
    map.insert("property1".to_string(), JsonValue::from(vec![
        JsonValue::from("value1"),
        JsonValue::from("value2")
    ]));
    map.insert("property2".to_string(), JsonValue::from(Vec::<JsonValue>::new()));
    let root = JsonValue::from(map);
    let result = root.pretty(4);
    let expected = "{\n\t\"property1\" : [ \"value1\", \"value2\" ],\n\t\"property2\" : []\n}\n";
    assert_eq!(expected, result);
}#[test]
fn main_styledwritertest_writearrays() {
    let mut map = BTreeMap::new();
    map.insert("property1".to_string(), JsonValue::from(vec![
        JsonValue::from("value1"),
        JsonValue::from("value2")
    ]));
    map.insert("property2".to_string(), JsonValue::from(Vec::<JsonValue>::new()));
    let root = JsonValue::from(map);
    let result = root.pretty(3);
    let expected = "{\n   \"property1\" : [ \"value1\", \"value2\" ],\n   \"property2\" : []\n}\n";
    assert_eq!(expected, result);
}#[test]
fn main_valuetest_arrays() {
    let empty_array: JsonValue = Vec::<JsonValue>::new().into();
    let array1: JsonValue = vec![JsonValue::from("a")].into();
    assert!(empty_array.is_array());
    assert!(array1.is_array());
    assert!(!empty_array.is_object());
    assert!(!array1.is_object());
    assert!(!empty_array.is_null());
    assert!(!array1.is_null());
    assert!(!empty_array.is_boolean());
    assert!(!array1.is_boolean());
    assert!(!empty_array.is_number());
    assert!(!array1.is_number());
    assert!(!empty_array.is_string());
    assert!(!array1.is_string());
    let mut arr = array1.clone();
    let removed = arr.array_remove(0);
    assert_eq!(removed, JsonValue::from("a"));
    assert_eq!(arr.len(), 0);
}#[test]
fn main_valuetest_comparearray() {
    let empty_array: JsonValue = Vec::<JsonValue>::new().into();
    let a = JsonValue::from("a");
    let b = JsonValue::from("b");
    let c = JsonValue::from("c");
    let d = JsonValue::from("d");
    let l1a_array: JsonValue = vec![a.clone()].into();
    let l1b_array: JsonValue = vec![b.clone()].into();
    let l2a_array: JsonValue = vec![a.clone(), b.clone()].into();
    let l2b_array: JsonValue = vec![c.clone(), d.clone()].into();
    assert_eq!(empty_array, empty_array.clone());
    assert_eq!(l1a_array, l1a_array.clone());
    assert_eq!(l1b_array, l1b_array.clone());
    assert_eq!(l2a_array, l2a_array.clone());
    assert_eq!(l2b_array, l2b_array.clone());
}#[test]
fn main_styledwritertest_writevaluewithcomment() {
    let val = json::JsonValue::from("hello");
    let result = val.pretty(2);
    let expected = "\n//commentBeforeValue\n\"hello\"\n";
    assert_eq!(result, expected);
}#[test]
fn main_valuetest_arrayissue252() {
    let arr = json::JsonValue::from(vec!["a","b","c","d","e"]);
    assert_eq!(arr.len(), 5);
}#[test]
fn main_valuetest_commentbefore() {
    let val = json::JsonValue::from(None::<i32>);
    let result = json::stringify(val.clone());
    let expected = "// this comment should appear before\nnull";
    assert_eq!(result, expected);
    let res2 = val.pretty(2);
    let exp2 = "\n// this comment should appear before\nnull\n";
    assert_eq!(res2, exp2);
}#[test]
fn main_valuetest_comparenull() {
    let null1 = json::JsonValue::from(None::<i32>);
    let null2 = json::JsonValue::from(None::<i32>);
    assert_eq!(null1, null2);
}#[test]
fn main_valuetest_compareobject() {
    let empty = json::JsonValue::from(BTreeMap::<&str, json::JsonValue>::new());
    let mut map1 = BTreeMap::new();
    map1.insert("key1", json::JsonValue::from("a"));
    let _l1a = json::JsonValue::from(map1);
}#[test]
fn main_valuetest_membercount() {
    let empty_array = JsonValue::from(Vec::<&str>::new());
    assert_eq!(empty_array.len(), 0);
    let empty_object = JsonValue::from(BTreeMap::<&str, &str>::new());
    assert_eq!(empty_object.len(), 0);
    let array1 = JsonValue::from(vec!["a"]);
    assert_eq!(array1.len(), 1);
    let mut map = BTreeMap::new();
    map.insert("key", "value");
    let object1 = JsonValue::from(map);
    assert_eq!(object1.len(), 1);
}#[test]
fn main_valuetest_null() {
    let null_val = JsonValue::from(None::<&str>);
    assert!(null_val.is_null());
    assert!(!null_val.is_boolean());
    assert!(!null_val.is_number());
    assert!(!null_val.is_string());
    assert!(!null_val.is_array());
    assert!(!null_val.is_object());
}#[test]
fn main_valuetest_objects() {
    let empty: JsonValue = JsonValue::from(BTreeMap::<&str, JsonValue>::new());
    assert!(empty.is_object());
    assert!(!empty.is_null());
    assert!(!empty.is_boolean());
    assert!(!empty.is_number());
    assert!(!empty.is_string());
    assert!(!empty.is_array());
    let mut obj: JsonValue = JsonValue::from(BTreeMap::<&str, JsonValue>::new());
    *obj.index_mut("key") = JsonValue::from("value");
    let removed = obj.remove("key");
    assert!(removed.is_string());
    assert_eq!(removed.as_str(), Some("value"));
    assert!(obj.is_object());
}#[test]
fn main_valuetest_copymovearray() {
    let array1 = JsonValue::from(vec![
        JsonValue::from("item1"),
        JsonValue::from("item2"),
    ]);
    let array2 = JsonValue::from(vec![
        JsonValue::from("item1"),
        JsonValue::from("item2"),
    ]);
    assert_eq!(array1.len(), 2);
    assert_eq!(array2.len(), 2);
    let moved = array1;
    assert_eq!(moved.len(), 2);
}#[test]
fn main_valuetest_copyobject() {
    let array_copy = JsonValue::from(vec![
        JsonValue::from("a"),
        JsonValue::from("b"),
        JsonValue::from("c"),
        JsonValue::from("d"),
    ]);
    let array_val = JsonValue::from(vec![
        JsonValue::from("a"),
        JsonValue::from("b"),
        JsonValue::from("c"),
        JsonValue::from("d"),
        JsonValue::from("e"),
    ]);
    assert_eq!(array_copy.len(), 4);
    assert_eq!(array_val.len(), 5);
}#[test]
fn main_valuetest_getarrayvalue() {
    let array = JsonValue::from(vec![
        JsonValue::from(0i32),
        JsonValue::from(1i32),
        JsonValue::from(2i32),
        JsonValue::from(3i32),
        JsonValue::from(4i32),
    ]);
    assert_eq!(array.len(), 5);
}#[test]
fn main_valuetest_precision() {
    let mut val = 100.0 / 3.0;
    assert_eq!(json::stringify(val), "33.333");
    val = 0.25000000;
    assert_eq!(json::stringify(val), "0.25");
    val = 0.2563456;
    assert_eq!(json::stringify(val), "0.25635");
    // precision=1 case (source uses same builder with changed precision)
    val = 0.2563456;
    assert_eq!(json::stringify(val), "0.3");
}#[test]
fn main_valuetest_specialfloats() {
    assert_eq!(json::stringify(f64::NAN), "NaN");
    assert_eq!(json::stringify(f64::INFINITY), "Infinity");
    assert_eq!(json::stringify(f64::NEG_INFINITY), "-Infinity");
}#[test]
fn main_valuetest_searchvaluebypath() {
    let inner = {
        let mut m = BTreeMap::new();
        m.insert("object", json::JsonValue::from("object"));
        json::JsonValue::from(m)
    };
    let prop1 = json::JsonValue::from(vec![json::JsonValue::from(0), json::JsonValue::from(1)]);
    let mut root_map = BTreeMap::new();
    root_map.insert("property1", prop1);
    root_map.insert("property2", inner);
    let root = json::JsonValue::from(root_map);
    let outcome = root.dump();
    let expected = "{\"property1\":[0,1],\"property2\":{\"object\":\"object\"}}\n";
    assert_eq!(outcome, expected);
}#[test]
fn main_valuetest_strings() {
    let empty = json::JsonValue::from("");
    let s = json::JsonValue::from("a");
    let s1 = json::JsonValue::from("sometext with space");
    assert!(empty.is_string());
    assert!(!empty.is_null());
    assert!(!empty.is_boolean());
    assert!(!empty.is_number());
    assert!(!empty.is_array());
    assert!(!empty.is_object());
    assert_eq!(empty.as_str(), Some(""));
    assert!(s.is_string());
    assert_eq!(s.as_str(), Some("a"));
    assert!(s1.is_string());
    assert_eq!(s1.as_str(), Some("sometext with space"));
    assert!(!s1.is_null());
    assert!(!s1.is_boolean());
    assert!(!s1.is_number());
    assert!(!s1.is_array());
    assert!(!s1.is_object());
}#[test]
#[should_panic]
fn main_valuetest_typechecksthrowexceptions() {
    let mut str_val = JsonValue::from("test");
    let mut arr_val = JsonValue::from(vec![JsonValue::from("dummy")]);
    // remove on non-object (string and array) should panic in source; target does not
    str_val.remove("test");
    arr_val.remove("test");
    // as_str on non-string (array) should panic in source; target returns None
    arr_val.as_str();
}#[test]
fn main_valuetest_widestring() {
    let uni = "\u{5f0f}\u{ff0c}\u{8fdb}"; // 式，进
    let mut map = BTreeMap::new();
    map.insert("abc", json::JsonValue::from(uni));
    let root = json::JsonValue::from(map);
    let styled = root.pretty(0);
    assert!(styled.contains(uni));
}
