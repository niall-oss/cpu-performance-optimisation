__version__ = "0.1.0"


def init():
    from gui.cpuperformance import config
    from gui.cpuperformance import hooks

    config.load()
    hooks.install()


def fini():
    from gui.cpuperformance import hooks

    hooks.uninstall()
