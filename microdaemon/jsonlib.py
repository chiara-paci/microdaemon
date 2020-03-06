import json
import collections
import datetime
import pytz
import numpy
import pandas
import unittest.mock

def json_object_pairs_hook(obj): 
    odict=collections.OrderedDict(obj)
    if "__include__" not in odict:
        return odict
    ndict=json_load(odict["__include__"])
    for k in odict:
        if k=="__include__": continue
        ndict[k]=odict[k]
    return ndict

## ok
def json_fd_load(fd,comment="//"):
    """Load a json file by file object. Skip any line beginning with *comment*.

    :fd: file object
    :comment: first characters of comment lines
    :returns: python object 
    """

    txt=""
    for r in fd.readlines(): 
        if type(r) is bytes:
            r=r.decode('utf-8')
        if r.strip().startswith(comment):
            continue
        txt+=r

    return json.loads(txt,object_pairs_hook=json_object_pairs_hook)

## ok
def json_load(fpath,comment="//"):
    """Load a json file by file path. Skip any line beginning with *comment*.

    :fpath: file path
    :comment: first characters of comment lines
    :returns: python object 
    """

    if fpath=="-": 
        fd=sys.stdin
    else: 
        fd=open(fpath,'r')
    txt=json_fd_load(fd,comment=comment)
    if fpath!="-": fd.close()
    return txt

class JsonSerializerError(Exception):
    def __init__(self,original,obj):
        self.original=original
        self.obj=obj

    def __str__(self):
        return "Object %s of type %s is not json serializable" % (self.obj,type(self.obj))

def serialize_time(obj):
    if obj is None: return obj
    if isinstance(obj,datetime.timedelta):
        s=obj.seconds % 60
        m=obj.seconds // 60
        h=m//60
        m=m%60
        return {
            "days": obj.days,
            "seconds": obj.seconds,
            "total_seconds": obj.total_seconds(),
            "human": {
                "hour": h,
                "minute": m,
                "second": s,
                "str": "%02d:%02d:%02d" % (h,m,s)
            }
        }

    if obj.tzinfo is None:
        return {
            "year": obj.year,
            "month": obj.month,
            "day": obj.day,
            "hour": obj.hour,
            "minute": obj.minute,
            "second": obj.second,
            "timestamp": (obj - datetime.datetime(1970, 1, 1)).total_seconds(),
            "tzinfo": {
                "utcoffset": serialize_time(datetime.timedelta(0,0)),
                "dst": None,
                "name": "UTC",
            }
        }
        
    if obj.tzinfo.utcoffset(obj).total_seconds()==0:
        return {
            "year": obj.year,
            "month": obj.month,
            "day": obj.day,
            "hour": obj.hour,
            "minute": obj.minute,
            "second": obj.second,
            "timestamp": (obj.astimezone(pytz.utc) - datetime.datetime(1970, 1, 1,tzinfo=pytz.utc)).total_seconds(),
            "tzinfo": {
                "utcoffset": serialize_time(datetime.timedelta(0,0)),
                "dst": None,
                "name": "UTC",
            }
        }

    ret=serialize_time(obj.astimezone(pytz.utc))
    ret["local"]={
        "year": obj.year,
        "month": obj.month,
        "day": obj.day,
        "hour": obj.hour,
        "minute": obj.minute,
        "second": obj.second,
        "tzinfo": {
            "utcoffset": serialize_time(obj.tzinfo.utcoffset(obj)),
            "dst": obj.tzinfo.dst(obj),
            "name": obj.tzinfo.tzname(obj),
        }
    }

    return ret

def serialize_numpy(obj):
    if type(obj) in [numpy.int64,numpy.uint8,numpy.uint64]:
        return int(obj)
    if type(obj) in [numpy.ndarray]:
        return list(obj)
    if type(obj) in [numpy.datetime64]:
        return serialize_pandas(pandas.Timestamp(obj))
    
    return obj

def serialize_pandas(obj):
    if type(obj) in [ pandas.core.series.Series ]:
        return obj.to_json()
    if type(obj) in [ pandas.core.indexes.numeric.Int64Index ]:
        return serialize_numpy(obj.values)
    if type(obj) in [ pandas.core.indexes.datetimes.DatetimeIndex ]:
        return serialize_numpy(obj.values)
    return obj

## ok
def json_settings():
    from json import JSONEncoder

    def _default(self, obj):
        if type(obj) in [ datetime.datetime, datetime.timedelta,datetime.date,
                          pandas._libs.tslib.Timestamp,pandas._libs.tslib.Timedelta, ]:
            return serialize_time(obj)
        if type(obj) in [ numpy.int64,numpy.ndarray,numpy.datetime64,numpy.uint8,numpy.uint64 ]:
            return serialize_numpy(obj)
        if type(obj) in [ pandas.core.series.Series, pandas.core.indexes.numeric.Int64Index,
                          pandas.core.indexes.datetimes.DatetimeIndex ]:
            return serialize_pandas(obj)
        if isinstance(obj,unittest.mock.MagicMock):
            return str(obj)
        try:
            ret=getattr(obj.__class__, "__serialize__", _default.default)(obj)
        except TypeError as e:
            #log("ERROR: object %s of type %s is not json serializable" % (obj,type(obj)))
            raise JsonSerializerError(e,obj) from None
        return ret

    _default.default = JSONEncoder().default
    JSONEncoder.default = _default
