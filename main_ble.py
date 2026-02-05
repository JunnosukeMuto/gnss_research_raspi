#!/usr/bin/python3

# https://github.com/bluez/bluez/blob/master/test/example-gatt-server

import os
import socket
from typing import Any
from gi.repository import GLib

import dbus
import dbus.connection
import dbus.proxies
import dbus.service
import dbus.mainloop.glib


BLUEZ_NAME          = "org.bluez"
GATT_MANAGER_IFACE  = "org.bluez.GattManager1"
GATT_SERVICE_IFACE  = "org.bluez.GattService1"
GATT_CHRC_IFACE     = "org.bluez.GattCharacteristic1"
DBUS_OM_IFACE       = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE     = "org.freedesktop.DBus.Properties"

APP_PATH            = "/com/example/gnss-research"
POS_SERVICE_PATH    = "/com/example/gnss-research/position/service0"
POS_SERVICE_UUID    = "70787d4e-af36-4bfb-901b-37133b5191bb"
POS_CHRC_PATH       = "/com/example/gnss-research/position/service0/char0"
POS_CHRC_UUID       = "0b53a515-bf15-44c8-a814-516de5f8a613"

MTU_PAYLOAD_MAX_LEN = 20

SOCK_PATH           = "/run/gnss-research/ble.sock"


####################################
# Interface
####################################

class ObjectManager(dbus.Interface):

    def __init__(self, object: dbus.proxies.ProxyObject):
        super().__init__(object, DBUS_OM_IFACE)

    def GetManagedObjects(self) -> dict[str, dict[str, dict[str, Any]]]:
        objs = super().GetManagedObjects()
        if type(objs) != dict[str, dict[str, dict[str, Any]]]:
            raise TypeError
        
        return objs
    

class GattManager(dbus.Interface):
    """
    https://github.com/bluez/bluez/blob/master/doc/org.bluez.GattManager.rst
    """

    def __init__(self, object: dbus.proxies.ProxyObject):
        super().__init__(object, GATT_MANAGER_IFACE)

    def RegisterApplication(self, application: str, options: dict = {}):
        super().RegisterApplication(application, options)


####################################
# Gatt Exceptions
####################################

class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = 'org.bluez.Error.NotSupported'


####################################
# Gatt Object Tree
####################################


class GattCharacteristic(dbus.service.Object):
    """
    https://github.com/bluez/bluez/blob/master/doc/org.bluez.GattCharacteristic.rst
    """
    
    def __init__(self, conn: dbus.connection.Connection, path: str, uuid: str, service_path: str, soc_dgram: socket.socket):
        self.path = path
        self.conn = conn
        self.uuid = uuid
        self.service_path = service_path
        self.soc = soc_dgram

        self.notifying = False
        self.value: bytes = b''

        # 保持しないとGCでwatchが消える恐れあり
        self._io_watch_id = GLib.io_add_watch(
            self.soc,
            GLib.IO_IN,
            self._on_socket_readable
        )

        super().__init__(conn, self.path)

    # No Descriptors, notify only
    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                'Service': self.service_path,
                'UUID': self.uuid,
                'Flags': ['notify'],
            }
        }
    
    def notify_value(self):
        if self.notifying:
            # yはuint8なので1バイト、ayはバイト列になる
            self.PropertiesChanged(
                GATT_CHRC_IFACE,
                {'Value': dbus.Array(self.value, signature='y')},
                []
            )
    
    def _on_socket_readable(self, source, condition):
        try:
            data = self.soc.recv(MTU_PAYLOAD_MAX_LEN)
        except BlockingIOError:
            return True
        
        self.value = data
        self.notify_value()

        return True
        
    @dbus.service.method(GATT_CHRC_IFACE, in_signature='', out_signature='')
    def StartNotify(self):
        self.notifying = True
        self.notify_value()     # 即Notify（ベストプラクティス）

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='', out_signature='')
    def StopNotify(self):
        self.notifying = False

    @dbus.service.signal(DBUS_PROP_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, interface: str, changed: dict[str, Any], invalidated: list[str]):
        pass
        

class GattService(dbus.service.Object):
    """
    https://github.com/bluez/bluez/blob/master/doc/org.bluez.GattService.rst
    """

    def __init__(self, conn: dbus.connection.Connection, path: str, uuid: str, primary: bool):
        self.path = path
        self.conn = conn
        self.uuid = uuid
        self.primary = primary
        self.characteristics: list[GattCharacteristic] = []
        super().__init__(conn, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                'UUID': self.uuid,
                'Primary': self.primary,
                'Characteristics': dbus.Array(
                        self.get_characteristic_paths(),
                        signature='o')
            }
        }
    
    def add_chrcs(self, chrcs: list[GattCharacteristic]):
        self.characteristics.extend(chrcs)

    def get_characteristic_paths(self):
        result = []
        for chrc in self.characteristics:
            result.append(chrc.path)
        return result


class Application(dbus.service.Object):
    """
    the standard DBus.ObjectManager interface must be available on the root service path
    """

    def __init__(self, conn: dbus.connection.Connection, object_path: str, services: list[GattService]):
        self.path = object_path
        self.conn = conn
        self.services: list[GattService] = services
        super().__init__(conn, self.path)

    @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        objs = {}

        for srv in self.services:
            objs[srv.path] = srv.get_properties()
            for c in srv.characteristics:
                objs[c.path] = c.get_properties()

        return objs


####################################
# Main loop
####################################


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()

    # https://www.bluez.org/bluez-5-api-introduction-and-porting-guide/
    # org.bluezのルートオブジェクトはObjectManager
    bluez_root_obj = bus.get_object(BLUEZ_NAME, '/')
    bluez_om = ObjectManager(bluez_root_obj)
    
    # org.bluezの公開するオブジェクトの中にGattManager1を実装したものがないか見つける
    bluez_obj_tree = bluez_om.GetManagedObjects()
    
    found: dbus.proxies.ProxyObject | None = None

    for o_path, iface_dict in bluez_obj_tree.items():
        if GATT_MANAGER_IFACE in iface_dict.keys():
            found = bus.get_object(BLUEZ_NAME, o_path)

    if not found:
        print("GattManager1 interface not found")
        return
    
    # GattManager1を発見
    gm = GattManager(found)

    # gnssサービスと通信するUNIXドメインソケット
    if os.path.exists(SOCK_PATH):
        os.unlink(SOCK_PATH)
    soc = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    soc.bind((SOCK_PATH))
    soc.setblocking(False)
    
    # GattServiceの後にGattCharacteristicをインスタンス化すること（export順）
    srv = GattService(bus, POS_SERVICE_PATH, POS_SERVICE_UUID, True)
    chrc = GattCharacteristic(bus, POS_CHRC_PATH, POS_CHRC_UUID, POS_SERVICE_PATH, soc)
    srv.add_chrcs([chrc])

    # 自プロセス(= D-Bus service)のこのパス以下にGATTオブジェクトがあると登録
    app = Application(bus, APP_PATH, [srv])

    try:
        gm.RegisterApplication(app.path)
    except dbus.exceptions.DBusException as e:
        print(e)
        return

    # メインループ
    loop = GLib.MainLoop()
    loop.run()


if __name__ == "__main__":
    main()