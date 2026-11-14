"""
Procesos y canales: fork para los workers y un pipe entre hilos con la misma
interfaz (para el modo de un solo proceso).
"""

import multiprocessing
import threading

from collections import deque


# fork explicito: los workers heredan el hidraw abierto y el estado del daemon
# (python 3.14 cambia el metodo por defecto a forkserver)
_MP = multiprocessing.get_context("fork")
Process = _MP.Process
Queue   = _MP.Queue
Pipe    = _MP.Pipe


class LocalConn(object):
    """extremo de un pipe entre hilos con la interfaz de multiprocessing.Connection."""

    def __init__(self, inbox, outbox, cond):
        self.inbox = inbox
        self.outbox = outbox
        self.cond = cond

    def send(self, obj):
        with self.cond:
            self.outbox.append(obj)
            self.cond.notify_all()

    def poll(self, timeout=0.0):
        with self.cond:
            if self.inbox:
                return True
            if timeout:
                self.cond.wait(timeout)
            return bool(self.inbox)

    def recv(self):
        with self.cond:
            while not self.inbox:
                self.cond.wait()
            return self.inbox.popleft()

    def close(self):
        pass


def local_pipe():
    a, b = deque(), deque()
    cond = threading.Condition()
    return LocalConn(a, b, cond), LocalConn(b, a, cond)
