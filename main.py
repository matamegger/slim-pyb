import argparse
import os.path
import sys
from pathlib import Path

from pycparser import parse_file

from astparser.moduelcleaner import ModuleCleaner
from astparser.parser import AstParser
from bindinggenerator import primitive_names
from bindinggenerator.systemgenerator import SystemGenerator
from bindinggenerator.writer import PythonBindingWriter, CtypesMapper, SystemWriter
from librarycompiler.SimulinkModelCompiler import SimulinkModelCompiler


class PathAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, os.path.expanduser(values))


def dir_path(path):
    if os.path.isdir(os.path.expanduser(path)):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


def header_file(file: str):
    if os.path.isfile(os.path.expanduser(file)) and file.endswith(".h"):
        return file
    else:
        raise argparse.ArgumentTypeError(f"{file} is not a valid header (.h) file")


def generate_bindings(main_file: str, output_path: str, bindgins_name: str, binary_name: str):
    fake_libc_location = str(Path(__file__).parent.absolute().joinpath("fake_libc_include"))

    ast = parse_file(main_file,
                     use_cpp=True,
                     cpp_path="clang",
                     cpp_args=['-E', "-I" + fake_libc_location, '-D_Atomic(x)=x', '-D_Bool=int', '-D__extension__=',
                               '-U__STDC__'])
    ast_parser = AstParser()
    module_cleaner = ModuleCleaner()
    module_cleaner.externally_known_type_name = primitive_names
    ast_parser.origin_file_filter = lambda it: "fake_libc_include" not in it
    module = ast_parser.parse(ast)
    module = module_cleaner.remove_not_used_elements(module)

    system_generator = SystemGenerator()
    system = system_generator.generate(
        module,
        name=bindgins_name,
        binary_basename=binary_name
    )

    ctypes_mapper = CtypesMapper()
    system_writer = SystemWriter(ctypes_mapper)
    system_writer.write(system, output_path, PythonBindingWriter(ctypes_mapper))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Compile and generate python bindings from Simulink Code Generator generated code.'
    )
    parser.add_argument(dest='header', type=header_file, action=PathAction)
    parser.add_argument(dest='output_path', action='store', type=dir_path)
    parser.add_argument('-b', '--binary-name', dest='binary_name', action='store', default=None)
    parser.add_argument('-c', '--compile', dest="compile", action='store_true', default=False)
    parser.add_argument('-g', '--generate-bindings', dest='bindings_name', action='store', default=None)

    arguments = parser.parse_args(sys.argv[1:])

    binary_name = arguments.binary_name
    if binary_name is None:
        binary_name = Path(arguments.header).stem

    if arguments.compile:
        print(f"Compiling binaries with basename {binary_name}")
        SimulinkModelCompiler().compile(str(Path(arguments.header).parent), arguments.output_path, binary_name)
        print("Done compiling")

    if arguments.bindings_name is not None:
        print(f"Generating bindings for {arguments.bindings_name}")
        generate_bindings(arguments.header, arguments.output_path, arguments.bindings_name, binary_name)
        print("Done generating bindings")
