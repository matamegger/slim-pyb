from typing import IO


class LineProvider:

    def next(self) -> str:
        pass

    def line(self) -> str:
        pass

    def destroy(self):
        pass


class FileLineProvider(LineProvider):
    __file: IO = None
    __currentLine: str = None

    def __init__(self, file):
        self.__file = file

    def next(self) -> str:
        self.__currentLine = self.__file.readline()
        return self.__currentLine

    def line(self):
        return self.__currentLine

    def destroy(self):
        self.__file.close()