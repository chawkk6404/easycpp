import re
from typing import Any, Dict, List, Match, Optional


__all__ = 'generate_stubs',


_FILE_SUFFIX_REGEX = re.compile(r'\.c(pp)?')
_FUNCTION_REGEX = re.compile(r'([\w\d]+) ([\w_]+)(\([\w\d*\s\[\]]+\))')
_POINTER_OR_ADDRESS = re.compile('[*&]')
_GET_CLASSES_REGEX = re.compile(r'class[\s\n\t]*([\w\d_]+)[\s\n\t]*\{[.\n]*')
_CLASS_REGEX = re.compile(r'class[\s\n\t]*([\w\d_]+)')
_VAR_REGEX = re.compile(r'([\w\d_]+)\s+[*&]*([\w\d_]+);')
_ARRAY_REGEX = re.compile(r'([\w\d_]+)\s+[*&]*([\w\d_]+)[\s\t\n]*\[[\s\t]*.*[\s\t]*]')


_sentinel: Any = object()


_CTYPES_CONVERSIONS: Dict[str, Optional[type]] = {
    'void': None,
    'bool': bool,
    'char': str,
    'wchar_t': str,
    'short': int,
    'int': int,
    'long': int,
    '__int64': int,
    'size_t': int,
    'ssize_t': int,
    'float': float,
    'double': float
}


def _get_name(string: str, classes: List[str]) -> str:
    type_ = _CTYPES_CONVERSIONS.get(string, _sentinel)

    if type_ is _sentinel:
        if string in classes:
            type_ = string
        else:
            type_ = 'typing.Any'

    if isinstance(type_, type):
        type_ = type_.__name__
    return str(type_)


BASE_STRING = '''import typing

T = typing.TypeVar('T')


class _MutableCollection(typing.Collection[T]):  # this is made to type arrays
    def __getitem__(self, name: str) -> T: ...
    def __setitem__(self, index: int, value: T) -> None: ...
    def __delitem__(self, index: int) -> None: ...
    
# typing for C++ below

'''


def generate_stubs(path: str):
    """
    Generate stub files (``.pyi``) for a C++ file.

    Parameters
    -----------
    path: :class:`str`
        The path to the file.


    .. note::
        It can get a bit messy but it still does the job! Here is an example of a generated file.

        .. code:: py

            import typing

            T = typing.TypeVar('T')


            class _MutableCollection(typing.Collection[T]):  # this is made to type arrays
                def __getitem__(self, name: str) -> T: ...
                def __setitem__(self, index: int, value: T) -> None: ...
                def __delitem__(self, index: int) -> None: ...

            # typing for C++ below

            class Human:
                ...
                name: str
            def hello(human: Human) -> None: ...
                """
    stubs_path = _FILE_SUFFIX_REGEX.sub('.pyi', path)

    with open(path, 'r') as file:
        code = file.read()

    stubs_string = BASE_STRING
    current_level = 0

    classes = [name for name in _GET_CLASSES_REGEX.findall(code)]

    for line in code.split('\n'):
        function_match = _FUNCTION_REGEX.search(line)
        class_match = _CLASS_REGEX.search(line)
        var_match = _VAR_REGEX.search(line)
        array_match = _ARRAY_REGEX.search(line)

        if class_match:
            stubs_string += ' ' * current_level + f'class {class_match.group(1)}:\n'\
                            + ' ' * (current_level + 4) + '...\n'

        if function_match:
            stubs_string += _get_function_annotations(function_match, classes, current_level)

        if var_match:
            var_type = _get_name(var_match.group(1), classes)
            stubs_string += ' ' * current_level + f'{var_match.group(2)}: {var_type}\n'

        if array_match:
            array_type = _get_name(array_match.group(1), classes)
            array_name = array_match.group(2)
            stubs_string += ' ' * current_level + f'{array_name}: _MutableCollection[{array_type}]\n'

        if '{' in line and not function_match:
            current_level += 4
        if '}' in line and current_level >= 4 and not function_match:
            current_level -= 4

    with open(stubs_path, 'w') as file:
        file.write(stubs_string)


def _get_function_annotations(function_match: Match[str], classes: List[str], current_level: int) -> str:
    name = function_match.group(2)
    signature = ' ' * current_level + f'def {name}('
    parameters = function_match.group(3).replace('(', '').replace(')', '').split(',')

    for parameter in parameters:
        parameter = parameter.strip().replace('  ', ' ')

        parameter_type_string, parameter_name = parameter.split(' ')
        parameter_type_string = _POINTER_OR_ADDRESS.sub('', parameter_type_string)
        parameter_type = _get_name(parameter_type_string, classes)

        parameter_name = _POINTER_OR_ADDRESS.sub('', parameter_name)

        signature += f'{parameter_name}: {parameter_type}'

    return_type_string = function_match.group(1).lstrip('*').lstrip('unsigned ').lstrip('long ')
    return_type = _get_name(return_type_string, classes)

    signature += ') -> '
    signature += return_type
    signature += ': ...\n\n'

    return signature
