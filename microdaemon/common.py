import os.path
import random
import string
import datetime
import re
import socket
import time
import json
import collections
import pytz
import numpy
import pandas
import importlib
import logging
import threading

from . import config

## ok
class Sequence(object):
    def __init__(self):
        self._num=-1

    def __call__(self): 
        self._num+=1
        return self._num


class SerializedSequence(Sequence):
    def __init__(self,name): 
        Sequence.__init__(self)
        self._name=name
        self._fname=os.path.join(config.SEQUENCES_DIR,self._name)

    def _read(self):
        if not os.path.exists(self._fname): 
            return
        with open(self._fname,"r") as fd:
            self._num=int(fd.read().strip())

    def _write(self):
        dname=os.path.dirname(self._fname)
        if not os.path.isdir(dname):
            os.makedirs(dname)
        with open(self._fname,"w") as fd:
            fd.write(str(self._num))

    def __call__(self): 
        self._read()
        self._num+=1
        self._write()
        return self._num
        #return "%s-%d" % (self._name,self._num)

class NamedSerializedSequence(SerializedSequence):
    def __call__(self):
        num=SerializedSequence.__call__(self)
        return "%s-%d" % (self._name,num)

## ok
class LoadClassError(Exception): pass

## ok
def load_class(path):
    t=path.rsplit(".",1)
    if len(t)==1:
        raise LoadClassError("Invalid class %s" % path)
    mod=importlib.import_module(t[0])
    cls=getattr(mod,t[1])
    return cls

## ok
def utc_now():
    """Return a timezone aware (UTC) datetime object for now.

    :returns: datetime -- now in utc. 
    """ 
    return datetime.datetime.now(datetime.timezone.utc)

def naive_to_utc(dt):
    dt=config.TZ.localize(dt)
    return dt.astimezone(datetime.timezone.utc)

def dict_to_utc(obj):
    dt=datetime.datetime(obj["year"],obj["month"],obj["day"],
                         obj["hour"],obj["minute"],obj["second"])
    return to_utc(dt)

def to_utc(dt):
    if not isinstance(dt,datetime.datetime):
        dt=datetime.datetime.fromtimestamp(dt)
    if not dt.tzinfo:
        return naive_to_utc(dt)
    return dt.astimezone(datetime.timezone.utc)
    
## ok
def log(*args,logger="root"):
    """Log a line with timestamp and all args.
    """ 
    #print(mk_tstamp(),*args)
    logger=logging.getLogger(logger)
    logger.info(" ".join([str(x) for x in args]))

## ok
def try_cast(x):
    """Try to cast a string (or bytes) to a numeric type.

    :x: string to cast
    :returns: int if x can be converted to int, float if x can be converted to float or str otherwise
    """

    if type(x) is bytes:
        x=x.decode()
    try:
        y=int(x)
    except ValueError as e:
        try:
            y=float(x)
        except ValueError as e:
            y=x
    return y

## ok
def random_string(l_min=3,l_max=10,add_chars=""):
    size=random.randint(l_min,l_max)
    chars=string.ascii_lowercase +string.ascii_uppercase + string.digits + add_chars
    S=''.join(random.choice(chars) for _ in range(size))
    return S

## ok
def slugify(S):
    S=S.replace(" ","")
    return S

## ok
def wait(sec):
    ev=threading.Event()
    ev.clear()
    ev.wait(sec)
