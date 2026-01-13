import fcntl
import select
import threading
import queue
import os
import traceback

from dotenv import load_dotenv


I2C_SLAVE = 0x0703  # linux/i2c-dev.h
READ_SIZE = 256


def i2c_thread(que: queue.Queue, stop: threading.Event, i2c_path: str, i2c_addr: int, debug: bool = False):

    try:
        fd = os.open(i2c_path, os.O_RDWR)

        if not debug:
            fcntl.ioctl(fd, I2C_SLAVE, i2c_addr)

        while not stop.is_set():
            r, w, e = select.select([fd], [], [], 0.5)  # read()のブロック防止

            if not r:
                continue

            data = os.read(fd, READ_SIZE)

            if all(b == 0xFF for b in data):
                continue

            try:
                que.put(data, timeout=0.5)
            except queue.Full:
                pass

    except Exception:
        traceback.print_exc()

    finally:
        if fd is not None:
            os.close(fd)


if __name__ == "__main__":
    que = queue.Queue()
    stop = threading.Event()

    load_dotenv()
    i2c_path = os.getenv("I2C_PATH_DEV")
    i2c_addr = int(os.getenv("I2C_ADDR"), 16)

    t = threading.Thread(target=i2c_thread, args=(que, stop, i2c_path, i2c_addr, True))
    t.start()

    try:
        while True:
            try:
                nmea: str = que.get(timeout=1)
                print(nmea)
            except queue.Empty:
                pass

    except KeyboardInterrupt:
        stop.set()
        t.join()