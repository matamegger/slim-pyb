from dataclasses import dataclass
from typing import Optional

from cstructparser import Field

PYTHON_BINDER_CLASS_PATTERN = """class {0}(ctypes.Structure):
    {1}
    _fields_ = [
{2}
    ]
"""

PYTHON_BINDER_CLASS_FIELD_PATTERN = "(\"{0}\", {1})"
PYTHON_BINDER_CLASS_FIELD_INDENT = "        "


@dataclass
class PythonClass:
    name: str
    comment: Optional[str]
    fields: list[Field]

    @staticmethod
    def __field_transformation(field: Field) -> str:
        type = field.type
        if field.isPointer:
            type = f"ctypes.POINTER({type})"
        if field.size > 1:
            type = f"({type} * {field.size})"
        return PYTHON_BINDER_CLASS_FIELD_INDENT + PYTHON_BINDER_CLASS_FIELD_PATTERN.format(field.name, type)

    def __str__(self) -> str:
        fields = ",\n".join(map(PythonClass.__field_transformation, self.fields))
        comment = "" if not self.comment else f"\"\"\"{self.comment}\"\"\"\n"

        return PYTHON_BINDER_CLASS_PATTERN.format(self.name, comment, fields)
