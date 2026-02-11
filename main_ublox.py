import csv
from datetime import datetime
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import threading
import queue
import traceback
from typing import Any

from dotenv import load_dotenv

from i2c_thread import i2c_thread
from nmea_thread import nmea_thread
from ntrip_thread import ntrip_thread
from uart_thread import uart_thread

load_dotenv()

DEBUG_UBLOX = False


def getenv(key: str, path: bool = False) -> str:
    val = os.getenv(key)
    if val == None:
        raise ValueError()
    if path and not os.path.exists(val) and not DEBUG_UBLOX:
        raise FileNotFoundError()
    return val


try:
    if (os.getenv("DEBUG_UBLOX")):
        DEBUG_UBLOX = True

    NTRIP_URL = getenv("NTRIP_URL")
    NTRIP_USER = getenv("NTRIP_USER")
    NTRIP_PASS = getenv("NTRIP_PASS")

    I2C_PATH = getenv("I2C_PATH_PROD", path=True)
    I2C_ADDR = int(getenv("I2C_ADDR"), 16)
    UART_PATH = getenv("UART_PATH_PROD", path=True)

    LOGDIR = Path(getenv("LOGDIR", path=True)) / "ublox/"
    SOCK_PATH = getenv("SOCK_PATH", path=True)

except Exception as e:
    print(e)
    sys.exit(1)


if DEBUG_UBLOX:
    LOGDIR = Path("/tmp")


def main():
    signal.signal(signal.SIGTERM, handle_sigterm)

    que_i2c_nmea = queue.Queue()
    que_nmea_out = queue.Queue()
    que_ntrip_uart = queue.Queue()

    stop = threading.Event()

    # まずI2CスレッドとNMEAパーススレッドだけ開始
    print("Starting I2C thread and NMEA thread...")

    threads = [
        threading.Thread(target=i2c_thread, args=(que_i2c_nmea, stop, I2C_PATH, I2C_ADDR)),
        threading.Thread(target=nmea_thread, args=(que_i2c_nmea, que_nmea_out, stop)),
    ]

    for t in threads:
        t.start()


    print("Acquiring non-RTK position...")

    try:
        # まず大まかな緯度経度を取得する
        while True:
            try:
                d: dict[str, Any] = que_nmea_out.get(timeout=1)
                break

            except queue.Empty:
                pass


        lat_init = float(d['lat'])
        lon_init = float(d['lon'])


        # ntripスレッドとuartでRTCMを送るスレッド開始
        print(d)
        print("Starting NTRIP thread and UART thread...")

        t1 = threading.Thread(target=ntrip_thread, args=(que_ntrip_uart, stop, lat_init, lon_init, NTRIP_URL, NTRIP_USER, NTRIP_PASS))
        t2 = threading.Thread(target=uart_thread, args=(que_ntrip_uart, stop, UART_PATH))
        t1.start()
        t2.start()
        threads.append(t1)
        threads.append(t2)


        # ログファイルとBLEサービスに接続
        print("Connecting to /var/log/ and ble deamon...")

        logfile = LOGDIR / f"{datetime.now().isoformat()}.csv"

        with logfile.open('a') as f, \
             socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:

            writer = csv.DictWriter(f, ['seq', 'lat', 'lon', 'alt', 'quality'])
            writer.writeheader()

            # クライアントとして接続
            if not DEBUG_UBLOX:
                s.connect((SOCK_PATH))

            # RTK測位データの取得開始
            print("Acquiring RTK position data...")

            while True:
                try:
                    d: dict[str, Any] = que_nmea_out.get(timeout=1)
                    if type(d) is not dict:
                        continue
                    
                    # CSVログ出力
                    writer.writerow(d)

                    # UNIXドメインソケットでデータ送出
                    payload = struct.pack(
                        "<HBiii",               # リトルエンディアン,ushort,uchar,int,int,int
                        d["seq"] & 0xFFFF,      # 2byteでマスク（超過で例外）
                        d["quality"] & 0xFF,    # 1byte
                        int(d["lat"] * 1e7),
                        int(d["lon"] * 1e7),    # 180e7 < 2147483648
                        int(d["alt"] * 1e3),    # m -> mm
                    )
                    
                    if not DEBUG_UBLOX:
                        s.sendall(payload)
                    else:
                        print(d)

                except queue.Empty:
                    pass
        

    except KeyboardInterrupt:
        pass

    except SystemExit:
        pass

    except Exception:
        traceback.print_exc()

    finally:
        print('Gracefully finishing...')
        stop.set()
        for t in threads:
            t.join()


def handle_sigterm(signum, frame):
    sys.exit(0)


if __name__ == "__main__":
    main()