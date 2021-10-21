import ctypes

primitive_names_to_ctypes = {
    "byte": ctypes.c_byte,
    "char": ctypes.c_char,
    "signed char": ctypes.c_char,
    "short": ctypes.c_short,
    "int": ctypes.c_int,
    "unsigned": ctypes.c_int,
    "int8": ctypes.c_int8,
    "int16": ctypes.c_int16,
    "int32": ctypes.c_int32,
    "int64": ctypes.c_int64,
    "long": ctypes.c_long,
    "long int": ctypes.c_long,
    "long long": ctypes.c_longlong,
    "float": ctypes.c_float,
    "double": ctypes.c_double,
    "long double": ctypes.c_longdouble,
    "unsigned byte": ctypes.c_ubyte,
    "unsigned char": ctypes.c_ubyte,
    "unsigned short": ctypes.c_ushort,
    "unsigned int": ctypes.c_uint,
    "unsigned int8": ctypes.c_uint8,
    "unsigned int16": ctypes.c_uint16,
    "unsigned int32": ctypes.c_uint32,
    "unsigned int64": ctypes.c_uint64,
    "unsigned long": ctypes.c_ulong,
    "unsigned long long": ctypes.c_ulonglong,
    "size_t": ctypes.c_size_t,
    "ptrdiff_t": ctypes.c_ssize_t,
    "void": None
}

primitive_names = set([k for k, v in primitive_names_to_ctypes.items()])