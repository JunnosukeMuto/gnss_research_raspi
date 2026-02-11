#!/usr/bin/python3

# https://www.bluetooth.com/specifications/specs/core-specification-6-0/
# https://github.com/bluez/bluez/blob/master/test/example-gatt-server
# https://github.com/bluez/bluez/blob/master/test/example-advertisement
# https://dbus.freedesktop.org/doc/dbus-specification.html
# https://dbus.freedesktop.org/doc/dbus-python/index.html
# https://pygobject.gnome.org/

import os
import signal
import socket
import sys
import traceback
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
LE_AD_IFACE         = "org.bluez.LEAdvertisement1"
LE_AD_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
DBUS_OM_IFACE       = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE     = "org.freedesktop.DBus.Properties"

APP_PATH            = "/com/example/gnssresearch"
AD_PATH             = "/com/example/gnssresearch/advertisement"
AD_LOCAL_NAME       = "gnss-research"
POS_SERVICE_PATH    = "/com/example/gnssresearch/position/service0"
POS_SERVICE_UUID    = "70787d4e-af36-4bfb-901b-37133b5191bb"
POS_CHRC_PATH       = "/com/example/gnssresearch/position/service0/char0"
POS_CHRC_UUID       = "0b53a515-bf15-44c8-a814-516de5f8a613"

MTU_PAYLOAD_MAX_LEN = 20

SOCK_PATH           = "/run/gnss-research/ble.sock"


####################################
# Gatt Exceptions
####################################


class InvalidArgsException(dbus.exceptions.DBusException):
    _dbus_error_name = 'org.freedesktop.DBus.Error.InvalidArgs'


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
        self.path = dbus.ObjectPath(path)
        self.conn = conn
        self.uuid = uuid
        self.service_path = dbus.ObjectPath(service_path)
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
                'UUID': dbus.String(self.uuid),
                'Flags': dbus.Array(['notify'], signature='s'),
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

    @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface: str):
        if not interface in self.get_properties():
            raise InvalidArgsException()
        
        return self.get_properties()[interface]
    
    @dbus.service.method(DBUS_PROP_IFACE, in_signature='ss', out_signature='v')
    def Get(self, interface: str, property: str):
        props = self.get_properties()
        if interface in props and property in props[interface]:
            return props[interface][property]
        
        raise InvalidArgsException()
        

class GattService(dbus.service.Object):
    """
    https://github.com/bluez/bluez/blob/master/doc/org.bluez.GattService.rst
    """

    def __init__(self, conn: dbus.connection.Connection, path: str, uuid: str, primary: bool):
        self.path = dbus.ObjectPath(path)
        self.conn = conn
        self.uuid = uuid
        self.primary = primary
        self.characteristics: list[GattCharacteristic] = []
        super().__init__(conn, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                'UUID': dbus.String(self.uuid),
                'Primary': dbus.Boolean(self.primary),
                'Includes': dbus.Array([], signature='o'),
            }
        }
    
    def add_chrcs(self, chrcs: list[GattCharacteristic]):
        self.characteristics.extend(chrcs)

    def get_characteristic_paths(self):
        result = []
        for chrc in self.characteristics:
            result.append(chrc.path)
        return result
    
    @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface: str):
        if not interface in self.get_properties():
            raise InvalidArgsException()
        
        return self.get_properties()[interface]
    
    @dbus.service.method(DBUS_PROP_IFACE, in_signature='ss', out_signature='v')
    def Get(self, interface: str, property: str):
        props = self.get_properties()
        if interface in props and property in props[interface]:
            return props[interface][property]
        
        raise InvalidArgsException()


class Application(dbus.service.Object):
    """
    the standard DBus.ObjectManager interface must be available on the root service path
    """

    def __init__(self, conn: dbus.connection.Connection, path: str, services: list[GattService]):
        self.path = dbus.ObjectPath(path)
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
# LE Advertising
####################################
    

class Advertisement(dbus.service.Object):
    """
    https://github.com/bluez/bluez/blob/master/doc/org.bluez.LEAdvertisement.rst
    """

    def __init__(self, conn: dbus.connection.Connection, path: str, service_uuids: list[str], local_name: str):
        self.path = dbus.ObjectPath(path)
        self.service_uuids = service_uuids
        self.local_name = local_name
        super().__init__(conn, self.path)

    def get_properties(self):
        return {
            LE_AD_IFACE: {
                'Type': dbus.String('peripheral'),
                'ServiceUUIDs': dbus.Array(self.service_uuids, signature='s'),
                'LocalName': dbus.String(self.local_name),
            }
        }
    
    @dbus.service.method(LE_AD_IFACE, in_signature='', out_signature='')
    def Release(self):
        pass
    
    @dbus.service.method(DBUS_PROP_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface: str):
        if not interface in self.get_properties():
            raise InvalidArgsException()
        
        return self.get_properties()[interface]
    
    @dbus.service.method(DBUS_PROP_IFACE, in_signature='ss', out_signature='v')
    def Get(self, interface: str, property: str):
        props = self.get_properties()
        if interface in props and property in props[interface]:
            return props[interface][property]
        
        raise InvalidArgsException()


####################################
# Main loop
####################################


def main():
    signal.signal(signal.SIGTERM, handle_sigterm)

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # https://www.bluez.org/bluez-5-api-introduction-and-porting-guide/
    # org.bluezのルートオブジェクトはObjectManager
    bluez_root_obj = bus.get_object(BLUEZ_NAME, '/')
    bluez_om = dbus.Interface(bluez_root_obj, DBUS_OM_IFACE)
    
    # org.bluezの公開するオブジェクトからGattManager1、LEAdvertisingManager1を見つける
    bluez_obj_tree = bluez_om.GetManagedObjects()
    
    found_gm: dbus.proxies.ProxyObject | None = None
    found_am: dbus.proxies.ProxyObject | None = None

    for o_path, iface_dict in bluez_obj_tree.items():
        if GATT_MANAGER_IFACE in iface_dict.keys():
            found_gm = bus.get_object(BLUEZ_NAME, o_path)
        if LE_AD_MANAGER_IFACE in iface_dict.keys():
            found_am = bus.get_object(BLUEZ_NAME, o_path)

    if not found_gm:
        print(f"{GATT_MANAGER_IFACE} interface not found")
        return
    
    if not found_am:
        print(f"{LE_AD_MANAGER_IFACE} interface not found")
        return
    
    # 発見
    gm = dbus.Interface(found_gm, GATT_MANAGER_IFACE)
    am = dbus.Interface(found_am, LE_AD_MANAGER_IFACE)

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

    # Register
    app = Application(bus, APP_PATH, [srv])
    ad = Advertisement(bus, AD_PATH, [POS_SERVICE_UUID], AD_LOCAL_NAME)

    try:
        gm.RegisterApplication(app.path, {})
        am.RegisterAdvertisement(ad.path, {})
    except dbus.exceptions.DBusException as e:
        print(e)
        return

    # メインループ
    try:
        loop = GLib.MainLoop()
        loop.run()

    except KeyboardInterrupt:
        pass

    except SystemExit:
        pass

    except Exception:
        traceback.print_exc()

    finally:
        am.UnregisterAdvertisement(ad.path)
        dbus.service.Object.remove_from_connection(ad.path)


def handle_sigterm(signum, frame):
    sys.exit(0)


if __name__ == "__main__":
    main()