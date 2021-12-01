# SliM Pyb
Generate binaries and Python bindings for Simulink Models.
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

## Prerequisites

The generation of the code of the Simulink model obviously needs **Simulink** as well as the **Simulink Coder** plugin.

_Once the code is generated none of the MatLab software is needed anymore._

To run this project [python3](https://www.python.org/downloads/) as well as [pipenv](https://pypi.org/project/pipenv/) is needed. Additionally, [docker](https://docs.docker.com/get-docker/) must be installed to compile the code for multiple platforms.

The python packages that need to be installed should be handled by `pipenv` and the included `Pipfile`.

## Usage

If you do not have the generated code for the Simulink Model you first need to generate it.

Once you have the generated the code further steps can be executed on machines without MatLab/Simulink installed.

## Export Code from Simulink

TBD

## FAQ

#### Why using docker for the compilation?
Apparently cross-platform compiling is not very easy to setup.
To make the usage of this project easier, but still support major platforms a docker image is used.

## Credits
- [eliben/pycparser](https://github.com/eliben/pycparser)
- [dapperfu/Python-Simulink](https://github.com/dapperfu/Python-Simulink)