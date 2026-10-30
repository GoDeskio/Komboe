"""org.freedesktop.secrets for an unlocked local vault.

Item secrets live in the encrypted vault file. GetSecret fails while the
service is locked. The service does not open a network connection.
"""
from __future__ import annotations

import threading

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

SERVICE = "org.freedesktop.secrets"
PATH = "/org/freedesktop/secrets"
ITEM_IFACE = "org.freedesktop.Secret.Item"
SVC = "org.freedesktop.Secret.Service"
LABEL = "org.freedesktop.Secret.Item.Label"
ATTRS = "org.freedesktop.Secret.Item.Attributes"


class Item(dbus.service.Object):
    def __init__(self, bus, path, service):
        self.service = service
        super().__init__(bus, path)

    @dbus.service.method(ITEM_IFACE, in_signature="o", out_signature="(oayays)")
    def GetSecret(self, session):
        if self.service.locked:
            raise dbus.exceptions.DBusException("org.freedesktop.Secret.Error.IsLocked", "locked")
        secret = self.service.items[str(self._object_path)]["secret"]
        return (dbus.ObjectPath(session), dbus.ByteArray(b""), dbus.ByteArray(secret.encode()), "text/plain")


class SecretService(dbus.service.Object):
    def __init__(self, bus, vault):
        self.bus = bus
        self.vault = vault
        self.locked = False
        self.items = {}
        self._objects = {}
        self._n = 0
        name = dbus.service.BusName(SERVICE, bus)
        super().__init__(name, PATH)

    def _add(self, label, attributes, secret):
        self._n += 1
        path = f"/org/freedesktop/secrets/collection/komboe/{self._n}"
        self.vault.add_item(1, label, {"username": attributes.get("username", ""), "password": secret, "service": attributes.get("service", "")})
        self.items[path] = {"attributes": dict(attributes), "label": label, "secret": secret}
        self._objects[path] = Item(self.bus, path, self)
        return path

    def _reload(self):
        self.items = {}
        for item in self.vault.items():
            fields = item["fields"]
            self._n += 1
            path = f"/org/freedesktop/secrets/collection/komboe/{self._n}"
            self.items[path] = {
                "attributes": {"service": fields.get("service", ""), "username": fields.get("username", "")},
                "label": item["name"],
                "secret": fields.get("password", ""),
            }
            self._objects[path] = Item(self.bus, path, self)

    @dbus.service.method(SVC, in_signature="sv", out_signature="vo")
    def OpenSession(self, _algo, _input):
        return dbus.ByteArray(b""), dbus.ObjectPath("/org/freedesktop/secrets/session/komboe")

    @dbus.service.method(SVC, in_signature="a{sv}(oayays)b", out_signature="oo")
    def CreateItem(self, properties, secret, _replace):
        if self.locked:
            raise dbus.exceptions.DBusException("org.freedesktop.Secret.Error.IsLocked", "locked")
        label = str(properties.get(LABEL, "item"))
        raw_attrs = properties.get(ATTRS, {})
        attributes = {str(k): str(v) for k, v in dict(raw_attrs).items()}
        value = bytes(secret[2]).decode()
        path = self._add(label, attributes, value)
        return dbus.ObjectPath(path), dbus.ObjectPath("/")

    @dbus.service.method(SVC, in_signature="a{ss}", out_signature="aoao")
    def SearchItems(self, attributes):
        matched = []
        for path, item in self.items.items():
            if all(item["attributes"].get(str(k)) == str(v) for k, v in attributes.items()):
                matched.append(path)
        if self.locked:
            return dbus.Array([], signature="o"), dbus.Array(matched, signature="o")
        return dbus.Array(matched, signature="o"), dbus.Array([], signature="o")

    @dbus.service.method(SVC, in_signature="", out_signature="")
    def Lock(self):
        self.locked = True

    @dbus.service.method(SVC, in_signature="", out_signature="")
    def Unlock(self):
        self.locked = False
        self._reload()


def serve(bus_address: str, vault):
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.bus.BusConnection(bus_address)
    loop = GLib.MainLoop()
    service = SecretService(bus, vault)
    thread = threading.Thread(target=loop.run, daemon=True)
    thread.start()
    service.loop = loop
    return service, thread
