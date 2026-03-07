"""Minimal local pydantic-compatible shim for offline test execution."""

from __future__ import annotations

from dataclasses import MISSING


class _FieldSpec:
    def __init__(self, default=..., default_factory=None, **_: object) -> None:
        self.default = default
        self.default_factory = default_factory


def Field(default=..., default_factory=None, **kwargs: object):
    return _FieldSpec(default=default, default_factory=default_factory, **kwargs)


class BaseModel:
    def __init__(self, **kwargs: object) -> None:
        annotations = getattr(self.__class__, "__annotations__", {})
        for key in annotations:
            if key in kwargs:
                value = kwargs[key]
            else:
                class_value = getattr(self.__class__, key, MISSING)
                if isinstance(class_value, _FieldSpec):
                    if class_value.default_factory is not None:
                        value = class_value.default_factory()
                    elif class_value.default is ...:
                        raise TypeError(f"Missing required field: {key}")
                    else:
                        value = class_value.default
                elif class_value is MISSING:
                    raise TypeError(f"Missing required field: {key}")
                else:
                    value = class_value
            setattr(self, key, value)

    def model_dump(self) -> dict[str, object]:
        return {k: getattr(self, k) for k in getattr(self.__class__, "__annotations__", {})}

    @classmethod
    def model_json_schema(cls) -> dict[str, object]:
        return {
            "title": cls.__name__,
            "type": "object",
            "properties": {k: {"type": "string"} for k in getattr(cls, "__annotations__", {})},
        }
