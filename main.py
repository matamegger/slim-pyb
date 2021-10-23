import os.path
import sys
from pathlib import Path

from pycparser import parse_file

from astparser.moduelcleaner import ModuleCleaner
from astparser.parser import AstParser
from bindinggenerator import primitive_names
from bindinggenerator.systemgenerator import SystemGenerator
from bindinggenerator.writer import PythonBindingWriter, FileOutput, CtypesMapper, SystemWriter

if __name__ == '__main__':
    main_file_path = os.path.expanduser(sys.argv[1])
    output_path = os.path.expanduser(sys.argv[2])
    parent_dir = Path(main_file_path).parent.absolute()

    ast = parse_file(main_file_path,
                     use_cpp=True,
                     cpp_path="clang",
                     cpp_args=['-E', '-Ifake_libc_include', '-D_Atomic(x)=x', '-D_Bool=int', '-D__extension__=',
                               '-U__STDC__'])
    astParser = AstParser()
    moduleCleaner = ModuleCleaner()
    moduleCleaner.externally_known_type_name = primitive_names
    astParser.origin_file_filter = lambda it: "fake_libc_include" not in it
    module = astParser.parse(ast)
    module = moduleCleaner.remove_not_used_elements(module)

    system_generator = SystemGenerator()
    system = system_generator.generate(
        module,
        name="SpringMassDamper",
        binary_basename="springmassdamper"
    )

    ctypes_mapper = CtypesMapper()
    system_writer = SystemWriter(ctypes_mapper)
    system_writer.write(system, output_path, PythonBindingWriter(ctypes_mapper))

    # output_file = open(output_file_path, "w")
    # output_file.write(generated_python)
    # output_file.close()
