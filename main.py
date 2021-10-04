import re
from dataclasses import dataclass
import os.path
import sys
from pathlib import Path
from typing import Optional
from os import listdir
from os.path import isfile, join

from cstructparser import HeaderFileParser, Field, Struct
from lineprovider import FileLineProvider
from pybindingwriter import PythonClass

predefined_types = [
    "int8_T",
    "uint8_T",
    "int16_T",
    "uint16_T",
    "int32_T",
    "uint32_T",
    "int64_T",
    "uint64_T",
    "real32_T",
    "real64_T",
    "real_T",
    "time_T",
    "boolean_T",
    "int_T",
    "uint_T",
    "ulong_T",
    "ulonglong_T",
    "char_T",
    "uchar_T",
    "char_T",
    "creal32_T",
    "creal64_T",
    "creal_T",
    "cint8_T",
    "cuint8_T",
    "cint16_T",
    "cuint16_T",
    "cint32_T",
    "cuint32_T",
    "cint64_T",
    "cuint64_T"
]

if __name__ == '__main__':
    main_file_path = os.path.expanduser(sys.argv[1])
    main_file = open(main_file_path, "r")
    parent_dir = Path(main_file_path).parent.absolute()

    parser = HeaderFileParser()

    file_line_provider = FileLineProvider(main_file)
    main_structs = parser.parse(file_line_provider)
    file_line_provider.destroy()

    structs = main_structs.copy()
    known_types = predefined_types.copy()
    for struct in main_structs:
        def add_to_known_types(struct: Struct, know_types: list):
            def add_struct_to_known_types(struct: Struct, known_types: list):
                known_types.append(struct.typedef if struct.typedef else struct.name)

            add_struct_to_known_types(struct, known_types)
            for s in struct.inner_structs:
                add_to_known_types(s, know_types)

        add_to_known_types(struct, known_types)

    needed_types = []
    additional_structs: list[Struct] = []


    def get_unknown_types(struct: Struct, known_types: list[str]):
        types = map(lambda it:
                    re.match("(?:ctypes.POINTER\([a-zA-Z_$][a-zA-Z_$0-9]*\))|([a-zA-Z_$][a-zA-Z_$0-9]*)", it).group(1),
                    struct.fields
                    )
        return list(set(filter(lambda it: it not in known_types, types)))


    for struct in main_structs:
        print(PythonClass(
            struct.typedef if struct.typedef else struct.name,
            None,
            struct.fields
        ))

        for field in struct.fields:
            match = re.match("(?:ctypes.POINTER\([a-zA-Z_$][a-zA-Z_$0-9]*\))|([a-zA-Z_$][a-zA-Z_$0-9]*)", field.type)
            type = match.group(1)
            if type not in known_types and type not in needed_types:
                needed_types.append(type)

    if len(needed_types) == 0:
        print("done")
        exit(0)

    other_headers = [join(parent_dir, f) for f in listdir(parent_dir) if
                     isfile(join(parent_dir, f)) and f.endswith(".h")]
    for path in other_headers:
        file = open(join(parent_dir, path), "r")
        file_line_provider = FileLineProvider(file)
        tmp = parser.parse(file_line_provider)
        additional_structs += tmp

    added_struct_to_list = True
    while added_struct_to_list:
        added_struct_to_list = False
        for struct in additional_structs:
            if struct.name in needed_types or struct.typedef in needed_types:
                structs.append(struct)
                added_struct_to_list = True
                unknown_types = get_unknown_types(struct, known_types)
                needed_types = list(set(needed_types + unknown_types))

    for a in needed_types:
        print(a)

    print("done")
