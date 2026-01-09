"""
Utility functions common across Data Science's team plugins and tools
"""
from __future__ import annotations

import inspect
import importlib
from functools import lru_cache
from typing import TYPE_CHECKING, List, Optional, Type, Union

from soongo_data.utils.logging_utils import gen_logger

if TYPE_CHECKING:
    from types import ModuleType


class MissingImport(Exception):

    def __init__(self, package_name):
        super().__init__(
            msg=(
                f'The following required package could not be imported: '
                f'{package_name}'
            )
        )


@lru_cache(maxsize=None)
def safe_import(
    module_name: str,
    min_major_version: int = 0,
    min_minor_version: int = 0,
) -> Optional[ModuleType]:
    """ Safely import the required module.

    Some rare packages may use alphanumerical version numbers. They are not
    handled.

    :param module_name: str name of the module to import (e.g. "pandas")
    :param min_major_version: int minimum major version number of the module to
        import
    :param min_minor_version: int minimum minor version number of the module to
        import

    :return: module if installed at the required minimal version, or None if
        not available.
    """
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        return

    modules = module_name.split('.')
    try:
        if len(modules) > 1:
            version = importlib.import_module(modules[0]).__version__
        else:
            version = module.__version__

    except AttributeError:
        # Importlib may not raise an ImportError when package not available
        # but return an empty namespace with no __version__ attribute
        logger = gen_logger('safe_import')
        logger.warning(
            'Module %s version cannot be verified',
            module_name,
        )
        return module

    try:
        major, minor = version.split(sep='.', maxsplit=2)[:2]
        valid = ((int(major), int(minor)) >= (min_major_version, min_minor_version))
    except Exception:
        logger = gen_logger('safe_import')
        logger.error(
            'Module %s package version format %s not handled',
            module_name,
            version,
        )
        return

    if valid:
        return module
    else:
        logger = gen_logger('safe_import')
        logger.error(
            'Module %s package version %s is below minimum requirements %d.%d',
            module_name,
            version,
            min_major_version,
            min_minor_version,
        )
        return


def lazy_import(
    str_import_path: str,
    object: Optional[str] = None,
) -> Union[ModuleType, Type]:
    """ Import a module lazily.

    :param str_import_path: str path to the module to import (e.g. "pandas").
    To import a specific class from a module, pass the path separated by '.'
    e.g. "pandas.DataFrame". This will import the module and return the class.

    :return: imported module / class
    """
    module = importlib.import_module(str_import_path)
    if object is None:
        return module

    return getattr(module, object)


def import_child_class_from_path(path: str, parent_class: Type) -> List[Type]:
    """
    Dynamically imports and returns the first child class of the given parent_class
    found in the specified file path.

    :param path: The file path to import the class from.
    :param parent_class: The parent class to match against.
    :return: The child class of the parent_class, or None if not found.
    """
    # Get the module name from the file path
    module = lazy_import(path)

    # Iterate through all classes in the module
    return [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, parent_class) and obj is not parent_class
    ]
