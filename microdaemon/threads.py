import threading
import random

from . import common

class WhileTrueThread(threading.Thread):
    def run(self):
        common.log("%s running" % self.name)
        while True:
            self._target(*self._args,**self._kwargs)
            #func(*args,**kwargs)

class WaitWhileTrueThread(threading.Thread):
    def __init__(self,timeout,**kwargs):
        threading.Thread.__init__(self,**kwargs)
        self._timeout=timeout

    def run(self):
        common.log("%s running" % self.name)
        while True:
            self._target(*self._args,**self._kwargs)
            ev=threading.Event()
            ev.clear()
            ev.wait(self._timeout)

class WaitRandomStartThread(threading.Thread):
    def __init__(self,timeout,**kwargs):
        threading.Thread.__init__(self,**kwargs)
        self._timeout=timeout

    def run(self):
        common.log("%s running" % self.name)
        delay=random.uniform(0,self._timeout)
        ev=threading.Event()
        ev.clear()
        ev.wait(delay)
        while True:
            self._target(*self._args,**self._kwargs)
            ev=threading.Event()
            ev.clear()
            ev.wait(self._timeout)
