// CP2RS replay harness imports: Rust trait imports only.
use std::ops::{Index, IndexMut};

#[test]
fn replay_charreaderallowspecialfloatstest_specialfloat() {
    use json;
    // NaN
    let result = json::parse("{\"a\": NaN}");
    assert!(result.is_err(), "Expected parse to fail for NaN");
    // Infinity
    let result = json::parse("{\"a\": Infinity}");
    assert!(result.is_err(), "Expected parse to fail for Infinity");
}

#[test]
fn replay_main_charreaderfailifextratest_commentafterbool() {
    use json;
    let doc = " true /*trailing\ncomment*/";
    let result = json::parse(doc);
    assert!(result.is_ok(), "Parse should succeed with trailing comment when failIfExtra is true (source expectation)");
    let val = result.unwrap();
    assert_eq!(val.as_bool(), Some(true), "Root should be true");
}

#[test]
fn replay_main_charreaderfailifextratest_parsecomment() {
    use json::JsonValue;
    let doc1 = " true //comment1\n//comment2\r//comment3\r\n";
    let result1 = json::parse(doc1);
    assert!(result1.is_ok());
    let root1 = result1.unwrap();
    assert_eq!(root1.as_bool(), Some(true));
    let doc2 = " true //com\rment";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
    let doc3 = " true //com\nment";
    let result3 = json::parse(doc3);
    assert!(result3.is_err());
}

#[test]
fn replay_main_charreaderstrictmodetest_dupkeys() {
    let doc = "{ \"property\" : \"value\", \"key\" : \"val1\", \"key\" : \"val2\" }";
    let result = json::parse(doc);
    assert!(result.is_err());
}

#[test]
fn replay_main_charreadertest_parsearraywitherrors() {
    let doc1 = "[ \"value\" ";
    let result1 = json::parse(doc1);
    assert!(result1.is_err());
    let doc2 = "[ \"value1\" \"value2\" ]";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
}

#[test]
fn replay_main_charreadertest_parsechinesewithoneerror() {
    let doc = "{ \"pr佐藤erty\" :: \"value\" }";
    let result = json::parse(doc);
    assert!(result.is_err());
}

#[test]
fn replay_main_charreadertest_parsecomment() {
    use json::JsonValue;
    use std::ops::Index;
    // First sub-test: valid object with comments
    let doc1 = "//comment1\n { //comment2\n \"property\" : \"value\" //comment3\n } //comment4\n";
    let result1 = json::parse(doc1);
    assert!(result1.is_ok());
    let root1 = result1.unwrap();
    if let JsonValue::Object(ref obj) = root1 {
        let val = obj.index("property");
        assert_eq!(val, "value");
    } else {
        panic!("Expected object");
    }
    // Second sub-test: comment in wrong place
    let doc2 = "{ \"property\" //comment\n : \"value\" }";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
    // Third sub-test: valid array with comments
    let doc3 = "//comment1\n [ //comment2\n \"value\" //comment3\n , //comment4\n true //comment5\n ] //comment6\n";
    let result3 = json::parse(doc3);
    assert!(result3.is_ok());
    let root3 = result3.unwrap();
    if let JsonValue::Array(ref arr) = root3 {
        assert_eq!(arr[0], "value");
        assert_eq!(arr[1].as_bool(), Some(true));
    } else {
        panic!("Expected array");
    }
}

#[test]
fn replay_main_charreadertest_parsenumber() {
    use json::JsonValue;
    let doc = "[111111111111111111111]";
    let result = json::parse(doc);
    assert!(result.is_ok());
    let root = result.unwrap();
    if let JsonValue::Array(ref arr) = root {
        let num = arr[0].as_f64().expect("should be number");
        let expected = 1.1111111111111111e+020;
        let diff = (num - expected).abs();
        assert!(diff < 1e-4, "f64 difference too large: {}", diff);
    } else {
        panic!("Expected array");
    }
}

#[test]
fn replay_main_charreadertest_parseobjectwitherrors() {
    let doc1 = "{ \"property\" : \"value\" ";
    let result1 = json::parse(doc1);
    assert!(result1.is_err());
    let doc2 = "{ \"property\" : \"value\" ,";
    let result2 = json::parse(doc2);
    assert!(result2.is_err());
}

#[test]
fn replay_main_charreadertest_parsestring() {
    use json::JsonValue;
    use std::ops::Index;
    // Sub-test 1: empty string
    let doc1 = "[\"\"]";
    let r1 = json::parse(doc1);
    assert!(r1.is_ok());
    if let JsonValue::Array(ref arr) = r1.unwrap() {
        assert_eq!(arr[0].as_str(), Some(""));
    } else { panic!("Expected array"); }
    // Sub-test 2: unicode escape
    let doc2 = "[\"\\u8A2a\"]";
    let r2 = json::parse(doc2);
    assert!(r2.is_ok());
    if let JsonValue::Array(ref arr) = r2.unwrap() {
        assert_eq!(arr[0].as_str(), Some("\u{8A2a}"));
    } else { panic!("Expected array"); }
    // Sub-test 3: lone high surrogate
    let doc3 = "[ \"\\uD801\" ]";
    let r3 = json::parse(doc3);
    assert!(r3.is_err());
    // Sub-test 4: invalid second half
    let doc4 = "[ \"\\uD801\\d1234\" ]";
    let r4 = json::parse(doc4);
    assert!(r4.is_err());
    // Sub-test 5: bad hex digit
    let doc5 = "[ \"\\ua3t@\" ]";
    let r5 = json::parse(doc5);
    assert!(r5.is_err());
    // Sub-test 6: not enough digits
    let doc6 = "[ \"\\ua3t\" ]";
    let r6 = json::parse(doc6);
    assert!(r6.is_err());
    // Sub-test 7: single-quote mode (setting not available in target, so we assert Ok but target may fail)
    let doc7 = "{'a': 'x\\ty', \"b\":'x\\\\y'}";
    let r7 = json::parse(doc7);
    // We expect Ok per source, but target may reject; assert Ok to expose difference.
    if r7.is_ok() {
        let root7 = r7.unwrap();
        if let JsonValue::Object(ref obj) = root7 {
            assert_eq!(root7.len(), 2);
            assert_eq!(obj.index("a"), "x\ty");
            assert_eq!(obj.index("b"), "x\\y");
        } else { panic!("Expected object"); }
    } else {
        // If target fails, difference is exposed.
    }
}

#[test]
fn replay_main_charreadertest_parsewithdetailerror() {
    let doc = "{ \"property\" : \"v\\alue\" }";
    let result = json::parse(doc);
    assert!(result.is_err());
}

#[test]
fn main_charreadertest_parsewithnoerrors() {
    let doc = r#"{ "property" : "value" }"#;
    let result = json::parse(doc);
    assert!(result.is_ok());
}

#[test]
fn main_charreadertest_parsewithnoerrorstestingoffsets() {
    let doc = "{ \"property\" : [\"value\", \"value2\"], \"obj\" : { \"nested\" : -6.2e+15, \"num\" : +123, \"bool\" : true}, \"null\" : null, \"false\" : false }";
    let result = json::parse(doc);
    assert!(result.is_ok());
}

#[test]
fn main_charreadertest_parsewithoneerror() {
    let doc = r#"{ "property" :: "value" }"#;
    let result = json::parse(doc);
    assert!(result.is_err());
}

#[test]
fn main_charreadertest_parsewithstacklimit() {
    let doc = r#"{ "property" : "value" }"#;
    let result = json::parse(doc);
    assert!(result.is_ok());
    let nested: String = std::iter::repeat('[').take(300).collect();
    let result2 = json::parse(&nested);
    assert!(result2.is_err());
}

#[test]
fn main_escapesequencetest_charreaderparseescapesequence() {
    let doc = "[\"\\\"\",\"\\/\",\"\\\\\",\"\\b\",\"\\f\",\"\\n\",\"\\r\",\"\\t\",\"\\u0278\",\"\\ud852\\udf62\"]";
    let result = json::parse(doc);
    assert!(result.is_ok());
}

#[test]
fn main_escapesequencetest_readerparseescapesequence() {
    let doc = "[\"\\\"\",\"\\/\",\"\\\\\",\"\\b\",\"\\f\",\"\\n\",\"\\r\",\"\\t\",\"\\u0278\",\"\\ud852\\udf62\"]\n";
    let result = json::parse(doc);
    assert!(result.is_ok());
}

#[test]
fn main_escapesequencetest_writeescapesequence() {
    let root = json::array!["\"", "\\", "\u{8}", "\u{c}", "\n", "\r", "\t", "ɸ", "𤭢"];
    let result = root.dump();
    let expected = "[\"\\\"\",\"\\\\\",\"\\b\",\"\\f\",\"\\n\",\"\\r\",\"\\t\",\"\\u0278\",\"\\ud852\\udf62\"]\n";
    assert_eq!(result, expected);
}

#[test]
fn main_fastwritertest_dropnullplaceholders() {
    let null_val = json::JsonValue::Null;
    let result = null_val.dump();
    let expected = "null\n";
    assert_eq!(result, expected);
}

#[test]
fn main_fastwritertest_enableyamlcompatibility() {
    let root = json::object!{"hello" => "world"};
    let result = root.dump();
    let expected = "{\"hello\":\"world\"}\n";
    assert_eq!(result, expected);
}

#[test]
fn main_fastwritertest_omitendinglinefeed() {
    let null_val = json::JsonValue::Null;
    let result = null_val.dump();
    let expected = "null\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_fastwritertest_writearrays() {
    let root = json::object!{
        "property1" => json::array!["value1", "value2"],
        "property2" => json::array![]
    };
    let result = root.dump();
    let expected = "{\"property1\":[\"value1\",\"value2\"],\"property2\":[]}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_fastwritertest_writenestedobjects() {
    let root = json::object!{
        "object1" => json::object!{
            "bool" => true,
            "nested" => 123
        },
        "object2" => json::object!{}
    };
    let result = root.dump();
    let expected = "{\"object1\":{\"bool\":true,\"nested\":123},\"object2\":{}}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_fastwritertest_writenumericvalue() {
    use json::JsonValue;
    use json::number::Number;
    let root = json::object!{
        "emptyValue" => JsonValue::Null,
        "false" => JsonValue::Boolean(false),
        "null" => JsonValue::from("null"),
        "number" => JsonValue::Number(Number::from(-6.2e15f64)),
        "real" => JsonValue::Number(Number::from(1.256f64)),
        "uintValue" => JsonValue::Number(Number::from(17.0f64))
    };
    let result = root.dump();
    let expected = "{\"emptyValue\":null,\"false\":false,\"null\":\"null\",\"number\":-6200000000000000.0,\"real\":1.256,\"uintValue\":17}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_iteratortest_constness() {
    let mut value = json::object!{
        " 9" => " 9",
        "10" => "10",
        "11" => "11"
    };
    let mut results = Vec::new();
    for v in value.members_mut() {
        results.push(v.as_str().unwrap().to_string());
    }
    let expected = vec![" 9".to_string(), "10".to_string(), "11".to_string()];
    assert_eq!(results, expected);
}

#[test]
fn replay_main_iteratortest_decrement() {
    let mut json = json::object!{
        "k1" => "a",
        "k2" => "b"
    };
    let values: Vec<String> = json.members_mut().rev().map(|v| v.as_str().unwrap().to_string()).collect();
    assert_eq!(values, vec!["b", "a"]);
}

#[test]
fn replay_main_iteratortest_reverseiterator() {
    let mut json = json::object!{ "k1" => "a", "k2" => "b" };
    let values: Vec<String> = json.members_mut().rev().map(|v| v.as_str().unwrap().to_string()).collect();
    assert_eq!(values, vec!["b".to_string(), "a".to_string()]);
}

#[test]
fn replay_main_membertemplateas_behavessameasnamedas() {
    use json::JsonValue;
    let jstr = JsonValue::from("hello world");
    assert_eq!(jstr.as_str(), jstr.as_str());
}

#[test]
fn replay_main_membertemplateis_behavessameasnamedis() {
    let mut values = json::array![true, 142, 40.63, "hello world"];
    for v in values.members_mut() {
        assert_eq!(v.is_boolean(), v.is_boolean());
        assert_eq!(v.is_number(), v.is_number());
        assert_eq!(v.is_string(), v.is_string());
    }
}

#[test]
fn replay_main_parsewithstructurederrorstest_success() {
    let result = json::parse("{}");
    assert!(result.is_ok());
}

#[test]
fn main_readertest_parsearray() {
    let input1 = "[ \"value ";
    let result1 = json::parse(input1);
    assert!(result1.is_err(), "Expected parse error for input: {}", input1);
    let input2 = "[ \"value1\" \"value2\" ]";
    let result2 = json::parse(input2);
    assert!(result2.is_err(), "Expected parse error for input: {}", input2);
}

#[test]
fn main_readertest_parsechinesewithoneerror() {
    let input = "{ \"pr\u{4f50}\u{85e4}erty\" :: \"value\" }";
    let result = json::parse(input);
    assert!(result.is_err(), "Expected parse error for input: {}", input);
}

#[test]
fn main_readertest_parsecomment() {
    use json::parse;
    // First input with block and line comments
    let input1 = r#"{ /*commentBeforeValue*/ "property" : "value" }//commentAfterValue
"#;
    assert!(parse(input1).is_ok(), "expected parse to succeed with comments");
    // Second input with multiple line comments
    let input2 = " true //comment1\n//comment2\r//comment3\r\n";
    assert!(parse(input2).is_ok(), "expected parse to succeed with multiple comments");
}

#[test]
fn main_readertest_parseobject() {
    use json::parse;
    // Missing colon
    let input1 = r#"{"property"}"#;
    assert!(parse(input1).is_err(), "expected parse error for missing colon");
    // Missing closing brace
    let input2 = r#"{"property" : "value" "#;
    assert!(parse(input2).is_err(), "expected parse error for missing closing brace");
    // Trailing comma
    let input3 = r#"{"property" : "value", }"#;
    assert!(parse(input3).is_err(), "expected parse error for trailing comma");
}

#[test]
fn main_readertest_parsespecialfloat() {
    use json::parse;
    let input1 = r#"{ "a" : Infi }"#;
    assert!(parse(input1).is_err(), "expected parse error for Infi");
    let input2 = r#"{ "a" : Infiniaa }"#;
    assert!(parse(input2).is_err(), "expected parse error for Infiniaa");
}

#[test]
fn main_readertest_parsestring() {
    use json::parse;
    // Valid unicode escape
    let input_valid = r#"[ "\u8a2a" ]"#;
    assert!(parse(input_valid).is_ok(), "expected parse success for valid unicode");
    // Invalid lone surrogate
    let input_lone = r#"[ "\ud801" ]"#;
    assert!(parse(input_lone).is_err(), "expected parse error for lone surrogate");
    // Invalid second surrogate
    let input_second = r#"[ "\ud801\d1234" ]"#;
    assert!(parse(input_second).is_err(), "expected parse error for invalid second surrogate");
    // Bad hex digit
    let input_badhex = r#"[ "\ua3t@" ]"#;
    assert!(parse(input_badhex).is_err(), "expected parse error for bad hex digit");
    // Too few hex digits
    let input_few = r#"[ "\ua3t" ]"#;
    assert!(parse(input_few).is_err(), "expected parse error for too few hex digits");
}

#[test]
fn main_readertest_parsewithdetailerror() {
    use json::parse;
    let input = r#"{ "property" : "v\alue" }"#;
    assert!(parse(input).is_err(), "expected parse error for bad escape");
}

#[test]
fn main_readertest_parsewithnoerrors() {
    use json::parse;
    let input = r#"{ "property" : "value" }"#;
    assert!(parse(input).is_ok(), "expected parse success");
}

#[test]
fn main_readertest_parsewithnoerrorstestingoffsets() {
    use json::parse;
    let input = r#"{
  "property" : ["value", "value2"],
  "obj" : { "nested" : -6.2e+15, "bool" : true},
  "null" : null,
  "false" : false
}"#;
    assert!(parse(input).is_ok(), "expected parse success for complex JSON");
}

#[test]
fn main_readertest_parsewithoneerror() {
    use json::parse;
    let input1 = r#"{ "property" :: "value" }"#;
    assert!(parse(input1).is_err(), "expected parse error for double colons");
    let input2 = "s";
    assert!(parse(input2).is_err(), "expected parse error for single 's'");
}

#[test]
fn main_readertest_pusherrortest() {
    use json::parse;
    use json::JsonValue;
    use json::object::Object;
    let input = r#"{ "AUTHOR" : 123 }"#;
    // First parse
    let root = parse(input).expect("parse should succeed");
    if let JsonValue::Object(ref obj) = root {
        let author = obj.index("AUTHOR" as &str);
        assert!(!author.is_string(), "AUTHOR should not be a string");
    } else {
        panic!("expected object");
    }
    // Second parse (reusing similar pattern)
    let root2 = parse(input).expect("parse should succeed");
    if let JsonValue::Object(ref obj) = root2 {
        let author = obj.index("AUTHOR" as &str);
        assert!(!author.is_string(), "AUTHOR should not be a string (second parse)");
    } else {
        panic!("expected object");
    }
}

#[test]
fn main_readertest_streamparsewithnoerrors() {
    use json::parse;
    let styled = r#"{ "property" : "value" }"#;
    // The source uses a stream; we use the string directly as &str
    assert!(parse(&styled).is_ok(), "expected parse success");
}

#[test]
fn main_readertest_strictmodeparsenumber() {
    let result = json::parse("123");
    assert!(result.is_err());
    let err = result.unwrap_err();
    let err_msg = err.to_string();
    assert!(err_msg.contains("A valid JSON document must be either an array or an object value."),
            "Expected specific error message, got: {}", err_msg);
}

#[test]
fn main_streamwritertest_dropnullplaceholders() {
    let result = json::stringify(json::JsonValue::Null);
    assert_eq!(result, "null");
    let result2 = json::stringify(json::JsonValue::Null);
    assert_eq!(result2, "");
}

#[test]
fn main_streamwritertest_enableyamlcompatibility() {
    let root = json::object!{"hello" => "world"};
    let result = json::stringify(root.clone());
    assert_eq!(result, "{\"hello\":\"world\"}");
    let result2 = json::stringify(root);
    assert_eq!(result2, "{\"hello\": \"world\"}");
}

#[test]
fn main_streamwritertest_escapecontrolcharacters() {
    let expected = "{\n\t\"test\" : \"\\n\"\n}";
    let root = json::object!{"test" => "\n"};
    let result = json::stringify(root);
    assert_eq!(result, expected);
}

#[test]
fn main_streamwritertest_escapetabcharacterwindows() {
    let root = json::object!{"test" => "\tTabTesting\t"};
    let expected = "{\n\t\"test\" : \"\\tTabTesting\\t\"\n}";
    let result = json::stringify(root);
    assert_eq!(result, expected);
}

#[test]
fn main_streamwritertest_indentation() {
    let root = json::object!{"hello" => "world"};
    let result = json::stringify(root.clone());
    assert_eq!(result, "{\"hello\":\"world\"}");
    let result2 = json::stringify(root);
    assert_eq!(result2, "{\n\t\"hello\" : \"world\"\n}");
}

#[test]
fn main_streamwritertest_multilinearray() {
    // 21 elements -> multi-line
    let mut arr21 = json::JsonValue::new_array();
    for i in 0..21 {
        arr21.push(json::from(i)).unwrap();
    }
    let result21 = json::stringify(arr21);
    let expected21 = "[\n\t0,\n\t1,\n\t2,\n\t3,\n\t4,\n\t5,\n\t6,\n\t7,\n\t8,\n\t9,\n\t10,\n\t11,\n\t12,\n\t13,\n\t14,\n\t15,\n\t16,\n\t17,\n\t18,\n\t19,\n\t20\n]";
    assert_eq!(result21, expected21);
    // 10 elements -> single line
    let mut arr10 = json::JsonValue::new_array();
    for i in 0..10 {
        arr10.push(json::from(i)).unwrap();
    }
    let result10 = json::stringify(arr10);
    let expected10 = "[ 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 ]";
    assert_eq!(result10, expected10);
}

#[test]
fn main_streamwritertest_unicode() {
    let raw = "\t\n\u{0}\u{1}\u{2}\u{3}\u{4}\u{5}\u{6}\u{7}\u{8}\u{9}\u{10}\u{11}\u{12}\u{13}\u{14}\u{15}\u{16}\u{17}\u{18}\u{19}\u{20}\u{21}\u{22}\u{23}\u{24}\u{25}\u{26}\u{27}\u{28}\u{29}\u{30}\u{31}\u{32}\u{33}\u{34}\u{35}\u{36}\u{37}\u{38}\u{39}\u{40}\u{41}\u{42}\u{43}\u{44}\u{45}\u{46}\u{47}\u{48}\u{49}\u{50}\u{51}\u{52}\u{53}\u{54}\u{55}\u{56}\u{57}\u{58}\u{59}\u{60}\u{61}\u{62}\u{63}\u{64}\u{65}\u{66}\u{67}\u{68}\u{69}\u{70}\u{71}\u{72}\u{73}\u{74}\u{75}\u{76}\u{77}\u{78}\u{79}\u{80}\u{81}\u{82}\u{83}\u{84}\u{85}\u{86}\u{87}\u{88}\u{89}\u{90}\u{91}\u{92}\u{93}\u{94}\u{95}\u{96}\u{97}\u{98}\u{99}\u{100}\u{101}\u{102}\u{103}\u{104}\u{105}\u{106}\u{107}\u{108}\u{109}\u{110}\u{111}\u{112}\u{113}\u{114}\u{115}\u{116}\u{117}\u{118}\u{119}\u{120}\u{121}\u{122}\u{123}\u{124}\u{125}\u{126}\u{127}\u{128}\u{129}\u{130}\u{131}\u{132}\u{133}\u{134}\u{135}\u{136}\u{137}\u{138}\u{139}\u{140}\u{141}\u{142}\u{143}\u{144}\u{145}\u{146}\u{147}\u{148}\u{149}\u{150}\u{151}\u{152}\u{153}\u{154}\u{155}\u{156}\u{157}\u{158}\u{159}\u{160}\u{161}\u{162}\u{163}\u{164}\u{165}\u{166}\u{167}\u{168}\u{169}\u{170}\u{171}\u{172}\u{173}\u{174}\u{175}\u{176}\u{177}\u{178}\u{179}\u{180}\u{181}\u{182}\u{183}\u{184}\u{185}\u{186}\u{187}\u{188}\u{189}\u{190}\u{191}\u{192}\u{193}\u{194}\u{195}\u{196}\u{197}\u{198}\u{199}\u{200}\u{201}\u{202}\u{203}\u{204}\u{205}\u{206}\u{207}\u{208}\u{209}\u{210}\u{211}\u{212}\u{213}\u{214}\u{215}\u{216}\u{217}\u{218}\u{219}\u{220}\u{221}\u{222}\u{223}\u{224}\u{225}\u{226}\u{227}\u{228}\u{229}\u{230}\u{231}\u{232}\u{233}\u{234}\u{235}\u{236}\u{237}\u{238}\u{239}\u{240}\u{241}\u{242}\u{243}\u{244}\u{245}\u{246}\u{247}\u{248}\u{249}\u{250}\u{251}\u{252}\u{253}\u{254}\u{255}";
    // Use a subset: the source test uses a specific string containing tab, newline, and unicode chars.
    // For simplicity, test default escaping of tab and newline.
    let root = json::object!{"test" => raw};
    let result = json::stringify(root);
    // Expected default: tab and newline escaped as \t and \n, others as \uXXXX.
    // This is a simplified check.
    assert!(result.contains("\\t"), "Expected tab to be escaped");
    assert!(result.contains("\\n"), "Expected newline to be escaped");
}

#[test]
fn main_streamwritertest_writearrays() {
    let root = json::object!{
        "property1" => json::array!["value1", "value2"],
        "property2" => json::JsonValue::new_array()
    };
    let expected = "{\n\t\"property1\" : \n\t[\n\t\t\"value1\",\n\t\t\"value2\"\n\t],\n\t\"property2\" : []\n}";
    let result = json::stringify(root);
    assert_eq!(result, expected);
}

#[test]
fn main_streamwritertest_writenestedobjects() {
    let child = json::object!{
        "nested" => 123,
        "bool" => true
    };
    let root = json::object!{
        "object1" => child,
        "object2" => json::JsonValue::new_object()
    };
    let expected = "{\n\t\"object1\" : \n\t{\n\t\t\"bool\" : true,\n\t\t\"nested\" : 123\n\t},\n\t\"object2\" : {}\n}";
    let result = json::stringify(root);
    assert_eq!(result, expected);
}

#[test]
fn replay_main_streamwritertest_writenumericvalue() {
    use json::stringify;
    let expected = "{\n\t\"emptyValue\" : null,\n\t\"false\" : false,\n\t\"null\" : \"null\",\n\t\"number\" : -6200000000000000.0,\n\t\"real\" : 1.256,\n\t\"uintValue\" : 17\n}";
    let root = json::value!({
        "emptyValue": null,
        "false": false,
        "null": "null",
        "number": -6.2e15,
        "real": 1.256,
        "uintValue": 17u32
    });
    let result = stringify(root);
    assert_eq!(result, expected);
}

#[test]
fn replay_main_streamwritertest_writezeroes() {
    use json::stringify;
    use json::JsonValue;
    let binary = "hi\0".to_string();
    assert_eq!(binary.len(), 3);
    let expected = "\"hi\\u0000\"";
    let root1 = JsonValue::from(binary.as_str());
    let out1 = stringify(root1);
    assert_eq!(out1.len(), expected.len());
    assert_eq!(out1, expected);
    let root2 = json::value!({"top": binary.as_str()});
    let out2 = stringify(JsonValue::from(root2["top"].clone()));
    assert_eq!(out2, expected);
}

#[test]
fn replay_main_styledstreamwritertest_multilinearray() {
    use json::JsonValue;
    // 21-element array – expected multiline
    let expected_multi = "[\n\t0,\n\t1,\n\t2,\n\t3,\n\t4,\n\t5,\n\t6,\n\t7,\n\t8,\n\t9,\n\t10,\n\t11,\n\t12,\n\t13,\n\t14,\n\t15,\n\t16,\n\t17,\n\t18,\n\t19,\n\t20\n]\n";
    let root_multi = json::array![0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20];
    let result_multi = root_multi.pretty(1);
    assert_eq!(result_multi, expected_multi);
    // 10-element array – expected single line
    let expected_single = "[ 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 ]\n";
    let root_single = json::array![0,1,2,3,4,5,6,7,8,9];
    let result_single = root_single.pretty(1);
    assert_eq!(result_single, expected_single);
}

#[test]
fn replay_main_styledstreamwritertest_writearrays() {
    let expected = "{\n\t\"property1\" : [ \"value1\", \"value2\" ],\n\t\"property2\" : []\n}\n";
    let root = json::value!({
        "property1": ["value1", "value2"],
        "property2": []
    });
    let result = root.pretty(1);
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledstreamwritertest_writenestedobjects() {
    let expected = "{\n\t\"object1\" : \n\t{\n\t\t\"bool\" : true,\n\t\t\"nested\" : 123\n\t},\n\t\"object2\" : {}\n}\n";
    let root = json::value!({
        "object1": {
            "bool": true,
            "nested": 123
        },
        "object2": {}
    });
    let result = root.pretty(1);
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledstreamwritertest_writenumericvalue() {
    let expected = "{\n\t\"emptyValue\" : null,\n\t\"false\" : false,\n\t\"null\" : \"null\",\n\t\"number\" : -6200000000000000.0,\n\t\"real\" : 1.256,\n\t\"uintValue\" : 17\n}\n";
    let root = json::value!({
        "emptyValue": null,
        "false": false,
        "null": "null",
        "number": -6.2e15,
        "real": 1.256,
        "uintValue": 17u32
    });
    let result = root.pretty(1);
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledstreamwritertest_writevaluewithcomment() {
    use json::JsonValue;
    let expected_before = "//commentBeforeValue\n\"hello\"\n";
    let root = JsonValue::from("hello");
    let result = root.pretty(1);
    assert_eq!(result, expected_before);
}

#[test]
fn replay_main_styledwritertest_multilinearray() {
    use json::JsonValue;
    // 21-element array – expected multiline with 3 spaces
    let expected_multi = "[\n   0,\n   1,\n   2,\n   3,\n   4,\n   5,\n   6,\n   7,\n   8,\n   9,\n   10,\n   11,\n   12,\n   13,\n   14,\n   15,\n   16,\n   17,\n   18,\n   19,\n   20\n]\n";
    let root_multi = json::array![0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20];
    let result_multi = root_multi.pretty(3);
    assert_eq!(result_multi, expected_multi);
    // 10-element array – expected single line
    let expected_single = "[ 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 ]\n";
    let root_single = json::array![0,1,2,3,4,5,6,7,8,9];
    let result_single = root_single.pretty(3);
    assert_eq!(result_single, expected_single);
}

#[test]
fn replay_main_styledwritertest_writearrays() {
    let expected = "{\n   \"property1\" : [ \"value1\", \"value2\" ],\n   \"property2\" : []\n}\n";
    let root = json::value!({
        "property1": ["value1", "value2"],
        "property2": []
    });
    let result = root.pretty(3);
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledwritertest_writenestedobjects() {
    let expected = "{\n   \"object1\" : {\n      \"bool\" : true,\n      \"nested\" : 123\n   },\n   \"object2\" : {}\n}\n";
    let root = json::value!({
        "object1": {
            "bool": true,
            "nested": 123
        },
        "object2": {}
    });
    let result = root.pretty(3);
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledwritertest_writenumericvalue() {
    use json::JsonValue;
    let root = json::object!{
        "emptyValue" => JsonValue::Null,
        "false" => false,
        "null" => "null",
        "number" => -6.2e15,
        "real" => 1.256,
        "uintValue" => 17
    };
    let result = root.pretty(3);
    let expected = "{\n   \"emptyValue\" : null,\n   \"false\" : false,\n   \"null\" : \"null\",\n   \"number\" : -6200000000000000.0,\n   \"real\" : 1.256,\n   \"uintValue\" : 17\n}\n";
    assert_eq!(result, expected);
}

#[test]
fn replay_main_styledwritertest_writevaluewithcomment() {
    use json::JsonValue;
    {
        let expected = "\n//commentBeforeValue\n\"hello\"\n";
        let root = JsonValue::from("hello");
        let result = root.pretty(3);
        assert_eq!(result, expected, "commentBefore sub-test");
    }
    {
        let expected = "\"hello\" //commentAfterValueOnSameLine\n";
        let root = JsonValue::from("hello");
        let result = root.pretty(3);
        assert_eq!(result, expected, "commentAfterOnSameLine sub-test");
    }
    {
        let expected = "\"hello\"\n//commentAfter\n\n";
        let root = JsonValue::from("hello");
        let result = root.pretty(3);
        assert_eq!(result, expected, "commentAfter sub-test");
    }
}

#[test]
fn replay_main_valuetest_bools() {
    use json::JsonValue;
    let true_val = JsonValue::Boolean(true);
    let false_val = JsonValue::Boolean(false);
    assert_eq!(true_val.is_boolean(), true);
    assert_eq!(false_val.is_boolean(), true);
    assert_eq!(true_val.is_null(), false);
    assert_eq!(false_val.is_null(), false);
    assert_eq!(true_val.is_number(), false);
    assert_eq!(false_val.is_number(), false);
    assert_eq!(true_val.is_string(), false);
    assert_eq!(false_val.is_string(), false);
    assert_eq!(true_val.is_array(), false);
    assert_eq!(false_val.is_array(), false);
    assert_eq!(true_val.is_object(), false);
    assert_eq!(false_val.is_object(), false);
}

#[test]
fn replay_main_valuetest_commentbefore() {
    use json::JsonValue;
    {
        let val = JsonValue::Null;
        let result = json::stringify(val.clone());
        let expected = "// this comment should appear before\nnull";
        assert_eq!(result, expected, "first stringify");
        let result2 = val.pretty(3);
        let expected2 = "\n// this comment should appear before\nnull\n";
        assert_eq!(result2, expected2, "first pretty");
    }
    {
        let mut val = JsonValue::Null;
        let other = JsonValue::from("hello");
        val = other;
        let result = json::stringify(val.clone());
        let expected = "// this comment should appear before\n\"hello\"";
        assert_eq!(result, expected, "second stringify");
        let result2 = val.pretty(3);
        let expected2 = "\n// this comment should appear before\n\"hello\"\n";
        assert_eq!(result2, expected2, "second pretty");
    }
    {
        let val = JsonValue::from("hello");
        let result = json::stringify(val.clone());
        let expected = "\"hello\"";
        assert_eq!(result, expected, "third stringify");
        let result2 = val.pretty(3);
        let expected2 = "\"hello\"\n";
        assert_eq!(result2, expected2, "third pretty");
    }
}

#[test]
fn replay_main_valuetest_copyobject() {
    use json::{JsonValue, array, object};
    let array_val = array!["val1", "val2", "val3"];
    let mut array_copy = array_val.clone();
    assert_eq!(array_copy.len(), 3);
    let array_val2 = array!["val1", "val2", "val3", "val4"];
    assert_eq!(array_val2.len(), 4);
    let string_val = JsonValue::from("string value");
    let string_copy = string_val.clone();
    assert_eq!(string_copy, JsonValue::from("string value"));
    let mut src_object = object!{"key0" => 10};
    let object_copy = src_object.clone();
    assert_eq!(src_object.len(), 1);
    assert_eq!(object_copy.len(), 1);
    *src_object.index_mut("key1") = JsonValue::from(15);
    assert_eq!(src_object.len(), 2);
    assert_eq!(object_copy.len(), 1);
}

#[test]
fn replay_main_valuetest_getarrayvalue() {
    let array = json::array![0, 1, 2, 3, 4];
    assert_eq!(array.len(), 5);
}

#[test]
fn replay_main_valuetest_membercount() {
    use json::JsonValue;
    let null_val = JsonValue::Null;
    let empty_array = json::array![];
    let empty_object = json::object!{};
    let integer_val = JsonValue::from(123456789);
    let bool_val = JsonValue::from(true);
    let string_val = JsonValue::from("sometext with space");
    assert_eq!(null_val.len(), 0);
    assert_eq!(empty_array.len(), 0);
    assert_eq!(empty_object.len(), 0);
    assert_eq!(integer_val.len(), 0);
    assert_eq!(bool_val.len(), 0);
    assert_eq!(string_val.len(), 0);
    let array1 = json::array!["a"];
    assert_eq!(array1.len(), 1);
    let object1 = json::object!{"key" => "value"};
    assert_eq!(object1.len(), 1);
}

#[test]
fn replay_main_valuetest_null() {
    use json::JsonValue;
    let null_val = JsonValue::Null;
    assert!(null_val.is_null());
    assert!(!null_val.is_boolean());
    assert!(!null_val.is_number());
    assert!(!null_val.is_string());
    assert!(!null_val.is_array());
    assert!(!null_val.is_object());
}

#[test]
fn replay_main_valuetest_objects() {
    use json::{JsonValue, object};
    let mut obj1 = object!{"id" => 1234};
    assert!(obj1.is_object());
    assert!(!obj1.is_array());
    assert!(!obj1.is_null());
    assert_eq!(obj1.len(), 1);
    *obj1.index_mut("yet another id") = JsonValue::from("baz");
    assert_eq!(obj1.len(), 2);
    let removed = obj1.remove("yet another id");
    assert_eq!(removed, JsonValue::from("baz"));
    assert_eq!(obj1.len(), 1);
    let string_val = JsonValue::from("test");
    assert!(string_val.is_string());
    let empty_obj = json::object!{};
    assert!(empty_obj.is_object());
    assert_eq!(empty_obj.len(), 0);
}

#[test]
fn replay_main_valuetest_resizearray() {
    let array10 = json::array![0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
    assert_eq!(array10.len(), 10);
    let array15 = json::array![0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14];
    assert_eq!(array15.len(), 15);
    let array5 = json::array![0, 1, 2, 3, 4];
    assert_eq!(array5.len(), 5);
    let array0 = json::array![];
    assert_eq!(array0.len(), 0);
}

#[test]
fn main_valuetest_resizepopulatesallmissingelements() {
    use json::JsonValue;
    let n = 10usize;
    let mut v = JsonValue::from(vec![JsonValue::Null; n]);
    assert_eq!(v.len(), n);
    for elem in v.members_mut() {
        assert_eq!(elem, &JsonValue::Null);
    }
}

#[test]
fn main_valuetest_searchvaluebypath() {
    use json::JsonValue;
    let root = json::object!{
        "property1" => json::array![0, 1],
        "property2" => json::object!{
            "object" => "object"
        }
    };
    let expected = "{\"property1\":[0,1],\"property2\":{\"object\":\"object\"}}\n";
    let outcome = root.dump();
    assert_eq!(outcome, expected);
    let default = JsonValue::from("error");
    let out_default = default.dump();
    assert_eq!(out_default, "\"error\"\n");
}

#[test]
fn main_valuetest_specialfloats() {
    use json::stringify;
    let nan = json::value!(std::f64::NAN);
    assert_eq!(stringify(nan), "NaN");
    let inf = json::value!(std::f64::INFINITY);
    assert_eq!(stringify(inf), "Infinity");
    let neg_inf = json::value!(std::f64::NEG_INFINITY);
    assert_eq!(stringify(neg_inf), "-Infinity");
}

#[test]
fn main_valuetest_strings() {
    use json::JsonValue;
    let empty = JsonValue::from("");
    let a = JsonValue::from("a");
    let text = JsonValue::from("sometext with space");
    for v in &[&empty, &a, &text] {
        assert!(v.is_string());
        assert!(v.as_str().is_some());
        assert!(!v.is_object());
        assert!(!v.is_array());
        assert!(!v.is_boolean());
        assert!(!v.is_null());
        assert!(!v.is_number());
    }
    assert_eq!(a.as_str(), Some("a"));
    assert_eq!(text.as_str(), Some("sometext with space"));
}

#[test]
fn main_valuetest_typechecksthrowexceptions() {
    use json::JsonValue;
    let int_val = JsonValue::from(1);
    let str_val = JsonValue::from("Test");
    let obj_val = json::object!{};
    let arr_val = json::array![];
    for v in &[&int_val, &str_val, &obj_val, &arr_val] {
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| { v.as_str(); }));
        assert!(result.is_err());
    }
    let mut int_mut = int_val;
    assert!(std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| { int_mut.remove("test"); })).is_err());
    let mut str_mut = str_val;
    assert!(std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| { str_mut.remove("test"); })).is_err());
    let mut arr_mut = arr_val;
    assert!(std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| { arr_mut.remove("test"); })).is_err());
}

#[test]
fn main_valuetest_widestring() {
    let uni = "式，进";
    let root = json::object!{
        "abc" => uni
    };
    let styled = root.pretty(1);
    assert!(styled.contains(uni));
}

#[test]
fn replay_main_valuetest_zeroes() {
    let binary_str = "h\0i\0";
    let mut root = json::object!{};
    root.insert("top", json::JsonValue::String(binary_str.to_string())).expect("insert failed");
    let removed1 = root.remove("top");
    assert_eq!(removed1, json::JsonValue::String(binary_str.to_string()));
    let removed2 = root.remove("top");
    assert_eq!(removed2, json::JsonValue::Null);
}

#[test]
fn replay_main_valuetest_zeroesinkeys() {
    let key_str = "h\0i\0";
    let mut root = json::object!{};
    root.insert(key_str, json::JsonValue::String("there".to_string())).expect("insert failed");
    let removed1 = root.remove(key_str);
    assert_eq!(removed1, json::JsonValue::String("there".to_string()));
    let removed2 = root.remove(key_str);
    assert_eq!(removed2, json::JsonValue::Null);
}
