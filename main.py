import os.path
import sys
from dataclasses import replace
from pathlib import Path

from pycparser import parse_file

from astparser.parser import AstParser
from bindinggenerator.generator import primitive_names, PythonBindingFileGenerator, ElementArranger
from bindinggenerator.moduelcleaner import ModuleCleaner
from bindinggenerator.writer import PythonWriter, FileOutput, CtypesMapper

if __name__ == '__main__':
    main_file_path = os.path.expanduser(sys.argv[1])
    output_file_path = os.path.expanduser(sys.argv[2])
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

    bindingGenerator = PythonBindingFileGenerator()
    generated_python = bindingGenerator.generate(module)
    #print(generated_python)
    arranged_elements = ElementArranger().arrange(generated_python.elements, primitive_names)
    generated_python = replace(generated_python, elements=arranged_elements)

    output = FileOutput(output_file_path)
    mapper = CtypesMapper()
    writer = PythonWriter(mapper)

    writer.write(generated_python, output)

    #output_file = open(output_file_path, "w")
    #output_file.write(generated_python)
    #output_file.close()