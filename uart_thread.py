import threading
import queue
import os
import termios
import time
import traceback

from dotenv import load_dotenv

from ntrip_thread import ntrip_thread


def uart_thread(que: queue.Queue, stop: threading.Event, uart_path: str, debug: bool = False):

    fd = os.open(uart_path, os.O_RDWR | os.O_NOCTTY)

    attrs = termios.tcgetattr(fd)

    attrs[0] &= ~(termios.IXON | termios.IXOFF | termios.IXANY)
    attrs[1] &= ~(termios.OPOST)

    attrs[2] &= ~termios.PARENB
    attrs[2] &= ~termios.CSTOPB
    attrs[2] &= ~termios.CSIZE
    attrs[2] |= termios.CS8
    attrs[2] |= termios.CREAD | termios.CLOCAL

    attrs[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG)

    attrs[4] = termios.B38400
    attrs[5] = termios.B38400

    termios.tcsetattr(fd, termios.TCSANOW, attrs)

    try:
        while not stop.is_set():
            try:
                chunk: bytes = que.get(timeout=0.5)
            except queue.Empty:
                continue

            os.write(fd, chunk)

            if debug:
                with open("uart_dump.bin", "ab") as f:
                    f.write(chunk)

    except Exception:
        traceback.print_exc()
    
    finally:
        os.close(fd)


if __name__ == "__main__":
    lat = 32.48
    lon = 130.60
    que = queue.Queue()
    stop = threading.Event()

    bytesps = 0
    last = time.time()

    load_dotenv()
    uart_path = str(os.getenv("UART_PATH_DEV"))

    t1 = threading.Thread(target=ntrip_thread, args=(lat, lon, que, stop))
    t2 = threading.Thread(target=uart_thread, args=(que, stop, uart_path, True))
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        stop.set()
        t1.join()
        t2.join()