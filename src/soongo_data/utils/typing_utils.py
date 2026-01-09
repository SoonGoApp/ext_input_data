from typing import Dict, List, TypeVar, Union

JSONType = Union[
    str,
    int,
    float,
    bool,
    None,
    Dict[str, "JSONType"],  # Nested JSON objects
    List["JSONType"],       # Arrays of JSON-compatible types
]
ExceptionType = TypeVar('ExceptionType', bound=Exception)
