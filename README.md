# SliM Pyb
Python framework to generate binaries and Python bindings for Simulink Models.
___

## Motivation
MathWorks Simulink is a great tool setup and simulate dynamical systems as well as the according control systems. The convenience of the graphical interface and the possibilities of the MatLab code and engine behind it, contributed to a wide popularity of the tool set.
Unfortunately, the proprietary closed system does not allow for a big community and in case of missing tools or functionality one has to wait until MathWorks provides the according tools.

Python is a widely known programming language, with a strong community and many well maintained packages to realize various applications. 

The motivation for this project is to combine the community and possibilities of Python with the convenience of Simulink and the knowledge and work that has been already created in models.
It should be easy to make Simulink Models accessible for Python environments and allow the sharing of these environments with systems that do not have MathWorks software installed.

Many projects that use MatLab and Simulink from another programming environment depend on these software components to be installed and basically running Matlab/Simulink in the background. 

MathWorks provides the possibility of generating C/C++ code and even shared libraries, which can then be used without MathWorks software being installed.
Those shared libraries are far more efficient than running MatLab/Simulink in the background.

_While the export of shared libraries is only possible with the Embedded Coder package, we only need the (cheaper) Simulink Coder package to generate code._

## What is generated?

A set of binaries (for Linux, Mac and Windows) as well as a set of python files. If bundled into a module, it is very easy to
share these with other, as there are no further dependencies besides Python itself.

The binaries represent the Simulink model(s), but not custom calling code written in `.m` files. Workflows that set and read properties
or control the simulation progress are not part of the generated files. After all that's what we aim to do from python. 

## Prerequisites

The generation of the code of the Simulink model obviously needs **Simulink** as well as the **Simulink Coder** plugin.

_Once the code is generated none of the MatLab software is needed anymore._

To run this project [python3](https://www.python.org/downloads/) as well as [pipenv](https://pypi.org/project/pipenv/) is needed. Additionally, [docker](https://docs.docker.com/get-docker/) must be installed to compile the code for multiple platforms.

The python packages that need to be installed should be handled by `pipenv` and the included `Pipfile`.

## Usage

If you do not have the generated code for the Simulink Model you first need to [generate it](ExportSimulinkModel.md).

Once you have the generated the code further steps can be executed on machines were MatLab/Simulink is not installed.

The zip file that was generated by Matlab should be extracted. 
Down in the file tree there should be a c header file with your project name. (e.g. `myProject.h)
The path to this header file is the first argument. It represents the definition of the system.

A full command would look like this:
```
python3 main.py ~/path/to/header.h outputDirectory -b binaryName -g PythonBindingsName -c
```

`-b binaryName` serves two purposes. When the `-c` (compile) parameter is provided, the model code will be compiled into binaries
with the provided base name. When the `-g PythonBindingsName` parameter is provided, the generated python binding will look for `binaryName` binary
files when initialized.
`-g PythonBindingsName` is also needed to enable the bindings generation, where the given name will be the name of the python class as well as a lower-case variant the file name.

Given this setup it is possible to independently compile the binaries and generate python bindings.

## References

To showcase the usage of converted Simulink Models, an [example project](https://github.com/matamegger/reinforced-pid-parameter) with a machine learning environment has been created.

## FAQ

#### Why using docker for the compilation?
Apparently cross-platform compiling is not very easy to setup.
To make the usage of this project easier, but still support major platforms a docker image is used.

## Credits
- [eliben/pycparser](https://github.com/eliben/pycparser)
  - The content of the folder `fake_libc_include` is copied from [eliben/pycparser](https://github.com/eliben/pycparser), which is licensed under BSD.
- [dapperfu/Python-Simulink](https://github.com/dapperfu/Python-Simulink)
- [multiarch/crossbuild](https://github.com/multiarch/crossbuild)