import enum
import re
from dataclasses import dataclass
from dataclasses import field as field_parameter
from typing import Optional

from lineprovider import LineProvider


@dataclass
class Field:
    name: str
    type: str
    isPointer: bool
    size: int


@dataclass
class Struct:
    name: str
    typedef: str
    fields: list[Field]


@dataclass
class _StructInit:
    name: str
    hasTypedef: bool
    fields: list[Field] = field_parameter(default_factory=lambda: [])
    innerStructsInit = None
    innerStructs: list[Struct] = field_parameter(default_factory=lambda: [])


class _ParserState(enum.Enum):
    FindStructStart = 1
    ReadStructContent = 2
    FindEnd = 3


C_SYMBOL_MATCHER = "[a-zA-Z_$][a-zA-Z_$0-9]*"
C_STRUCT_START_MATCHER = f"[\s\t]*(typedef )?struct ({C_SYMBOL_MATCHER} )?{{"
C_STRUCT_END_MATCHER = f"[\s\t]*}}\s*({C_SYMBOL_MATCHER})?\s*;"
C_STRUCT_FIELD_MATCHER = f"({C_SYMBOL_MATCHER}) (\*)?({C_SYMBOL_MATCHER})(?:\[([0-9]*)\])?;"


class HeaderFileParser:

    @staticmethod
    def __match_struct_start(line):
        return re.match(C_STRUCT_START_MATCHER, line)

    @staticmethod
    def __match_struct_end(line):
        return re.match(C_STRUCT_END_MATCHER, line)

    @staticmethod
    def __search_field(line):
        return re.search(C_STRUCT_FIELD_MATCHER, line)

    @staticmethod
    def __read_struct_init(line) -> Optional[_StructInit]:
        line_match = HeaderFileParser.__match_struct_start(line)
        if not line_match:
            return None

        return _StructInit(line_match.group(2), line_match.group(1) is not None)

    @staticmethod
    def __is_empty_line(line):
        return re.match("^(?!\s*$).+", line) is None

    @staticmethod
    def __read_field(line) -> Optional[Field]:
        line_match = HeaderFileParser.__search_field(line)
        if not line_match:
            return None
        size = int(line_match.group(4)) if line_match.group(4) else 1
        return Field(line_match.group(3), line_match.group(1), line_match.group(2) is not None, size)

    @staticmethod
    def __handle_read_struct_content(line: str, struct_init: _StructInit) -> Optional[Struct]:
        if struct_init.innerStructsInit:
            struct = HeaderFileParser.__handle_read_struct_content(line, struct_init.innerStructsInit)
            if not struct:
                return None
            struct_init.innerStructsInit = None
            struct_init.innerStructs.append(struct)
            assert struct.name is not None
            field = Field(struct.name, struct.name, False, 1)
            struct_init.fields.append(field)
            return None

        inner_struct_init = HeaderFileParser.__read_struct_init(line)
        if inner_struct_init:
            struct_init.innerStructsInit = inner_struct_init
            return None

        field = HeaderFileParser.__read_field(line)
        if field:
            struct_init.fields.append(field)
            return None

        if HeaderFileParser.__is_empty_line(line):
            return None

        struct_end = HeaderFileParser.__match_struct_end(line)
        if struct_end:
            struct_typedef = struct_end.group(1)
            struct_name = struct_init.name if struct_init.hasTypedef or not struct_typedef else struct_typedef

            return Struct(
                struct_name,
                struct_typedef,
                struct_init.fields
            )

        return None

    @staticmethod
    def parse(line_provider: LineProvider):
        line_provider = CommentRemovingLineProvider(line_provider)
        parser_state = _ParserState.FindStructStart
        struct_init: _StructInit
        structs = []

        while True:
            line_provider.next()

            if not line_provider.line():
                break

            if parser_state == _ParserState.FindStructStart:
                struct_init = HeaderFileParser.__read_struct_init(line_provider.line())
                if struct_init:
                    parser_state = _ParserState.ReadStructContent
                    print(f"Found struct with name {struct_init.name}, read content now")
            elif parser_state == _ParserState.ReadStructContent:
                struct = HeaderFileParser.__handle_read_struct_content(line_provider.line(), struct_init)
                if struct:
                    structs.append(struct)
                    parser_state = _ParserState.FindStructStart
            elif parser_state == _ParserState.FindEnd:
                line_match = re.match(C_STRUCT_END_MATCHER, line_provider.line())
                if not line_match:
                    continue
                parser_state = _ParserState.FindStructStart
            else:
                raise Exception("Undefined Parser state entered")

        return structs


class CommentRemovingLineProvider(LineProvider):
    __lineProvider: LineProvider
    __currentLine: str = None
    __multilineCommendStarted: bool = False

    def __init__(self, line_provider):
        self.__lineProvider = line_provider

    def __preprocess_line(self, line):
        if self.__multilineCommendStarted:
            line_match = re.match(".*\*\/(.*)", line)
            if line_match:
                self.__multilineCommendStarted = False
                return line_match.group(1)
            else:
                return None
        else:
            line_match = re.match("(.*)\/\*[^\*]*(\*\/)?(.*)", line)
            if line_match:
                self.__multilineCommendStarted = line_match.group(2) is None
                return line_match.group(1) + line_match.group(3)
            else:
                return line

    def next(self) -> Optional[str]:
        while True:
            line = self.__lineProvider.next()
            if not line:
                break
            line = self.__preprocess_line(line)
            if not line:
                continue
            if len(line) == 0 or line == "\n":
                continue
            break
        self.__currentLine = line
        return self.__currentLine

    def line(self) -> Optional[str]:
        return self.__currentLine

    def destroy(self):
        self.__lineProvider.destroy()
