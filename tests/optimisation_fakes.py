"""Stand-ins for the consumables panel and tooltip manager.

Behaviour mirrors the sources pinned in docs/DECOMPILED_REFERENCE.md.
"""

import types

TOOLTIP_FORMAT = "{{HEADER}}{0:>s}{{/HEADER}}\n/{{BODY}}{1:>s}{{/BODY}}"
SHELL_KINDS = {"ARMOR_PIERCING": "AP", "HIGH_EXPLOSIVE": "HE"}


def make_panel_module():
    gui_settings = types.SimpleNamespace(technicalInfo=True)
    kinds = types.SimpleNamespace(dyn=lambda kind: lambda: "kind:" + kind)
    R = types.SimpleNamespace(
        strings=types.SimpleNamespace(
            item_types=types.SimpleNamespace(shell=types.SimpleNamespace(kinds=kinds))
        )
    )
    backport = types.SimpleNamespace(
        text=lambda resource: SHELL_KINDS[resource.split(":", 1)[1]]
    )

    class ConsumablesPanel:
        """Builds the full tooltip, like the game, and records how often."""

        builds = 0

        def __init__(self, shells):
            self.shells = shells
            self.flash_tooltips = {}

        def _makeShellTooltip(self, descriptor, gunSettings):
            type(self).builds += 1
            header = backport.text(kinds.dyn(descriptor.kind)())
            body = f"damage {descriptor.damage}, reload {gunSettings.reload}"
            return TOOLTIP_FORMAT.format(header, body)

        def as_updateTooltipS(self, idx, tooltipStr):
            self.flash_tooltips[idx] = tooltipStr

        def update_all_shell_tooltips(self):
            """ConsumablesPanel.__updateAllShellTooltips."""
            for idx, (descriptor, gunSettings) in enumerate(self.shells):
                tooltip = self._makeShellTooltip(descriptor, gunSettings)
                self.as_updateTooltipS(idx=idx, tooltipStr=tooltip)

    return types.SimpleNamespace(
        __name__="consumables_panel",
        ConsumablesPanel=ConsumablesPanel,
        GUI_SETTINGS=gui_settings,
        R=R,
        backport=backport,
        TOOLTIP_FORMAT=TOOLTIP_FORMAT,
    )


def make_tooltip_module():
    class ToolTip:
        def __init__(self):
            self.shown = []

        def onCreateComplexTooltip(self, tooltipId, stateType):
            self.shown.append(tooltipId)

    return types.SimpleNamespace(__name__="tooltip_mgr", ToolTip=ToolTip)


def shell(kind, name, damage):
    return types.SimpleNamespace(kind=kind, userString=name, damage=damage)


def gun(reload):
    return types.SimpleNamespace(reload=reload)
