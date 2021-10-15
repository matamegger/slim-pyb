from dataclasses import dataclass
from typing import Optional

from cstructparser import Field

MODULE_METHOD_INIT_PATTERN = """self.__c_{0} = getattr(self.dll, "{1}")"""

MODULE_PATTERN = """class {0}:
    def __init__(self, model="{1}"):
        self.model = model
        if platform.system() == "Linux":
            self.dll_path = os.path.abspath(f"{model}.so")
            self.dll = ctypes.cdll.LoadLibrary(self.dll_path)
        elif platform.system() == "Darwin":
            self.dll_path = os.path.abspath("system.dylib")
            self.dll = ctypes.cdll.LoadLibrary(dll_path)
        elif platform.system() == "Windows":
            self.dll_path = os.path.abspath(f"{model}_win64.dll")
            self.dll = ctypes.windll.LoadLibrary(self.dll_path)
        else:
            raise Exception("System Not Supported")
            
        {2}
        """

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

@dataclass
class Argument:
    name: str
    type: str

@dataclass
class ModuleField:
    name: str
    type: str

@dataclass
class ModuleFunction:
    name: str
    returnType: str
    arguments: list[Argument]

@dataclass
class Module:
    name: str
    functions: list[ModuleFunction]
    fields: list[ModuleField]