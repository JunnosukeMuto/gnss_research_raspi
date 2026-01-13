import fcntl
import select
import threading
import queue
import os
import traceback
from typing import Any

from dotenv import load_dotenv

from i2c_thread import i2c_thread


def nmea_thread(que_in: queue.Queue, que_out: queue.Queue, stop: threading.Event):

    try:
        buf = bytearray()
        seq = 0

        while not stop.is_set():
            try:
                data: bytes = que_in.get(timeout=0.5)
            except queue.Empty:
                continue

            buf.extend(data)

            ##########################
            # ストリームから文境界を出す
            ##########################

            start = buf.find(b'$')

            # 開始文字が来るまでは破棄して待機
            if start == -1:
                buf.clear()
                continue

            # 開始文字以前は破棄
            elif start > 0:
                del buf[:start]

            end = buf.find(b'\r\n')

            # 終了文字が来るまでバッファを伸ばす
            if end == -1:
                continue

            # NMEA文の完成、バッファから削除
            sentence = bytes(buf[:end + 2])
            del buf[:end + 2]

            ##################################
            # デコード, チェックサム検証、パース
            ##################################

            try:
                decoded: str = sentence.decode("ascii").strip().strip('$')
            except UnicodeDecodeError:
                print('UnicodeDecodeError')
                continue

            # チェックサム分離
            if '*' in decoded:
                body, checksum_str = decoded.split('*', 1)
            else:
                print('checksum does not exist')
                continue

            # チェックサム検証
            checksum = int(checksum_str, 16)
            xor_sum: int = 0
            for c in body:
                xor_sum ^= ord(c)
            if checksum != xor_sum:
                print('checksum is not valid')
                print(f"body: {body}")
                print(f"checksum: {checksum}")
                print(f"actual checksum: {xor_sum}")
                continue

            fields: list[str] = body.split(',')

            # Sentence formatter検出、加工
            talker_id = fields[0][:2]
            fmt = fields[0][2:]
            if not talker_id in ['GP', 'GL', 'GA', 'GB', 'QZ', 'GN']:
                continue

            d: dict[str, Any] = {}

            if fmt == "GGA" and not len(fields) < 9:
                d['lat'] = dm2dd(fields[2], fields[3])
                d['lon'] = dm2dd(fields[4], fields[5])
                d['alt'] = float_nl(fields[9])
                d['fix'] = int_nl(fields[6])
            else:
                continue

            # シーケンス番号をつける
            d['seq'] = seq
            seq += 1

            # 送信
            try:
                que_out.put(d, timeout=0.5)
            except queue.Full:
                continue


    except Exception:
        traceback.print_exc()


def int_nl(x: str) -> float | None:

    try:
        val = int(x)
    except ValueError:
        return None
    return val


def float_nl(x: str) -> float | None:

    try:
        val = float(x)
    except ValueError:
        return None
    return val


# (d)ddmm.mmmmm -> (d)dd.ddddd
# convert degree-minutes notation to decimal degrees notation
def dm2dd(value: str | None, direction: str | None) -> float | None:

    if not value or not direction:
        return None
    
    try:
        raw = float(value)
    except ValueError:
        return None

    deg = int(raw // 100)
    min = raw % 100

    decimal = deg + min / 60.0

    if direction in ['S', 'W']:
        decimal = -decimal

    return decimal


if __name__ == "__main__":
    que_in = queue.Queue()
    que_out = queue.Queue()
    stop = threading.Event()

    load_dotenv()
    i2c_path = os.getenv("I2C_PATH_DEV")
    i2c_addr = int(os.getenv("I2C_ADDR"), 16)

    t1 = threading.Thread(target=i2c_thread, args=(que_in, stop, i2c_path, i2c_addr, True))
    t2 = threading.Thread(target=nmea_thread, args=(que_in, que_out, stop))
    t1.start()
    t2.start()

    try:
        while True:
            try:
                d: dict[str, Any] = que_out.get(timeout=1)
                print(d)
            except queue.Empty:
                pass

    except KeyboardInterrupt:
        stop.set()
        t1.join()
        t2.join()