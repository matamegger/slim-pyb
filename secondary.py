# input_file = os.path.expanduser(sys.argv[1])
# ast = parse_file(input_file,
#                  use_cpp=True,
#                  cpp_path="clang",
#                  cpp_args=['-E', '-Ifake_libc_include', '-D_Atomic(x)=x', '-D_Bool=int', '-D__extension__=',
#                            '-U__STDC__'])


# class SpringMassDamperSystem:
#     def __init__(self, model="springMassSystem"):
#         self.model = model
#         if platform.system() == "Linux":
#             self.dll_path = os.path.abspath(f"{model}.so")
#             self.dll = ctypes.cdll.LoadLibrary(self.dll_path)
#         elif platform.system() == "Darwin":
#             self.dll_path = os.path.abspath(f"{model}.dylib")
#             self.dll = ctypes.cdll.LoadLibrary(dll_path)
#         elif platform.system() == "Windows":
#             self.dll_path = os.path.abspath(f"{model}_win64.dll")
#             self.dll = ctypes.windll.LoadLibrary(self.dll_path)
#         else:
#             raise Exception("System Not Supported")
#
#         # Model entry point functions
#         self.__initialize = getattr(self.dll, f"{model}_initialize")
#         self.__step = getattr(self.dll, f"{model}_step")
#         self.__model_terminate = getattr(self.dll, f"{model}_terminate")
#
#         # Model signals
#         self._output = real_T.in_dll(self.dll, "OutputSignal")
#         self._time = real_T.in_dll(self.dll, "SimTime")
#
#         # Model Parameters
#         self._input_signal = real_T.in_dll(self.dll, "InputSignal")
#         self._num = (real_T * 2).in_dll(self.dll, "num")
#         self._den = (real_T * 2).in_dll(self.dll, "den")
import ctypes


class Base:
    fields: list = []

D = None

def WRAP(arg):
    return arg

class A(ctypes.Structure):
    pass


C =A

class B(ctypes.Structure):
    pass


B._fields_ = [
        ("another", ctypes.POINTER(A)),
    ]

A._fields_ = [
        ("test", B),
    ]


print(B._fields_[0][1])
print(A._fields_[0][1]._fields_)