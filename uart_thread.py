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

    ###############
    # cfmakeraw() 
    ###############

    # 消したいフラグだけ消し、立てたいフラグだけ立て、残りはfdのデフォルトに任せる
    iflag = attrs[0]
    oflag = attrs[1]
    cflag = attrs[2]
    lflag = attrs[3]
    ispeed = attrs[4]
    ospeed = attrs[5]
    cc = attrs[6]

    iflag &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP
               | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON)
    oflag &= ~termios.OPOST
    lflag &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
    cflag &= ~(termios.CSIZE | termios.PARENB)
    cflag |= termios.CS8

    ######################
    # GPS-RTK2ボード用設定
    ######################

    # no parity bit, 1 stop bit
    cflag &= ~(termios.PARENB | termios.CSTOPB)

    # 受信有効、モデム制御線無視
    cflag |= termios.CREAD | termios.CLOCAL

    # 38400 baud
    ispeed = termios.B38400
    ospeed = termios.B38400

    ########################

    new_attrs = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
    termios.tcsetattr(fd, termios.TCSANOW, new_attrs)

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