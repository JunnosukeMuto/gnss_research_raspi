import os
import threading
import queue
from typing import Any

from dotenv import load_dotenv

from i2c_thread import i2c_thread
from nmea_thread import nmea_thread
from ntrip_thread import ntrip_thread
from uart_thread import uart_thread

load_dotenv()


def main():
    que_i2c_nmea = queue.Queue()
    que_nmea_out = queue.Queue()
    que_ntrip_uart = queue.Queue()
    
    stop = threading.Event()
    
    i2c_path = os.getenv("I2C_PATH_PROD")
    i2c_addr = int(os.getenv("I2C_ADDR"), 16)
    uart_path = str(os.getenv("UART_PATH_PROD"))

    # まずI2CスレッドとNMEAパーススレッドだけ開始
    threads = [
        threading.Thread(target=i2c_thread, args=(que_i2c_nmea, stop, i2c_path, i2c_addr)),
        threading.Thread(target=nmea_thread, args=(que_i2c_nmea, que_nmea_out, stop)),
    ]

    for t in threads:
        t.start()


    try:

        # まず大まかな緯度経度を取得する
        while True:
            try:
                d: dict[str, Any] = que_nmea_out.get(timeout=1)
                print(d)
                break

            except queue.Empty:
                pass


        lat_init = float(d['lat'])
        lon_init = float(d['lon'])

        # ntripスレッドとuartでRTCMを送るスレッド開始
        t1 = threading.Thread(target=ntrip_thread, args=(lat_init, lon_init, que_ntrip_uart, stop))
        t2 = threading.Thread(target=uart_thread, args=(que_ntrip_uart, stop, uart_path))
        t1.start()
        t2.start()
        threads.append(t1)
        threads.append(t2)

        # システムPythonで動くbluetoothスレッドにAF_UNIXソケットで送信
        while True:
            try:
                d: dict[str, Any] = que_nmea_out.get(timeout=1)
                print(d)

            except queue.Empty:
                pass
        

    except KeyboardInterrupt:
        pass

    except ValueError:
        print('value error')
        pass

    finally:
        stop.set()
        for t in threads:
            t.join()


if __name__ == "__main__":
    main()