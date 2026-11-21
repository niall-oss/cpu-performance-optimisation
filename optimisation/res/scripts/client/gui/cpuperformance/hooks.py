from debug_utils import LOG_NOTE

from gui.cpuperformance import lazy_shell_tooltips
from gui.cpuperformance.override_utils import override, restore

_overrides = []


def _load(module_name, class_name):
    try:
        module = __import__(module_name, fromlist=[class_name])
    except ImportError:
        return None, None
    return module, getattr(module, class_name, None)


def _targets():
    panel_module, panel = _load(lazy_shell_tooltips.PANEL_MODULE, "ConsumablesPanel")

    def make_shell_tooltip(original, self, descriptor, gunSettings):
        return lazy_shell_tooltips.make_shell_tooltip(
            panel_module, original, self, descriptor, gunSettings)

    _, tooltip_mgr = _load(lazy_shell_tooltips.TOOLTIP_MODULE, "ToolTip")
    # Both halves or neither: placeholders nobody swaps would reach the player.
    return (
        (
            (panel, "_makeShellTooltip", make_shell_tooltip),
            (tooltip_mgr, "onCreateComplexTooltip", lazy_shell_tooltips.on_create_complex_tooltip),
        ),
    )


def _supported(group):
    for cls, method_name, _ in group:
        if cls is None or method_name not in vars(cls):
            LOG_NOTE("CPU Performance Optimisation: %s not found, this client is not supported"
                     % method_name)
            return False
    return True


def install():
    if _overrides:
        return True
    for group in _targets():
        if not _supported(group):
            continue
        for cls, method_name, wrapper in group:
            _overrides.append(override(cls, method_name, wrapper))
    return bool(_overrides)


def uninstall():
    while _overrides:
        restore(_overrides.pop())
    lazy_shell_tooltips.forget()
