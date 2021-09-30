import os.path
import sys
from cstructparser import HeaderFileParser
from lineprovider import FileLineProvider

if __name__ == '__main__':
    main_file_path = os.path.expanduser(sys.argv[1])
    main_file = open(main_file_path, "r")

    parser = HeaderFileParser()

    structs = parser.parse(FileLineProvider(main_file))

    for struct in structs:
        print(struct)
