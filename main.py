import enum
import os.path
import re
import sys
from dataclasses import dataclass


@dataclass
class Field:
    name: str
    type: str
    isPointer: bool
    size: int


@dataclass
class Struct:
    name: str
    fields: list[Field]


class ParserState(enum.Enum):
    FindStructStart = 1
    ReadFields = 2
    FindEnd = 3


if __name__ == '__main__':
    mainFilePath = os.path.expanduser(sys.argv[1])
    mainFile = open(mainFilePath, "r")

    parserState = ParserState.FindStructStart

    codeCommentStarted = False

    reprocessLine = False
    structs = []

    isTypedef = None
    structName = None
    fields = []


    while True:
        if not reprocessLine:
            line = mainFile.readline()
        reprocessLine = False

        if not line:
            break

        if codeCommentStarted:
            lineMatch = re.match(".*\*\/(.*)", line)
            if lineMatch:
                line = lineMatch.group(1)
                codeCommentStarted = False
                if len(line) == 0:
                    continue
            else:
                continue
        else:
            lineMatch = re.match("(.*)\/\*[^\*]*(\*\/)?(.*)", line)
            if lineMatch:
                oldLine = line
                print(f"Old line {line}")
                line = lineMatch.group(1) + lineMatch.group(3)
                codeCommentStarted = lineMatch.group(2) is None
                if len(line) == 0:
                    print(f"Removed line {oldLine}")
                    continue
                print(lineMatch.groups())
                print(f"Code comment started {''if codeCommentStarted else 'and ended'}, go on with {line}")

        print(f"process {bytes(line,'utf-8')}")

        if parserState == ParserState.FindStructStart:
            lineMatch = re.match("(typedef )?struct ([a-zA-Z_$][a-zA-Z_$0-9]* )?\{", line)
            if not lineMatch:
                continue

            isTypedef = lineMatch.group(1)
            structName = lineMatch.group(2)
            fields.clear()
            parserState = ParserState.ReadFields
            print(f"Found struct with name {structName}, read fields now")

        elif parserState == ParserState.ReadFields:
            lineMatch = re.search("([a-zA-Z_$][a-zA-Z_$0-9]*) (\*)?([a-zA-Z_$][a-zA-Z_$0-9]*)(?:\[([0-9]*)\])?;", line)
            if not lineMatch and re.match("^(?!\s*$).+", line):
                parserState = ParserState.FindEnd
                reprocessLine = True
                print(bytes(line, 'utf-8'))
                print("reprocess line and find end")
            elif lineMatch:
                size = int(lineMatch.group(4)) if lineMatch.group(4) else 1
                field = Field(lineMatch.group(3), lineMatch.group(1), lineMatch.group(2) is not None, size )
                print(f"Found Field")
                print(field)
                fields.append(field)
            else:
                continue
        elif parserState == ParserState.FindEnd:
            lineMatch = re.match("} \s*([a-zA-Z_$][a-zA-Z_$0-9]*)\s*;", line)
            if not lineMatch:
                continue
            if lineMatch.group(1) is not None:
                structName = lineMatch.group(1)

            struct = Struct(structName, fields.copy())
            structs.append(struct)
            print(f"Found struct {struct}")
            structName = None
            isTypedef = None
            fields.clear()
            parserState = ParserState.FindStructStart
        else:
            raise Exception("Undefined Parser state entered")

    for struct in structs:
        print(struct)