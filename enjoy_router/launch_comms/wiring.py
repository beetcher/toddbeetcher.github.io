"""Builds LAUNCH's CMS from the pieces main.py has: the Firestore store, the SMTP key and the environment (CMS_GUIDE.md section 4).

    comms.configure(wiring.build(LazyStore(_get_admin_store), lambda: BREVO_SMTP_KEY.value, os.environ))

Nothing here connects to anything until the first message is sent.
"""
from __future__ import annotations

import smtp_transport
from comms import Comms
from comms.channels.email import EmailChannel
from comms.settings import resolve_mode

from . import kinds as K
from .directory import IndividualDirectory
from .stores import LogStore, SettingsStore, TemplateStore


class LazyStore:
    """Hands every call to the store `getter()` returns, built on first use (so importing main.py needs no credentials)."""

    def __init__(self, getter):
        self._getter = getter

    def __getattr__(self, name):
        return getattr(self._getter(), name)


def build(store, key_getter, environ, sender=None, clock=None) -> Comms:
    """The CMS for the deployed functions. `sender` is the email provider call (default: the Brevo SMTP transport)."""
    send = sender or smtp_transport.send
    return Comms(kinds=K.registry(), directory=IndividualDirectory(store), templates=TemplateStore(store), log=LogStore(store),
                 settings=SettingsStore(store), channels=[EmailChannel(send, key_getter)], mode=resolve_mode(environ), clock=clock)
