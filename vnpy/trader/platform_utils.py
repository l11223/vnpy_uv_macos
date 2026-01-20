"""
Mac系统平台检测和动态库路径处理工具模块。

提供Mac系统检测、动态库路径处理、framework路径解析等功能，
统一Mac系统适配逻辑，避免代码重复。
"""

import ctypes
import ctypes.util
import os
import platform
from pathlib import Path
from typing import Optional


def is_mac_system() -> bool:
    """
    检测当前系统是否为Mac系统。

    Returns:
        bool: 如果是Mac系统（Darwin）返回True，否则返回False
    """
    return platform.system() == "Darwin"


def is_windows_system() -> bool:
    """
    检测当前系统是否为Windows系统。

    Returns:
        bool: 如果是Windows系统返回True，否则返回False
    """
    return platform.system() == "Windows"


def get_dylib_path(base_path: str, lib_name: str) -> str:
    """
    获取Mac系统动态库（.dylib）的完整路径。

    Args:
        base_path: 动态库所在的基础路径
        lib_name: 动态库名称（不含扩展名）

    Returns:
        str: 动态库的完整路径（包含.dylib扩展名）

    Example:
        >>> get_dylib_path("/usr/local/lib", "mylib")
        '/usr/local/lib/mylib.dylib'
    """
    base = Path(base_path)
    lib_path = base / f"{lib_name}.dylib"
    return str(lib_path)


def get_framework_path(framework_path: str) -> str:
    """
    解析Mac系统framework路径，返回内部可执行文件路径。

    Mac系统的framework结构为：
    xxx.framework/
        Versions/
            A/
                xxx  (实际的可执行文件)

    Args:
        framework_path: framework的基础路径（如：/path/to/xxx.framework）

    Returns:
        str: framework内部可执行文件的完整路径

    Example:
        >>> get_framework_path("/path/to/thostmduserapi_se.framework")
        '/path/to/thostmduserapi_se.framework/Versions/A/thostmduserapi_se'
    """
    framework = Path(framework_path)
    
    # 确保是framework目录
    if not framework_path.endswith(".framework"):
        raise ValueError(f"Invalid framework path: {framework_path}. Must end with .framework")
    
    # 提取framework名称（不含.framework后缀）
    framework_name = framework.stem
    
    # 构建framework内部路径：Versions/A/xxx
    internal_path = framework / "Versions" / "A" / framework_name
    
    return str(internal_path)


def get_mac_arch() -> str:
    """
    获取Mac系统的架构类型。

    Returns:
        str: 系统架构，如'x86_64'（Intel）或'arm64'（Apple Silicon）

    Example:
        >>> get_mac_arch()
        'arm64'  # 或 'x86_64'
    """
    return platform.machine()


def validate_framework_path(framework_path: str) -> bool:
    """
    验证framework路径是否有效。

    Args:
        framework_path: framework的基础路径

    Returns:
        bool: 如果framework路径有效且内部可执行文件存在返回True，否则返回False
    """
    try:
        internal_path = get_framework_path(framework_path)
        return os.path.exists(internal_path) and os.path.isfile(internal_path)
    except (ValueError, OSError):
        return False


def load_mac_library(lib_path: str) -> ctypes.CDLL:
    """
    加载Mac系统动态库，支持.dylib和.framework两种格式。

    Args:
        lib_path: 动态库路径，可以是.dylib文件路径或.framework目录路径

    Returns:
        ctypes.CDLL: 加载的动态库对象

    Raises:
        OSError: 如果动态库加载失败，抛出OSError异常，包含详细的错误信息

    Example:
        >>> # 加载.dylib格式
        >>> lib = load_mac_library("/usr/local/lib/mylib.dylib")
        
        >>> # 加载.framework格式
        >>> lib = load_mac_library("/path/to/thostmduserapi_se.framework")
    """
    if not is_mac_system():
        raise OSError("load_mac_library() can only be used on Mac system")
    
    # 处理framework格式
    if lib_path.endswith(".framework"):
        try:
            internal_path = get_framework_path(lib_path)
            if not os.path.exists(internal_path):
                raise OSError(
                    f"Framework internal file not found: {internal_path}\n"
                    f"Please check if the framework is properly installed.\n"
                    f"For Mac system security, you may need to manually open the framework "
                    f"binary file in Finder to add it to the system trust list."
                )
            return ctypes.CDLL(internal_path)
        except ValueError as e:
            raise OSError(f"Invalid framework path: {e}")
    
    # 处理.dylib格式
    elif lib_path.endswith(".dylib"):
        if not os.path.exists(lib_path):
            raise OSError(
                f"Dynamic library not found: {lib_path}\n"
                f"Please check if the library file exists and the path is correct."
            )
        return ctypes.CDLL(lib_path)
    
    else:
        raise OSError(
            f"Unsupported library format: {lib_path}\n"
            f"Mac system supports .dylib and .framework formats only."
        )


def find_framework_library(framework_name: str) -> Optional[str]:
    """
    查找Mac系统framework库的路径。

    Args:
        framework_name: framework名称（不含.framework后缀）

    Returns:
        Optional[str]: 如果找到framework返回其路径，否则返回None

    Example:
        >>> path = find_framework_library("thostmduserapi_se")
        >>> if path:
        ...     print(f"Found framework at: {path}")
    """
    if not is_mac_system():
        return None
    
    # 使用ctypes.util.find_library查找
    lib_path = ctypes.util.find_library(framework_name)
    
    if lib_path:
        # 如果是framework路径，直接返回
        if lib_path.endswith(".framework"):
            return lib_path
        # 如果是.dylib路径，尝试查找对应的framework
        # 这里可以根据实际需求扩展查找逻辑
    
    return None


def validate_mac_library(lib_path: str) -> bool:
    """
    验证Mac系统动态库是否有效且可加载。

    Args:
        lib_path: 动态库路径

    Returns:
        bool: 如果动态库有效且可加载返回True，否则返回False
    """
    if not is_mac_system():
        return False
    
    try:
        # 尝试加载库来验证
        load_mac_library(lib_path)
        return True
    except OSError:
        return False
