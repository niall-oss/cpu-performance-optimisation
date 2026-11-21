"""Builds shell tooltips on hover instead of every time vehicle attributes sync.

ConsumablesPanel._makeShellTooltip computes full shell stats (~25 ms for all
shells) whenever the server re-sends vehicle attributes, although the text
is only seen when a shell slot is hovered. The slot gets a cheap placeholder
instead, and the tooltip manager swaps in the real text when Flash asks for
that placeholder.
"""
import weakref

from debug_utils import LOG_CURRENT_EXCEPTION

from gui.cpuperformance import config

PANEL_MODULE = "gui.Scaleform.daapi.view.battle.shared.consumables_panel"
TOOLTIP_MODULE = "gui.Scaleform.framework.tooltip_mgr"

# placeholder -> [weak panel, original builder, descriptor, gunSettings,
#                 built tooltip or None]
_pending = {}


def _shell_header(panel_module, descriptor):
    shell_kinds = panel_module.R.strings.item_types.shell.kinds
    return panel_module.backport.text(shell_kinds.dyn(descriptor.kind)())


def _placeholder(panel_module, descriptor):
    """A valid complex tooltip naming the shell, unique per shell type.

    It is what the player would see if the swap ever failed.
    """
    header = _shell_header(panel_module, descriptor)
    return panel_module.TOOLTIP_FORMAT.format(_utf8(header), _utf8(descriptor.userString))


def _utf8(text):
    # Python 2: str.format can't take unicode with non-ASCII characters, and
    # Scaleform strings are UTF-8 str.
    if not isinstance(text, str) and hasattr(text, "encode"):
        return text.encode("utf-8")
    return text


def make_shell_tooltip(panel_module, original, panel, descriptor, gunSettings):
    if not config.is_on("lazyShellTooltips") or not panel_module.GUI_SETTINGS.technicalInfo:
        return original(panel, descriptor, gunSettings)
    try:
        panel_ref = weakref.ref(panel)
        placeholder = _placeholder(panel_module, descriptor)
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return original(panel, descriptor, gunSettings)
    _forget_closed_panels()
    _pending[placeholder] = [panel_ref, original, descriptor, gunSettings, None]
    return placeholder


def _forget_closed_panels():
    for placeholder, entry in list(_pending.items()):
        if entry[0]() is None:
            del _pending[placeholder]


def _build(placeholder):
    entry = _pending.get(placeholder)
    if entry is None:
        return None
    panel_ref, original, descriptor, gunSettings, built = entry
    if built is not None:
        return built
    panel = panel_ref()
    if panel is None:
        del _pending[placeholder]
        return None
    try:
        built = original(panel, descriptor, gunSettings)
    except Exception:
        LOG_CURRENT_EXCEPTION()
        return None
    entry[4] = built
    return built


def on_create_complex_tooltip(original, tooltip_mgr, tooltipId, stateType):
    if tooltipId in _pending:
        tooltipId = _build(tooltipId) or tooltipId
    return original(tooltip_mgr, tooltipId, stateType)


def forget():
    _pending.clear()
