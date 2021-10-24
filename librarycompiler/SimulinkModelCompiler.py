import os
import subprocess
import sys
from enum import Enum
from os.path import join
from shutil import copyfile


class Platform(Enum):
    LINUX = 0
    MAC = 1
    WINDOWS = 2


class SimulinkModelCompiler:
    _BASE_COMMAND = "docker run --rm -v \"{1}\":/output -v \"{0}\":/workdir -e CROSS_TRIPLE={2}  multiarch/crossbuild" \
                    " make -f \"{5}\" \"{3}\" \"name={4}\" output_dir=\"/output\""
    _MAKE_FILE = os.path.join(os.path.dirname(__file__), 'Makefile')
    _MAKEFILE_NAME = ""

    def __init__(self, makefile_name: str = "Makefile"):
        self._MAKEFILE_NAME = makefile_name

    @staticmethod
    def _library_extension_for_platform(platform: Platform) -> str:
        if platform == Platform.LINUX:
            return "so"
        elif platform == Platform.MAC:
            return "dylib"
        elif platform == Platform.WINDOWS:
            return "dll"
        else:
            raise Exception("Unknown platform")

    @staticmethod
    def _target_triple_for_platform(platform: Platform) -> str:
        if platform == Platform.LINUX:
            return "x86_64-linux-gnu"
        elif platform == Platform.MAC:
            return "x86_64-apple-darwin"
        elif platform == Platform.WINDOWS:
            return "x86_64-w64-mingw32"
        else:
            raise Exception("Unknown platform")

    def _setup(self, path: str):
        self.place_makefile(path)

    def _cleanup(self, path: str):
        os.remove(join(path, self._MAKEFILE_NAME))

    def compile(self, path: str, output_path: str, name: str, do_not_create_makefile: bool = False):
        path = os.path.abspath(os.path.expanduser(path))
        output_path = os.path.abspath(os.path.expanduser(output_path))
        if not do_not_create_makefile:
            self._setup(path)
        self._compile(Platform.LINUX, path, output_path, name)
        self._compile(Platform.MAC, path, output_path, name)
        self._compile(Platform.WINDOWS, path, output_path, name)
        if not do_not_create_makefile:
            self._cleanup(path)

    def place_makefile(self, path: str, makefile_name: str = None):
        if makefile_name is None:
            makefile_name = self._MAKEFILE_NAME
        copyfile(self._MAKE_FILE, join(path, makefile_name))

    def _compile(
            self,
            platform: Platform,
            path: str,
            output_path: str,
            output_name: str,
            makefile_name: str = None
    ):
        if makefile_name is None:
            makefile_name = self._MAKEFILE_NAME
        if platform == Platform.WINDOWS:
            output_name += "_win64"
        file_extension = self._library_extension_for_platform(platform)
        target_triple = self._target_triple_for_platform(platform)
        command = self._BASE_COMMAND.format(
            path,
            output_path,
            target_triple,
            file_extension,
            output_name,
            makefile_name
        )

        process = subprocess.Popen(command,
                                   shell=True,
                                   stdout=sys.stdout,
                                   stderr=sys.stderr)

        return_code = process.wait()
        if return_code != 0:
            raise Exception("Could not compile")
