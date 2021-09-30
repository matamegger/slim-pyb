import enum
import re
from dataclasses import dataclass
from dataclasses import field
from typing import IO, Optional

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
    fields: list[Field] = field(default_factory=lambda: [])
    innerStructsInit = None
    innerStructs: list[Struct] = field(default_factory=lambda: [])


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
    def __matchStructStart(line):
        return re.match(C_STRUCT_START_MATCHER, line)

    @staticmethod
    def __matchStructEnd(line):
        return re.match(C_STRUCT_END_MATCHER, line)

    @staticmethod
    def __searchField(line):
        return re.search(C_STRUCT_FIELD_MATCHER, line)

    @staticmethod
    def __readStructInit(line) -> Optional[_StructInit]:
        line_match = HeaderFileParser.__matchStructStart(line)
        if not line_match:
            return None

        return _StructInit(line_match.group(2), line_match.group(1) is not None)

    @staticmethod
    def __isEmptyLine(line):
        return re.match("^(?!\s*$).+", line) is None

    @staticmethod
    def __readField(line) -> Optional[Field]:
        line_match = HeaderFileParser.__searchField(line)
        if not line_match:
            return None
        size = int(line_match.group(4)) if line_match.group(4) else 1
        return Field(line_match.group(3), line_match.group(1), line_match.group(2) is not None, size)

    @staticmethod
    def __handleReadStructContent(line: str, structInit: _StructInit) -> Optional[Struct]:
        if structInit.innerStructsInit:
            struct = HeaderFileParser.__handleReadStructContent(line, structInit.innerStructsInit)
            if not struct:
                return None
            structInit.innerStructsInit = None
            structInit.innerStructs.append(struct)
            assert struct.name is not None
            field = Field(struct.name, struct.name, False, 1)
            structInit.fields.append(field)
            return None

        innerStructInit = HeaderFileParser.__readStructInit(line)
        if innerStructInit:
            structInit.innerStructsInit = innerStructInit
            return None

        field = HeaderFileParser.__readField(line)
        if field:
            structInit.fields.append(field)
            return None

        if HeaderFileParser.__isEmptyLine(line):
            return None

        structEnd = HeaderFileParser.__matchStructEnd(line)
        if structEnd:
            structTypedef = structEnd.group(1)
            structName = structInit.name if structInit.hasTypedef or not structTypedef else structTypedef

            return Struct(
                structName,
                structTypedef,
                structInit.fields
            )

        return None

    def parse(self, lineProvider: LineProvider):
        lineProvider = CommentRemovingLineProvider(lineProvider)
        parser_state = _ParserState.FindStructStart
        struct_init: _StructInit
        structs = []

        while True:
            lineProvider.next()

            if not lineProvider.line():
                break

            if parser_state == _ParserState.FindStructStart:
                struct_init = HeaderFileParser.__readStructInit(lineProvider.line())
                if struct_init:
                    parser_state = _ParserState.ReadStructContent
                    print(f"Found struct with name {struct_init.name}, read content now")
            elif parser_state == _ParserState.ReadStructContent:
                struct = HeaderFileParser.__handleReadStructContent(lineProvider.line(), struct_init)
                if struct:
                    structs.append(struct)
                    parser_state = _ParserState.FindStructStart
            elif parser_state == _ParserState.FindEnd:
                line_match = re.match(C_STRUCT_END_MATCHER, lineProvider.line())
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

    def __init__(self, lineProvider):
        self.__lineProvider = lineProvider

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