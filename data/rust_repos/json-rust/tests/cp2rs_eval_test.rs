#[macro_use]
extern crate json;

use json::JsonValue;
use json::stringify_pretty;

#[test]
fn stringify_pretty_object() {
    let object = json::object!{
        name: "Urlich",
        age: 50,
        parents: {
            mother: "Helga",
            father: "Brutus"
        },
        cars: [ "Golf", "Mercedes", "Porsche" ]
    };

    let expected = "{\n  \"name\": \"Urlich\",\n  \"age\": 50,\n  \"parents\": {\n    \"mother\": \"Helga\",\n    \"father\": \"Brutus\"\n  },\n  \"cars\": [\n    \"Golf\",\n    \"Mercedes\",\n    \"Porsche\"\n  ]\n}";
    assert_eq!(object.pretty(2), expected);
    assert_eq!(stringify_pretty(object, 2), expected);
}