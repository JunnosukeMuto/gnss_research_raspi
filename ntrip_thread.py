import threading
import queue
import os
import traceback
import requests
import math
import time
from dotenv import load_dotenv

load_dotenv()

NTRIP_HOST = str(os.getenv("NTRIP_HOST"))
NTRIP_PORT = int(os.getenv("NTRIP_PORT"))
NTRIP_USER = str(os.getenv("NTRIP_USER"))
NTRIP_PASS = str(os.getenv("NTRIP_PASS"))

MP_IDX = 1
LAT_IDX = 9
LON_IDX = 10


def ntrip_thread(lat: float, lon: float, que: queue.Queue, stop: threading.Event):

    try:
        res = requests.get(
            url=NTRIP_HOST,
            auth=(NTRIP_USER, NTRIP_PASS),
            headers={"Ntrip-Version" : "Ntrip/2.0"},
            timeout=10.0
            )
        
        # print(res.text)
        lines = res.text.splitlines()
        table: list[list[str]] = []

        for l in lines:
            cols = l.split(';')
            if len(cols) != 0 and cols[0] == "STR":
                table.append(cols)

        # print(table)
        min_dist: float = float('inf')
        min_dist_idx: int = 0

        # ユークリッド距離で最も近いキャスターを求める
        for i, record in enumerate(table):
            _lat = float(record[LAT_IDX])
            _lon = float(record[LON_IDX])
            dist = math.sqrt((lat - _lat) ** 2 + (lon - _lon) ** 2)
            if (dist < min_dist):
                min_dist = dist
                min_dist_idx = i

        mountpoint = table[min_dist_idx][MP_IDX]

        # print(f"mount point: {mountpoint}")
        # print("connecting...")
            
        with requests.get(
            url=f"{NTRIP_HOST}/{mountpoint}",
            auth=(NTRIP_USER, NTRIP_PASS),
            headers={
                "Ntrip-Version" : "Ntrip/2.0",
                "User-Agent": "NTRIP client"
                },
            stream=True,
            ) as r:

            r.raise_for_status()

            # print("connected!")
            # print("=================================")

            for chunk in r.iter_content(chunk_size=None):
                if stop.is_set():
                    break

                if not chunk:
                    continue

                try:
                    que.put(chunk)
                except queue.Full:
                    pass

    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    lat = 32.48
    lon = 130.60
    que = queue.Queue()
    stop = threading.Event()

    bytesps = 0
    last = time.time()

    t = threading.Thread(target=ntrip_thread, args=(lat, lon, que, stop))
    t.start()

    try:
        while True:
            chunk: bytes = que.get()
            bytesps += len(chunk)
            now = time.time()

            if now - last >= 1.0:
                print(f"RTCM: {bytesps} bytes/s")
                print(f"qsize: {que.qsize()}")
                bytesps = 0
                last = now

    except KeyboardInterrupt:
        stop.set()
        t.join()