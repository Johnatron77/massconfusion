from typing import Optional, Callable

from inflection import underscore


def _mappings_key_convertor(key_map: dict):
    def key_convertor(n: str) -> str:
        return underscore(key_map.get(n, n))
    return key_convertor


def map_data_to_class(
    cls,
    data: dict,
    key_map: Optional[dict] = None,
    value_converter: Callable = lambda k, v: v
) -> dict:
    key_convertor = underscore

    if key_map is not None:
        key_convertor = _mappings_key_convertor(key_map)

    return map_dict_to_class_attributes(cls, data, key_convertor, value_converter)


def map_dict_to_class_attributes(
    cls,
    data: dict,
    key_converter: Callable = lambda n: n,
    value_converter: Callable = lambda k, v: v
) -> dict:
    cls_attrs = dir(cls)
    return {key: value_converter(key,v) for k, v in data.items() if (key:=key_converter(k)) in cls_attrs}
