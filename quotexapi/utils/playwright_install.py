from __future__ import annotations

import subprocess

from playwright._impl._driver import compute_driver_executable
from playwright._impl._driver import get_driver_env
from playwright.async_api import BrowserType as AsyncBrowserType
from playwright.sync_api import BrowserType as SyncBrowserType

__version__ = "0.0.0"
__all__ = ["install"]


def install(
    browser_type: SyncBrowserType | AsyncBrowserType,
    *,
    with_deps: bool = False,
) -> bool:
    """install playwright and deps if needed

    :param browser_type: `BrowserType` object. Example: `p.chrome`
    :type browser_type: SyncBrowserType | AsyncBrowserType
    :param with_deps: install with dependencies. Defaults to `False`.
    :type with_deps: bool
    :param browser_type: SyncBrowserType | AsyncBrowserType: 
    :param *: 
    :param with_deps: bool:  (Default value = False)
    :returns: succeeded or failed
    :rtype: bool

    """
    driver_executable = str(compute_driver_executable())
    args = [driver_executable, "install-deps"]
    env = None
    if browser_type:
        args = ["playwright", "install", browser_type.name]
        env = get_driver_env()
        if with_deps:
            args.append("--with-deps")

    proc = subprocess.run(args, env=env, capture_output=True, text=True)

    return proc.returncode == 0
