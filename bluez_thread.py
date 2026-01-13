#!/usr/bin/env python3
import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib
import threading
import time

BLUEZ_SERVICE_NAME = "org.bluez"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"

DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"

GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
CHAR_UUID    = "abcdef01-1234-5678-1234-56789abcdef0"

# ---------------- Application ----------------

class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = "/org/bluez/example/app"
        self.services = []
        super().__init__(bus, self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE,
                         out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.path] = service.get_properties()
            for chrc in service.characteristics:
                response[chrc.path] = chrc.get_properties()
        return response

# ---------------- Service ----------------

class Service(dbus.service.Object):
    def __init__(self, bus, index):
        self.path = f"/org/bluez/example/service{index}"
        self.bus = bus
        self.uuid = SERVICE_UUID
        self.primary = True
        self.characteristics = []
        super().__init__(bus, self.path)

    def add_characteristic(self, chrc):
        self.characteristics.append(chrc)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                "UUID": self.uuid,
                "Primary": self.primary,
                "Characteristics": dbus.Array(
                    [chrc.path for chrc in self.characteristics],
                    signature="o"
                )
            }
        }

# ---------------- Characteristic ----------------

class NotifyCharacteristic(dbus.service.Object):
    def __init__(self, bus, index, service):
        self.path = f"{service.path}/char{index}"
        self.bus = bus
        self.uuid = CHAR_UUID
        self.service = service
        self.flags = ["notify"]
        self.notifying = False
        super().__init__(bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                "UUID": self.uuid,
                "Service": self.service.path,
                "Flags": self.flags,
            }
        }

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        self.notifying = True

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        self.notifying = False

    def notify(self, text):
        if not self.notifying:
            return
        value = dbus.Array([dbus.Byte(c) for c in text.encode()],
                           signature="y")
        self.PropertiesChanged(
            GATT_CHRC_IFACE,
            {"Value": value},
            []
        )

    @dbus.service.signal(DBUS_PROP_IFACE,
                          signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

# ---------------- Advertisement ----------------

class Advertisement(dbus.service.Object):
    def __init__(self, bus, index):
        self.path = f"/org/bluez/example/advertisement{index}"
        self.bus = bus
        self.service_uuids = [SERVICE_UUID]
        self.local_name = "RPi-BLE"
        super().__init__(bus, self.path)

    def get_properties(self):
        return {
            LE_ADVERTISEMENT_IFACE: {
                "Type": "peripheral",
                "ServiceUUIDs": self.service_uuids,
                "LocalName": self.local_name,
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature="s",
                         out_signature="a{sv}")
    def GetAll(self, interface):
        return self.get_properties()[interface]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE)
    def Release(self):
        pass

# ---------------- Main ----------------

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter = bus.get_object(BLUEZ_SERVICE_NAME, "/org/bluez/hci0")

    app = Application(bus)
    service = Service(bus, 0)
    chrc = NotifyCharacteristic(bus, 0, service)
    service.add_characteristic(chrc)
    app.add_service(service)

    gatt_mgr = dbus.Interface(adapter, GATT_MANAGER_IFACE)
    gatt_mgr.RegisterApplication(app.path, {},
        reply_handler=lambda: None,
        error_handler=lambda e: print(e)
    )

    adv = Advertisement(bus, 0)
    adv_mgr = dbus.Interface(adapter, LE_ADVERTISING_MANAGER_IFACE)
    adv_mgr.RegisterAdvertisement(adv.path, {},
        reply_handler=lambda: None,
        error_handler=lambda e: print(e)
    )

    def notify_loop():
        while True:
            chrc.notify("hello")
            time.sleep(1)

    threading.Thread(target=notify_loop, daemon=True).start()

    GLib.MainLoop().run()

if __name__ == "__main__":
    main()
