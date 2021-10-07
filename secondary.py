import enum
import os.path
import re
import sys
from dataclasses import dataclass
from pycparser import c_parser, c_ast, parse_file
from pycparser.c_ast import FileAST, FuncDecl
from pycparser.plyparser import Coord


input_file = os.path.expanduser(sys.argv[1])
ast = parse_file(input_file,
                 use_cpp=True,
                 cpp_path="clang",
                 cpp_args=['-E', '-Ifake_libc_include', '-D_Atomic(x)=x', '-D_Bool=int', '-D__extension__=',
                           '-U__STDC__'])


print(type(ast.ext[0].coord))
definitions = filter(lambda it: "fake_libc_include" not in it.coord.file, ast.ext)
#definitions = filter(lambda it: input_file == it.coord.file, definitions)
definitions = list(definitions)
definitions.reverse()



for node in definitions:
    print(node)
