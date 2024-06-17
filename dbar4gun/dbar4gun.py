import info

from multiprocessing import Process, Queue

from device  import WiiMoteDevice
from monitor import Monitor

def monitor_handle_events(queue):
    while 1:
        event = queue.get()
        if event == "remove":
            pass
        else:
            pass

        print("monitor: {} {}".format(*event))

if __name__ == '__main__':
    print("{} v{}".format(info.__title__,  info.__version__))

    monitor       = Monitor(queue = Queue())

    monitor_event_process = Process(
            target=monitor_handle_events, args=(monitor.queue,))

    monitor_event_process.start()

    monitor.run()
