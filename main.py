import os.path
import sys
from HeaderFileParser import HeaderFileParser, CommentRemovingLineProvider, FileLineProvider

if __name__ == '__main__':
    mainFilePath = os.path.expanduser(sys.argv[1])
    mainFile = open(mainFilePath, "r")

    parser = HeaderFileParser()

    structs = parser.parse(CommentRemovingLineProvider(FileLineProvider(mainFile)))

    for struct in structs:
        print(struct)
