__version__ = "0.2.0"


def init():
    from gui.cpuprofiler import config
    from gui.cpuprofiler import hooks

    config.load()
    if config.get("enabled"):
        hooks.install()


def fini():
    from gui.cpuprofiler import hooks

    hooks.uninstall()
