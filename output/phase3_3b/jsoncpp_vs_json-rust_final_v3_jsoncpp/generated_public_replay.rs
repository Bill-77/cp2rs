// CP2RS replay harness imports: Rust trait imports only.
use std::ops::{Index, IndexMut};

#[test]
fn replay_issue178_allowdropnull() {
    let doc = "[null]";
    let result = json::parse(doc);
    assert!(result.is_ok());
}

#[test]
fn replay_allownumerickeys() {
    let doc = "{15:true,-16:true,12.01:true}";
    let result = json::parse(doc);
    assert!(result.is_ok());
    let root = result.unwrap();
    let expected = json::object!{"15" => true, "-16" => true, "12.01" => true};
    assert_eq!(root, expected);
}

#[test]
fn replay_issue182_allowsinglequotes() {
    let doc1 = "{'a':true,\"b\":true}";
    let result1 = json::parse(doc1);
    assert!(result1.is_ok());
    let root1 = result1.unwrap();
    let expected1 = json::object!{"a" => true, "b" => true};
    assert_eq!(root1, expected1);
    let doc2 = "{'a': 'x', \"b\":'y'}";
    let result2 = json::parse(doc2);
    assert!(result2.is_ok());
    let root2 = result2.unwrap();
    let expected2 = json::object!{"a" => "x", "b" => "y"};
    assert_eq!(root2, expected2);
}

#[test]
fn replay_issue209_allowspecialfloats() {
    let doc = "{\"a\":NaN,\"b\":Infinity,\"c\":-Infinity,\"d\":+Infinity}";
    let result = json::parse(doc);
    assert!(result.is_ok());
    let root = result.unwrap();
    assert_eq!(root.len(), 4);
    if let json::JsonValue::Object(ref obj) = root {
        let a = obj["a"].as_f64().unwrap();
        assert!(a.is_nan());
        let b = obj["b"].as_f64().unwrap();
        assert_eq!(b, std::f64::INFINITY);
        let c = obj["c"].as_f64().unwrap();
        assert_eq!(c, std::f64::NEG_INFINITY);
        let d = obj["d"].as_f64().unwrap();
        assert_eq!(d, std::f64::INFINITY);
    } else {
        panic!("not an object");
    }
}

#[test]
fn replay_specialfloat_fail() {
    let doc1 = "{\"a\": NaN}";
    let result1 = json::parse(doc1);
    assert!(result1.is_err());
    let doc2 = "{\"a\": Infinity}";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
}

#[test]
fn replay_issue176_allowzeroes() {
    let doc1 = "{'a':true,\"b\":true}";
    let result1 = json::parse(doc1);
    assert!(result1.is_ok());
    let root1 = result1.unwrap();
    let expected1 = json::object!{"a" => true, "b" => true};
    assert_eq!(root1, expected1);
    let doc2 = "{'a': 'x', \"b\":'y'}";
    let result2 = json::parse(doc2);
    assert!(result2.is_ok());
    let root2 = result2.unwrap();
    let expected2 = json::object!{"a" => "x", "b" => "y"};
    assert_eq!(root2, expected2);
}

#[test]
fn replay_commentafterarray() {
    let doc = "[ \"property\" , \"value\" ] //trailing\n//comment\n";
    let result = json::parse(doc);
    assert!(result.is_ok());
    let root = result.unwrap();
    let expected = json::array!["property", "value"];
    assert_eq!(root, expected);
}

#[test]
fn replay_commentafterbool() {
    let doc = " true /*trailing\ncomment*/";
    let result = json::parse(doc);
    assert!(result.is_ok());
    let root = result.unwrap();
    assert_eq!(root.as_bool(), Some(true));
}

#[test]
fn replay_commentafterobject() {
    let doc = "{ \"property\" : \"value\" } //trailing\n//comment\n";
    let result = json::parse(doc);
    assert!(result.is_ok());
    let root = result.unwrap();
    let expected = json::object!{"property" => "value"};
    assert_eq!(root, expected);
}

#[test]
fn replay_issue107_failextra() {
    let doc = "1:2:3";
    let result = json::parse(doc);
    assert!(result.is_err());
}

#[test]
fn replay_charreader_issue164() {
    use json::{parse, JsonValue};
    let doc = r#" "property" : "value" }"#;
    // failIfExtra=false case: should succeed
    let result = parse(doc);
    assert!(result.is_ok());
    let root = result.unwrap();
    assert_eq!(root.as_str(), Some("property"));
    // failIfExtra=true case: should fail with error
    let result2 = parse(doc);
    assert!(result2.is_err());
    let err = result2.err().unwrap();
    let expected_msg = "* Line 1, Column 13\n  Extra non-whitespace after JSON value.\n";
    assert_eq!(err.to_string(), expected_msg);
}

#[test]
fn replay_charreader_failifextra_parsecomment() {
    use json::{parse, JsonValue};
    // doc1: " true //comment1\n//comment2\r//comment3\r\n"
    let doc1 = " true //comment1\n//comment2\r//comment3\r\n";
    let result = parse(doc1);
    assert!(result.is_ok());
    let root = result.unwrap();
    assert_eq!(root.as_bool(), Some(true));
    // doc2: " true //com\rment"
    let doc2 = " true //com\rment";
    let result2 = parse(doc2);
    assert!(result2.is_err());
    let err = result2.err().unwrap();
    let expected_msg = "* Line 2, Column 1\n  Extra non-whitespace after JSON value.\n";
    assert_eq!(err.to_string(), expected_msg);
}

#[test]
fn replay_charreader_parsechinesewithoneerror() {
    use json::parse;
    let doc = "{ \"pr佐藤erty\" :: \"value\" }";
    let result = parse(doc);
    assert!(result.is_err());
    let err = result.err().unwrap();
    let expected_msg = "* Line 1, Column 19\n  Syntax error: value, object or array expected.\n";
    assert_eq!(err.to_string(), expected_msg);
}

#[test]
fn replay_charreader_parsewithdetailerror() {
    use json::parse;
    let doc = r#"{"property" : "v\alue"}"#;
    let result = parse(doc);
    assert!(result.is_err());
    let err = result.err().unwrap();
    let expected_msg = "* Line 1, Column 16\n  Bad escape sequence in string\nSee Line 1, Column 20 for detail.\n";
    assert_eq!(err.to_string(), expected_msg);
}

#[test]
fn replay_charreader_strictmodetest_dupkeys() {
    let doc = r#"{"property":"value","key":"val1","key":"val2"}"#;
    let result = json::parse(doc);
    assert!(result.is_err(), "Expected parse error due to duplicate key");
}

#[test]
fn replay_charreader_parsearraywitherrors() {
    let doc1 = "[ \"value\" ";
    let result1 = json::parse(doc1);
    assert!(result1.is_err());
    let doc2 = "[ \"value1\" \"value2\" ]";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
}

#[test]
fn replay_charreader_parsecomment() {
    let doc1 = "//comment1\n { //comment2\n \"property\" : \"value\" //comment3\n } //comment4\n";
    let result1 = json::parse(doc1);
    assert!(result1.is_ok());
    let val1 = result1.unwrap();
    if let json::JsonValue::Object(ref obj) = val1 {
        assert_eq!(obj["property"].as_str(), Some("value"));
    } else {
        panic!("Expected object");
    }
    let doc2 = "{ \"property\" //comment\n : \"value\" }";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
}

#[test]
fn replay_charreader_parsenumber() {
    let doc = "[111111111111111111111]";
    let result = json::parse(doc);
    assert!(result.is_ok());
    let val = result.unwrap();
    if let json::JsonValue::Array(ref arr) = val {
        let first = &arr[0];
        assert_eq!(first.as_f64(), Some(1.1111111111111111e+020));
    } else {
        panic!("Expected array");
    }
}

#[test]
fn replay_charreader_parseobjectwitherrors() {
    let doc1 = "{ \"property\" : \"value\" ";
    let result1 = json::parse(doc1);
    assert!(result1.is_err());
    let doc2 = "{ \"property\" : \"value\" ,";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
}

#[test]
fn replay_charreader_parsestring() {
    let doc1 = "[\"\"]";
    let result1 = json::parse(doc1);
    assert!(result1.is_ok());
    let val1 = result1.unwrap();
    if let json::JsonValue::Array(ref arr) = val1 {
        assert_eq!(arr.len(), 1);
        assert_eq!(arr[0].as_str(), Some(""));
    } else {
        panic!("Expected array");
    }
    let doc2 = "[\"\\u8A2a\"]";
    let result2 = json::parse(doc2);
    assert!(result2.is_ok());
    let val2 = result2.unwrap();
    if let json::JsonValue::Array(ref arr) = val2 {
        assert_eq!(arr[0].as_str(), Some("訪"));
    } else {
        panic!("Expected array");
    }
}

#[test]
fn replay_charreader_parsewithnoerrors() {
    use json::parse;
    let doc = r#"{ \"property\" : \"value\" }"#;
    let result = parse(doc);
    assert!(result.is_ok());
}

#[test]
fn replay_charreader_parsewithnoerrorstestingoffsets() {
    use json::parse;
    let doc = concat!(
        "{ \\\"property\\\" : [\\\"value\\\", \\\"value2\\\"], \\\"obj\\\" : ",
        "{ \\\"nested\\\" : -6.2e+15, \\\"num\\\" : +123, \\\"bool\\\" : ",
        "true}, \\\"null\\\" : null, \\\"false\\\" : false }",
    );
    let result = parse(doc);
    assert!(result.is_ok());
}

#[test]
fn replay_charreader_parsewithoneerror() {
    use json::parse;
    let doc = r#"({ \"property\" :: \"value\" })"#;
    let result = parse(doc);
    assert!(result.is_err());
    let err = result.unwrap_err();
    assert_eq!(format!("{}", err), "* Line 1, Column 15\n  Syntax error: value, object or array expected.\n");
}

#[test]
fn replay_charreader_parsewithstacklimit() {
    use json::parse;
    let doc = r#"{ "property" : "value" }"#;
    let result1 = parse(doc);
    assert!(result1.is_ok());
    let root = result1.unwrap();
    let expected = json::object!{ "property" => "value" };
    assert_eq!(root, expected);
    let result2 = std::panic::catch_unwind(|| parse(doc));
    assert!(result2.is_err(), "Expected parse to panic, but it returned Ok");
}

#[test]
fn replay_escapesequence_charreaderparse() {
    use json::parse;
    let doc = concat!(
        "[\"\\\"\",\"\\/\",\"\\\\\",\"\\b\",",
        "\"\\f\",\"\\n\",\"\\r\",\"\\t\",",
        "\"\\u0278\",\"\\ud852\\udf62\"]",
    );
    let result = parse(doc);
    assert!(result.is_ok());
}

#[test]
fn replay_escapesequence_readerparse() {
    use json::parse;
    let doc = concat!(
        "[\"\\\"\",\"\\/\",\"\\\\\",\"\\b\",",
        "\"\\f\",\"\\n\",\"\\r\",\"\\t\",",
        "\"\\u0278\",\"\\ud852\\udf62\"]\n",
    );
    let result = parse(doc);
    assert!(result.is_ok());
}

#[test]
fn replay_escapesequence_write() {
    let root = json::array!["\"", "\\", "\u{8}", "\u{c}", "\n", "\r", "\t", "\u{0278}", "\u{24b62}"];
    let result = root.dump();
    let expected = r##"["\"","\\","\x08","\x0c","\n","\r","\t","ɸ","𤭢"]
"##;
    assert_eq!(result, expected);
}

#[test]
fn replay_fastwriter_dropnullplaceholders() {
    use json::JsonValue;
    let null_val = JsonValue::Null;
    // Source: default writer writes "null\n"
    assert_eq!(null_val.dump(), "null\n");
    // Source calls dropNullPlaceholders, but target has no such method. Expect behavior difference.
    assert_eq!(null_val.dump(), "\n");
}

#[test]
fn replay_fastwriter_enableyamlcompatibility() {
    let root = json::object!{ "hello" => "world" };
    assert_eq!(root.dump(), "{\"hello\":\"world\"}\n");
    assert_eq!(root.dump(), "{\"hello\": \"world\"}\n");
}

#[test]
fn replay_fastwriter_omitendinglinefeed() {
    use json::JsonValue;
    let null_val = JsonValue::Null;
    // Source: default writer appends newline
    assert_eq!(null_val.dump(), "null\n");
    // Source calls omitEndingLineFeed, target has no such method.
    assert_eq!(null_val.dump(), "null");
}

#[test]
fn replay_fastwriter_writearrays() {
    let root = json::object!{
        "property1" => json::array!["value1", "value2"],
        "property2" => json::array![]
    };
    let result = root.dump();
    let expected = "{\"property1\":[\"value1\",\"value2\"],\"property2\":[]}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_fastwriter_writenestedobjects() {
    let child = json::object!{
        "nested" => 123,
        "bool" => true
    };
    let root = json::object!{
        "object1" => child,
        "object2" => json::object!{}
    };
    let result = root.dump();
    let expected = "{\"object1\":{\"bool\":true,\"nested\":123},\"object2\":{}}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_fastwriter_writenumericvalue() {
    let root = json::object!{
        "emptyValue" => json::JsonValue::Null,
        "false" => json::JsonValue::Boolean(false),
        "null" => "null",
        "number" => -6.2e15_f64,
        "real" => 1.256_f64,
        "uintValue" => json::value!(17)
    };
    let result = root.dump();
    let expected = r##"{"emptyValue":null,"false":false,"null":"null","number":-6200000000000000.0,"real":1.256,"uintValue":17}
"##;
    assert_eq!(result, expected);
}

#[test]
fn replay_iteratortest_decrement() {
    let mut json = json::object!{
        "k1" => "a",
        "k2" => "b"
    };
    let mut values = Vec::new();
    for v in json.members_mut().rev() {
        values.push(v.as_str().unwrap().to_string());
    }
    assert_eq!(values, vec!["b", "a"]);
}

#[test]
fn replay_iteratortest_distance() {
    let mut json = json::object!{
        "k1" => "a",
        "k2" => "b"
    };
    let mut i = 0;
    for (dist, _) in json.members_mut().enumerate() {
        assert_eq!(i, dist as isize);
        i += 1;
    }
    // empty object
    let mut empty = json::object!{};
    assert_eq!(0, empty.members_mut().count());
}

#[test]
fn replay_reverseiterator() {
    let mut json = json::object!{ "k1" => "a", "k2" => "b" };
    let rev_values: Vec<String> = json.members_mut().rev().map(|v| v.as_str().unwrap().to_string()).collect();
    assert_eq!(rev_values, vec!["b", "a"]);
}

#[test]
fn replay_membertemplateas_behavessameasnamedas() {
    use json::JsonValue;
    let jstr = JsonValue::from("hello world");
    let s = jstr.as_str().expect("should be string");
    assert_eq!(s, "hello world");
}

#[test]
fn replay_membertemplateis_behavessameasnamedis() {
    use json::JsonValue;
    let values = vec![
        JsonValue::from(true),
        JsonValue::from(142),
        JsonValue::from(40.63),
        JsonValue::from("hello world"),
    ];
    assert!(values[0].is_boolean());
    assert!(values[1].is_number());
    assert!(values[2].is_number());
    assert!(values[3].is_string());
}

#[test]
fn replay_parsewithstructurederrorstest_singleerror() {
    let result = json::parse(r#"{ 1 : 2 }"#);
    assert!(result.is_err());
}

#[test]
fn replay_parsewithstructurederrorstest_success() {
    let result = json::parse("{}");
    assert!(result.is_ok());
    let root = result.unwrap();
    assert_eq!(root.len(), 0);
}

#[test]
fn replay_reader_allownumerickeystest() {
    let result = json::parse("({ 123 : })");
    assert!(result.is_err());
}

#[test]
fn replay_parsearray() {
    let result = json::parse("([ )");
    assert!(result.is_err());
}

#[test]
fn replay_reader_parsechinesewithoneerror() {
    let result = json::parse("({ 佐藤 :: })");
    assert!(result.is_err());
}

#[test]
fn main_readertest_allowdroppednullplaceholders() {
    let root = json::parse("[1,,2]").expect("parse should succeed");
    let expected = json::array![json::value!(1), json::Null, json::value!(2)];
    assert_eq!(root.len(), 3);
    assert_eq!(root, expected);
}

#[test]
fn replay_main_readertest_parsecomment() {
    let input = r#"({ /*commentBeforeValue*/ " : " }//commentAfterValue)"#;
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn replay_main_readertest_parseobject() {
    let input = r#"({"key" "value"})"#;
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn replay_main_readertest_parsespecialfloat() {
    let input = r#"({ "key" : Infi })"#;
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn replay_main_readertest_parsestring() {
    let input = r#"["\uD800"]"#;
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn replay_main_readertest_parsewithdetailerror() {
    let input = r#"({"key":"bad\z"})"#;
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn replay_main_readertest_parsewithnoerrors() {
    let input = r#"({ "key" : })"#;
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn replay_main_readertest_parsewithnoerrorstestingoffsets() {
    let input = r#"({)"#;
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn replay_main_readertest_parsewithoneerror() {
    let input = r#"({ "key" :: "value" })"#;
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn replay_main_readertest_streamparsewithnoerrors() {
    let input = r#"({ "key" : })"#;
    let result = json::parse(input);
    assert!(result.is_err());
}

#[test]
fn main_streamwritertest_dropnullplaceholders() {
    assert_eq!(json::stringify(json::value!(null)), "null");
    assert_eq!(json::stringify(json::value!(null)), "");
}

#[test]
fn main_streamwritertest_enableyamlcompatibility() {
    let root = json::value!({"hello": "world"});
    assert_eq!(json::stringify(root.clone()), "{\"hello\":\"world\"}");
    assert_eq!(json::stringify(root.clone()), "{\"hello\": \"world\"}");
    assert_eq!(json::stringify(root), "{\"hello\":\"world\"}");
}

#[test]
fn main_streamwritertest_escapecontrolcharacters() {
    assert_eq!(json::stringify("\n"), "\"\\n\"");
    assert_eq!(json::stringify("\u{0008}"), "\"\\b\"");
}

#[test]
fn main_streamwritertest_escapetabcharacterwindows() {
    assert_eq!(json::stringify("\tTabTesting\t"), "\"\\tTabTesting\\t\"");
}

#[test]
fn main_streamwritertest_indentation() {
    let root = json::value!({"hello": "world"});
    assert_eq!(json::stringify(root.clone()), "{\"hello\":\"world\"}");
    assert_eq!(json::stringify(root), "{\n\t\"hello\" : \"world\"\n}");
}

#[test]
fn main_streamwritertest_multilinearray() {
    let root = json::value!([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]);
    let expected = "[\n\t0,\n\t1,\n\t2,\n\t3,\n\t4,\n\t5,\n\t6,\n\t7,\n\t8,\n\t9,\n\t10,\n\t11,\n\t12,\n\t13,\n\t14,\n\t15,\n\t16,\n\t17,\n\t18,\n\t19,\n\t20\n]";
    assert_eq!(json::stringify(root), expected);
}

#[test]
fn main_streamwritertest_unicode() {
    // Test that a non-ASCII character is escaped as \u00e9
    assert_eq!(json::stringify("é"), "\"\\u00e9\"");
}

#[test]
fn main_streamwritertest_writearrays() {
    let root = json::value!({"property1": ["value1", "value2"], "property2": []});
    let expected = "{\n\t\"property1\" : \n\t[\n\t\t\"value1\",\n\t\t\"value2\"\n\t],\n\t\"property2\" : []\n}";
    assert_eq!(json::stringify(root), expected);
}

#[test]
fn main_streamwritertest_writenestedobjects() {
    let root = json::value!({"object1": {"nested": 123, "bool": true}, "object2": {}});
    let expected = "{\n\t\"object1\" : \n\t{\n\t\t\"nested\" : 123,\n\t\t\"bool\" : true\n\t},\n\t\"object2\" : {}\n}";
    assert_eq!(json::stringify(root), expected);
}

#[test]
fn main_readertest_strictmodeparsenumber() {
    // Source: ReaderTest.strictModeParseNumber - expects parse failure for bare number '123'
    // Target Rust parse accepts any valid JSON, but we assert error to expose difference.
    assert!(json::parse("123").is_err(), "Expected parse to fail in strict mode, but it succeeded");
}

#[test]
fn replay_main_streamwritertest_writenumericvalue() {
    let root = json::value!({
        "emptyValue": null,
        "false": false,
        "null": "null",
        "number": -6.2e15,
        "real": 1.256,
        "uintValue": 17
    });
    let result = json::stringify(root);
    let expected = "{\n\t\"emptyValue\" : null,\n\t\"false\" : false,\n\t\"null\" : \"null\",\n\t\"number\" : -6200000000000000.0,\n\t\"real\" : 1.256,\n\t\"uintValue\" : 17\n}";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledstreamwritertest_multilinearray() {
    let root21 = json::value!([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]);
    let result21 = root21.pretty(2);
    let expected21 = "[\n   0,\n   1,\n   2,\n   3,\n   4,\n   5,\n   6,\n   7,\n   8,\n   9,\n   10,\n   11,\n   12,\n   13,\n   14,\n   15,\n   16,\n   17,\n   18,\n   19,\n   20\n]";
    assert_eq!(result21, expected21);

    let root10 = json::value!([0,1,2,3,4,5,6,7,8,9]);
    let result10 = root10.pretty(2);
    let expected10 = "[ 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 ]\n";
    assert_eq!(result10, expected10);
}

#[test]
fn replay_main_styledstreamwritertest_writearrays() {
    let root = json::value!({
        "property1": ["value1", "value2"],
        "property2": []
    });
    let result = root.pretty(2);
    let expected = "{\n\t\"property1\" : [ \"value1\", \"value2\" ],\n\t\"property2\" : []\n}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledstreamwritertest_writenestedobjects() {
    let root = json::value!({
        "object1": {
            "bool": true,
            "nested": 123
        },
        "object2": {}
    });
    let result = root.pretty(2);
    let expected = "{\n\t\"object1\" : \n\t{\n\t\t\"bool\" : true,\n\t\t\"nested\" : 123\n\t},\n\t\"object2\" : {}\n}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledstreamwritertest_writenumericvalue() {
    let root = json::value!({
        "emptyValue": null,
        "false": false,
        "null": "null",
        "number": -6.2e15,
        "real": 1.256,
        "uintValue": 17
    });
    let result = root.pretty(2);
    let expected = "{\n\t\"emptyValue\" : null,\n\t\"false\" : false,\n\t\"null\" : \"null\",\n\t\"number\" : -6200000000000000.0,\n\t\"real\" : 1.256,\n\t\"uintValue\" : 17\n}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledwritertest_multilinearray() {
    let root21 = json::value!([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]);
    let result21 = root21.pretty(2);
    let expected21 = "[\n   0,\n   1,\n   2,\n   3,\n   4,\n   5,\n   6,\n   7,\n   8,\n   9,\n   10,\n   11,\n   12,\n   13,\n   14,\n   15,\n   16,\n   17,\n   18,\n   19,\n   20\n]";
    assert_eq!(result21, expected21);

    let root10 = json::value!([0,1,2,3,4,5,6,7,8,9]);
    let result10 = root10.pretty(2);
    let expected10 = "[ 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 ]\n";
    assert_eq!(result10, expected10);
}

#[test]
fn replay_main_styledwritertest_writearrays() {
    let root = json::value!({
        "property1": ["value1", "value2"],
        "property2": []
    });
    let result = root.pretty(2);
    let expected = "{\n   \"property1\" : [ \"value1\", \"value2\" ],\n   \"property2\" : []\n}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledwritertest_writenestedobjects() {
    let root = json::value!({
        "object1": {
            "bool": true,
            "nested": 123
        },
        "object2": {}
    });
    let result = root.pretty(2);
    let expected = "{\n   \"object1\" : {\n      \"bool\" : true,\n      \"nested\" : 123\n   },\n   \"object2\" : {}\n}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledstreamwritertest_writevaluewithcomment() {
    let root = json::JsonValue::from("hello");
    let result = root.pretty(0);
    let expected = "//commentBeforeValue\n\"hello\"\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledwritertest_writevaluewithcomment() {
    let root1 = json::JsonValue::from("hello");
    let result1 = root1.pretty(2);
    let expected1 = "\n//commentBeforeValue\n\"hello\"\n";
    assert_eq!(result1, expected1, "commentBefore scenario");

    let root2 = json::JsonValue::from("hello");
    let result2 = root2.pretty(2);
    let expected2 = "\"hello\" //commentAfterValueOnSameLine\n";
    assert_eq!(result2, expected2, "commentAfterOnSameLine scenario");

    let root3 = json::JsonValue::from("hello");
    let result3 = root3.pretty(2);
    let expected3 = "\"hello\"\n//commentAfter\n\n";
    assert_eq!(result3, expected3, "commentAfter scenario");
}

#[test]
fn replay_main_valuetest_arrayissue252() {
    use json::JsonValue;
    let arr = json::array![
        json::object!{"a" => 0, "b" => 0},
        json::object!{"a" => 1, "b" => 1},
        json::object!{"a" => 2, "b" => 2},
        json::object!{"a" => 3, "b" => 3},
        json::object!{"a" => 4, "b" => 4}
    ];
    assert_eq!(arr.len(), 5);
}

#[test]
fn replay_main_valuetest_bools() {
    let false_ = json::JsonValue::from(false);
    let true_ = json::JsonValue::from(true);
    assert!(!false_.is_null());
    assert!(false_.is_boolean());
    assert!(!false_.is_number());
    assert!(!false_.is_string());
    assert!(!false_.is_array());
    assert!(!false_.is_object());
    assert!(!true_.is_null());
    assert!(true_.is_boolean());
    assert!(!true_.is_number());
    assert!(!true_.is_string());
    assert!(!true_.is_array());
    assert!(!true_.is_object());
}

#[test]
fn replay_main_valuetest_commentbefore() {
    let val = json::JsonValue::Null;
    let expected_write = "// this comment should appear before\nnull";
    let result = json::stringify(val.clone());
    assert_eq!(result, expected_write);
    let expected_pretty = "\n// this comment should appear before\nnull\n";
    let res2 = val.pretty(0);
    assert_eq!(res2, expected_pretty);
}

#[test]
fn replay_main_valuetest_comparenull() {
    use json::{value, JsonValue};
    let null1 = json::JsonValue::Null;
    let null2 = json::value!(null);
    assert_eq!(null1, null2);
    // Also test nullSingleton equivalent: just use null again
    assert_eq!(null1, null1);
    assert_eq!(null2, null2);
}

#[test]
fn replay_main_valuetest_membercount() {
    let null_val = json::JsonValue::Null;
    let empty_array = json::array![];
    let empty_object = json::object!{};
    let array_one = json::array!["a"];
    let object_one = json::object!{"key" => "val"};
    assert_eq!(null_val.len(), 0);
    assert_eq!(empty_array.len(), 0);
    assert_eq!(empty_object.len(), 0);
    assert_eq!(array_one.len(), 1);
    assert_eq!(object_one.len(), 1);
}

#[test]
fn replay_main_valuetest_objects() {
    // empty object
    let empty = json::object!{};
    assert!(empty.is_object());
    assert!(!empty.is_null());
    assert!(!empty.is_boolean());
    assert!(!empty.is_number());
    assert!(!empty.is_string());
    assert!(!empty.is_array());
    assert_eq!(empty.len(), 0);
    // object with one key
    let mut obj = json::object!{"key1" => json::object!{"subkey" => "val"}};
    assert_eq!(obj.len(), 1);
    assert!(obj.is_object());
    // test remove
    let removed = obj.remove("key1");
    assert_eq!(obj.len(), 0);
    // test demand (index_mut)
    *obj.index_mut("newkey") = json::JsonValue::from("newval");
    assert_eq!(obj.len(), 1);
    assert_eq!(obj.index_mut("newkey"), &json::JsonValue::from("newval"));
}

#[test]
fn replay_main_valuetest_precision() {
    let v = 100.0 / 3.0;
    let result = json::stringify(v);
    assert_eq!(result, "33.333");
    let v2 = 0.25000000;
    let result2 = json::stringify(v2);
    assert_eq!(result2, "0.25");
    let v3 = 0.2563456;
    let result3 = json::stringify(v3);
    assert_eq!(result3, "0.25635");
    let result4 = json::stringify(v3);
    assert_eq!(result4, "0.3");
}

#[test]
fn replay_main_valuetest_resizearray() {
    let arr = json::JsonValue::from(vec![0; 10]);
    assert_eq!(arr.len(), 10);
    let arr2 = json::JsonValue::from(vec![0; 15]);
    assert_eq!(arr2.len(), 15);
    let arr3 = json::JsonValue::from(vec![0; 5]);
    assert_eq!(arr3.len(), 5);
    let arr4 = json::JsonValue::from(Vec::<i32>::new());
    assert_eq!(arr4.len(), 0);
}

#[test]
fn replay_main_valuetest_resizepopulatesallmissingelements() {
    let mut v = json::JsonValue::from(vec![json::JsonValue::Null; 10]);
    assert_eq!(v.len(), 10);
    for e in v.members_mut() {
        assert_eq!(*e, json::JsonValue::Null);
    }
}

#[test]
fn replay_main_valuetest_searchvaluebypath() {
    let root = json::object! {
        "property1" => json::array![0, 1],
        "property2" => json::object! {"object" => "object"}
    };
    let outcome = root.dump();
    let expected = "{\"property1\":[0,1],\"property2\":{\"object\":\"object\"}}\n";
    assert_eq!(outcome, expected);
}

#[test]
fn replay_main_valuetest_specialfloats() {
    assert_eq!(json::stringify(f64::NAN), "NaN");
    assert_eq!(json::stringify(f64::INFINITY), "Infinity");
    assert_eq!(json::stringify(f64::NEG_INFINITY), "-Infinity");
}

#[test]
fn replay_main_valuetest_strings() {
    let empty_str = json::JsonValue::from("");
    assert!(empty_str.is_string());
    assert!(!empty_str.is_null());
    assert!(!empty_str.is_boolean());
    assert!(!empty_str.is_number());
    assert!(!empty_str.is_array());
    assert!(!empty_str.is_object());
    assert_eq!(empty_str.as_str(), Some(""));

    let non_empty = json::JsonValue::from("a");
    assert!(non_empty.is_string());
    assert_eq!(non_empty.as_str(), Some("a"));

    let num = json::JsonValue::from(123);
    assert!(num.is_number());
    assert!(!num.is_string());
}

#[test]
fn replay_main_valuetest_typechecksthrowexceptions() {
    use std::panic::catch_unwind;
    let int_val = json::JsonValue::from(1);
    let str_val = json::JsonValue::from("test");
    let arr_val = json::JsonValue::from(vec![1,2,3]);
    let obj_val = json::JsonValue::from(std::collections::BTreeMap::<&str, json::JsonValue>::new());

    // intVal["test"]
    assert!(catch_unwind(|| { let _ = &int_val["test"]; }).is_err());
    // strVal["test"]
    assert!(catch_unwind(|| { let _ = &str_val["test"]; }).is_err());
    // arrVal["test"]
    assert!(catch_unwind(|| { let _ = &arr_val["test"]; }).is_err());

    // removeMember on non-object should not panic (target returns Null)
    let mut int_mut = json::JsonValue::from(1);
    let res = catch_unwind(move || { int_mut.remove("test"); });
    assert!(res.is_ok());
    let mut str_mut = json::JsonValue::from("test");
    let res = catch_unwind(move || { str_mut.remove("test"); });
    assert!(res.is_ok());
    let mut arr_mut = json::JsonValue::from(vec![1]);
    let res = catch_unwind(move || { arr_mut.remove("test"); });
    assert!(res.is_ok());

    // asCString on non-string returns None
    assert_eq!(int_val.as_str(), None);
}

#[test]
fn replay_main_valuetest_widestring() {
    let uni = "式，进";
    let mut root = json::object! {};
    root["abc"] = json::JsonValue::from(uni);
    let styled = root.pretty(0);
    // verify that pretty output contains the unicode
    assert!(styled.contains(uni));
    // verify as_str works
    assert_eq!(root["abc"].as_str(), Some(uni));
}

#[test]
fn replay_main_valuetest_zeroes() {
    let binary = "h\0i";
    let mut root = json::object! {};
    root["top"] = json::JsonValue::from(binary);
    assert_eq!(root["top"].as_str(), Some(binary));
    let removed = root.remove("top");
    assert_eq!(removed.as_str(), Some(binary));
    let removed2 = root.remove("top");
    assert_eq!(removed2, json::JsonValue::Null);
}

#[test]
fn replay_main_valuetest_zeroesinkeys() {
    let binary = "h\0i";
    let mut root = json::object! {};
    root[binary] = json::JsonValue::from("there");
    assert_eq!(root[binary].as_str(), Some("there"));
    let removed = root.remove(binary);
    assert_eq!(removed.as_str(), Some("there"));
    let removed2 = root.remove(binary);
    assert_eq!(removed2, json::JsonValue::Null);
}
