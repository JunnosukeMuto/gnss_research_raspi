import threading
import queue

def main():
    que1 = queue.Queue()
    que2 = queue.Queue()
    
    stop = threading.Event()

    threads = [
        threading.Thread()
    ]

    pass

if __name__ == "__main__":
    main()