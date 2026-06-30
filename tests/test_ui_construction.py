"""Construct every Modal and setup panel to catch reserved-attribute shadows and
other construction-time crashes.

This is the bug class the per-module unit tests structurally miss: they assert a
panel's *layout* but never actually instantiate a Modal, which is where naming a
field ``self.timeout`` (shadowing Modal's reserved ``timeout`` attribute) blows up
— discord.py does ``time.monotonic() + self.timeout`` on store and gets a TextInput.

The panel test self-discovers every ``WizardView`` subclass, so a new ``,setup``
panel is covered automatically. The modal test keeps an explicit construction case
per Modal (constructors differ), and ``test_every_modal_has_a_construction_case``
fails if a new Modal is added without one.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import SimpleNamespace

import discord
import pytest

import src.modules
from src.core.paginator import CommandBrowser, _CommandSearchModal
from src.core.views import WizardView
from src.modules.automod import setup_view as automod_sv
from src.modules.embed import views as embed_views
from src.modules.leveling import setup_view as leveling_sv
from src.modules.music import setup_view as music_sv
from src.modules.prefix import setup_view as prefix_sv
from src.modules.vanity import setup_view as vanity_sv
from src.modules.voicemaster import views as vm_views


def _import_all_ui_modules() -> None:
    """Import every setup_view / views module so __subclasses__ is fully populated."""
    for info in pkgutil.walk_packages(src.modules.__path__, "src.modules."):
        if info.name.rsplit(".", 1)[-1] in ("setup_view", "views"):
            importlib.import_module(info.name)


_import_all_ui_modules()


def _wizard_panels() -> list[type]:
    return sorted(WizardView.__subclasses__(), key=lambda c: c.__name__)


def test_setup_panels_are_discovered():
    # Guard against the discovery silently returning nothing (which would make the
    # parametrized test below vacuously pass).
    assert len(_wizard_panels()) >= 8


@pytest.mark.parametrize("panel_cls", _wizard_panels(), ids=lambda c: c.__name__)
def test_setup_panel_constructs_without_shadowing_reserved_attrs(panel_cls):
    view = panel_cls(1, 100)
    assert isinstance(view, discord.ui.View)
    # `timeout` is reserved (float | None); a widget assigned to self.timeout breaks
    # discord.py when the view is stored.
    assert view.timeout is None or isinstance(view.timeout, (int, float))


def _modal_cases() -> list[tuple[type, object]]:
    """(modal class, zero-arg builder) for every Modal in the codebase."""
    am_v = automod_sv.AutomodSetupView(1, 100)
    lv_v = leveling_sv.LevelingSetupView(1, 100)
    vn_v = vanity_sv.VanitySetupView(1, 100)
    pf_v = prefix_sv.PrefixSetupView(1, 100)
    mu_v = music_sv.MusicSetupView(1, 100)
    eb = embed_views.EmbedBuilderView(1)
    ch = SimpleNamespace(id=1, name="vc", user_limit=0)
    cb = CommandBrowser(1, [], "Cat", ",")
    return [
        (automod_sv._LimitsModal, lambda: automod_sv._LimitsModal(am_v)),
        (automod_sv._EscalationModal, lambda: automod_sv._EscalationModal(am_v)),
        (automod_sv._WordsModal, lambda: automod_sv._WordsModal(am_v)),
        (leveling_sv._XpModal, lambda: leveling_sv._XpModal(lv_v)),
        (leveling_sv._MessageModal, lambda: leveling_sv._MessageModal(lv_v)),
        (vanity_sv._MessageModal, lambda: vanity_sv._MessageModal(vn_v)),
        (prefix_sv._PrefixModal, lambda: prefix_sv._PrefixModal(pf_v)),
        (music_sv._VolumeModal, lambda: music_sv._VolumeModal(mu_v)),
        (embed_views._ContentModal, lambda: embed_views._ContentModal(eb)),
        (embed_views._AuthorFooterModal, lambda: embed_views._AuthorFooterModal(eb)),
        (embed_views._ImagesModal, lambda: embed_views._ImagesModal(eb)),
        (embed_views._AddFieldModal, lambda: embed_views._AddFieldModal(eb)),
        (embed_views._EditFieldModal, lambda: embed_views._EditFieldModal(eb, 0, {})),
        (embed_views._ImportModal, lambda: embed_views._ImportModal(eb)),
        (vm_views._RenameModal, lambda: vm_views._RenameModal(ch)),
        (vm_views._LimitModal, lambda: vm_views._LimitModal(ch)),
        (_CommandSearchModal, lambda: _CommandSearchModal(cb)),
    ]


_MODAL_CASES = _modal_cases()


@pytest.mark.parametrize("case", _MODAL_CASES, ids=[c.__name__ for c, _ in _MODAL_CASES])
def test_modal_constructs_without_shadowing_timeout(case):
    modal_cls, build = case
    modal = build()
    assert isinstance(modal, discord.ui.Modal)
    # The exact automod bug: a TextInput must never be assigned to self.timeout.
    assert modal.timeout is None, f"{modal_cls.__name__} shadows Modal.timeout"


def test_every_modal_has_a_construction_case():
    """A newly added Modal must get a construction case above, or this fails."""
    discovered: set[type] = set()
    stack: list[type] = [discord.ui.Modal]
    while stack:
        for sub in stack.pop().__subclasses__():
            if sub not in discovered:
                discovered.add(sub)
                stack.append(sub)
    ours = {c for c in discovered if c.__module__.startswith("src.")}
    covered = {cls for cls, _ in _MODAL_CASES}
    missing = sorted(c.__name__ for c in ours - covered)
    assert not missing, f"Modal(s) lacking a construction test: {missing}"


def _all_view_subclasses() -> set[type]:
    seen: set[type] = set()
    stack: list[type] = [discord.ui.View]
    while stack:
        for sub in stack.pop().__subclasses__():
            if sub not in seen:
                seen.add(sub)
                stack.append(sub)
    return {c for c in seen if c.__module__.startswith("src.")}


def test_no_ui_item_shadows_a_reserved_view_attribute():
    """A decorated button/select must not be named after a base View/Modal member.

    discord.py stores decorated items per class in ``__view_children_items__``; naming
    one ``_refresh`` (or ``stop``, ``timeout``, ``children`` ...) replaces that base
    member with an Item, which blows up inside discord.py (e.g. it calls
    ``view._refresh(components)`` on a message edit and the Button isn't callable). This
    static check catches the whole class for every view without needing to construct it.
    """
    view_reserved = set(dir(discord.ui.View))
    modal_reserved = set(dir(discord.ui.Modal))
    offenders: list[str] = []
    for cls in _all_view_subclasses():
        items = getattr(cls, "__view_children_items__", {})
        reserved = modal_reserved if issubclass(cls, discord.ui.Modal) else view_reserved
        offenders += [f"{cls.__name__}.{name}" for name in items if name in reserved]
    assert not offenders, f"UI items shadow base View/Modal attributes: {sorted(offenders)}"
