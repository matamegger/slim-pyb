SRC=$(wildcard *.c)

ifdef output_dir
OUTPUT_DIR = $(output_dir)/
endif

so: $(SRC)
	$(CC) -shared -fPIC -o $(OUTPUT_DIR)$(name).so $^ $(CFLAGS) $(LIBS)

dylib: $(SRC)
	$(CC) -dynamiclib -o $(OUTPUT_DIR)$(name).dylib $^ $(CFLAGS) $(LIBS)

dll: $(SRC)
	$(CC) -shared -o $(OUTPUT_DIR)$(name).dll $^ $(CFLAGS) $(LIBS)

