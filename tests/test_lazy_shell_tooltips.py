import json
import sys
import types
from pathlib import Path

import pytest
from optimisation_fakes import gun, make_panel_module, make_tooltip_module, shell

CLIENT_SCRIPTS = (
    Path(__file__).resolve().parents[1] / "optimisation" / "res" / "scripts" / "client"
)
MOD_PACKAGES = ("gui.cpuperformance", "gui.mods")
CONFIG_DIR = Path("mods/configs/ANIALLATOR.cpu_performance")
PANEL_MODULE = "gui.Scaleform.daapi.view.battle.shared.consumables_panel"
TOOLTIP_MODULE = "gui.Scaleform.framework.tooltip_mgr"


def _forget_mod_modules():
    for name in list(sys.modules):
        if any(name == pkg or name.startswith(pkg + ".") for pkg in MOD_PACKAGES):
            del sys.modules[name]


def write_config(**values):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "config.json").write_text(json.dumps(values))


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    panel_module = make_panel_module()
    tooltip_module = make_tooltip_module()
    notes = []
    exceptions = []

    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

    module(
        "debug_utils",
        LOG_NOTE=notes.append,
        LOG_CURRENT_EXCEPTION=lambda: exceptions.append(sys.exc_info()),
    )
    gui = module("gui")
    gui.__path__ = [str(CLIENT_SCRIPTS / "gui")]
    parts = PANEL_MODULE.split(".")
    for depth in range(2, len(parts)):
        module(".".join(parts[:depth]))
    module("gui.Scaleform.framework")
    monkeypatch.setitem(sys.modules, PANEL_MODULE, panel_module)
    monkeypatch.setitem(sys.modules, TOOLTIP_MODULE, tooltip_module)

    _forget_mod_modules()
    import gui.mods.mod_cpuperformance as entry

    panel_class = panel_module.ConsumablesPanel
    state = types.SimpleNamespace(
        entry=entry,
        module=panel_module,
        Panel=panel_class,
        ToolTip=tooltip_module.ToolTip,
        original_make=vars(panel_class)["_makeShellTooltip"],
        original_show=vars(tooltip_module.ToolTip)["onCreateComplexTooltip"],
        notes=notes,
        exceptions=exceptions,
    )
    entry.init()
    yield state
    entry.fini()
    _forget_mod_modules()
    assert not exceptions, exceptions


def _panel(client):
    return client.Panel(
        [
            (shell("ARMOR_PIERCING", "L28A1", 390), gun(9.5)),
            (shell("HIGH_EXPLOSIVE", "L35A1", 480), gun(9.5)),
        ]
    )


def test_attribute_syncs_no_longer_build_tooltips(client):
    panel = _panel(client)

    for _ in range(15):
        panel.update_all_shell_tooltips()

    assert client.Panel.builds == 0
    assert panel.flash_tooltips[0] == "{HEADER}AP{/HEADER}\n/{BODY}L28A1{/BODY}"


def test_hovering_a_shell_shows_the_full_tooltip(client):
    panel = _panel(client)
    panel.update_all_shell_tooltips()
    tooltips = client.ToolTip()

    tooltips.onCreateComplexTooltip(panel.flash_tooltips[1], "normal")

    assert tooltips.shown == [
        "{HEADER}HE{/HEADER}\n/{BODY}damage 480, reload 9.5{/BODY}"
    ]
    assert client.Panel.builds == 1


def test_hovering_again_reuses_the_built_tooltip(client):
    panel = _panel(client)
    panel.update_all_shell_tooltips()
    tooltips = client.ToolTip()

    for _ in range(3):
        tooltips.onCreateComplexTooltip(panel.flash_tooltips[0], "normal")

    assert client.Panel.builds == 1
    assert len(set(tooltips.shown)) == 1


def test_the_next_sync_makes_hover_rebuild_with_new_stats(client):
    panel = _panel(client)
    panel.update_all_shell_tooltips()
    tooltips = client.ToolTip()
    tooltips.onCreateComplexTooltip(panel.flash_tooltips[0], "normal")

    panel.shells[0] = (shell("ARMOR_PIERCING", "L28A1", 390), gun(8.7))
    panel.update_all_shell_tooltips()
    tooltips.onCreateComplexTooltip(panel.flash_tooltips[0], "normal")

    assert tooltips.shown[-1].endswith("reload 8.7{/BODY}")
    assert client.Panel.builds == 2


def test_other_tooltips_pass_through(client):
    tooltips = client.ToolTip()

    tooltips.onCreateComplexTooltip("{HEADER}Repair kit{/HEADER}", "normal")

    assert tooltips.shown == ["{HEADER}Repair kit{/HEADER}"]


def test_without_technical_info_the_game_builds_as_before(client):
    client.module.GUI_SETTINGS.technicalInfo = False
    panel = _panel(client)

    panel.update_all_shell_tooltips()

    assert client.Panel.builds == 2
    assert "damage 390" in panel.flash_tooltips[0]


def test_a_closed_panel_falls_back_to_the_placeholder(client):
    panel = _panel(client)
    panel.update_all_shell_tooltips()
    placeholder = panel.flash_tooltips[0]
    del panel
    tooltips = client.ToolTip()

    tooltips.onCreateComplexTooltip(placeholder, "normal")

    assert tooltips.shown == [placeholder]


def test_turning_the_fix_off_restores_the_game_behaviour(client):
    client.entry.fini()
    write_config(lazyShellTooltips=False)
    client.entry.init()
    panel = _panel(client)

    panel.update_all_shell_tooltips()

    assert client.Panel.builds == 2


def test_uninstall_restores_both_methods(client):
    client.entry.fini()

    assert vars(client.Panel)["_makeShellTooltip"] is client.original_make
    assert vars(client.ToolTip)["onCreateComplexTooltip"] is client.original_show


def test_missing_tooltip_manager_leaves_the_panel_alone(client, monkeypatch):
    client.entry.fini()
    monkeypatch.delattr(client.ToolTip, "onCreateComplexTooltip")
    client.entry.init()

    assert vars(client.Panel)["_makeShellTooltip"] is client.original_make
    assert any("onCreateComplexTooltip not found" in note for note in client.notes)
