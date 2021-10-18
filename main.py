import os.path
import sys
from pathlib import Path

from pycparser import parse_file

from astparser.parser import AstParser
from bindinggenerator.generator import BindingGenerator
from bindinggenerator.simplifyer import ModuleCleaner

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
    astParser.origin_file_filter = lambda it: "fake_libc_include" not in it
    module = astParser.parse(ast)
    module = ModuleCleaner().remove_not_used_elements(module)

    bindingGenerator = BindingGenerator()
    generated_python = bindingGenerator.generate(module)
    output_file = open(output_file_path, "w")
    output_file.write(generated_python)
    output_file.close()