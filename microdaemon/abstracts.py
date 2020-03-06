import abc
import collections
import json
import os.path

from . import common,config,jsonlib

class DictProxy(collections.abc.MutableMapping,abc.ABC):
    """Abstract for masquerading an OrderedDict. 

    A  DictProxy has  OrderedDict  standard behaviour,  with just  few
    details changed. See for example SerializedDict.

    """

    def __init__(self):
        collections.abc.MutableSequence.__init__(self)
        self._dict=collections.OrderedDict()

    def __str__(self): return self._dict.__str__()
    def __repr__(self): return self._dict.__repr__()
    def __getitem__(self,*args,**kwargs):  return self._dict.__getitem__(*args,**kwargs)
    def __delitem__(self,*args,**kwargs):  return self._dict.__delitem__(*args,**kwargs)
    def __setitem__(self,*args,**kwargs): self._dict.__setitem__(*args,**kwargs)
    def __iter__(self,*args,**kwargs): return self._dict.__iter__(*args,**kwargs)
    def __len__(self,*args,**kwargs): return self._dict.__len__(*args,**kwargs)
    def __contains__(self,*args,**kwargs):  return self._dict.__contains__(*args,**kwargs)
    def __reversed__(self,*args,**kwargs): return self._dict.__reversed__(*args,**kwargs)

class SerializedDict(DictProxy):

    """A standard OrderedDict that keeps a copy of self on filesystem, in
       ''fpath'', in json format."""

    def __init__(self,fpath):
        DictProxy.__init__(self)
        self._fpath=fpath
        if os.path.exists(self._fpath):
            self._dict=jsonlib.json_load(self._fpath)

            for k in self._dict:
                val=self._dict[k]
                if isinstance(val,collections.OrderedDict):
                    if "year" in val:
                        self._dict[k]=common.dict_to_utc(val)
        
    def _save(self):
        with open(self._fpath,"w") as fd:
            json.dump(self._dict,fd)

    def __delitem__(self,*args,**kwargs):  
        ret=self._dict.__delitem__(*args,**kwargs)
        self._save()
        return ret

    def __setitem__(self,*args,**kwargs): 
        ret=self._dict.__setitem__(*args,**kwargs)
        self._save()
        return ret

class ListDictCollection(collections.abc.MutableSequence,abc.ABC):
    """Object list and dictionary. 

    You can  append or insert  an object as into  a list, but  you can
    read it or by index (like a list) or by object object_id (like a dict).
    """

    object_name="object"

    class OneTimeDict(dict):
        def __setitem__(self,key,obj):
            if key in self:
                raise ObjectDuplicateException("Object %s already exists" % repr(obj))
            dict.__setitem__(self,key,obj)

    def __init__(self):
        self._objects=[]
        self._by_key=self.OneTimeDict()

    def sort(self,*args,**kwargs):
        self._objects.sort(*args,**kwargs)

    def __getitem__(self,key): 
        if type(key) in (tuple,list):
            return [ self.__getitem__(k) for k in key ]
        if type(key) is str:
            return self._by_key[key]
        return self._objects.__getitem__(key)

    def __len__(self,*args,**kwargs): return self._objects.__len__(*args,**kwargs)
    def __iter__(self,*args,**kwargs): return self._objects.__iter__(*args,**kwargs)
    def __reversed__(self,*args,**kwargs): return self._objects.__reversed__(*args,**kwargs)

    def __contains__(self,*args,**kwargs): 
        return self._objects.__contains__(*args,**kwargs) or self._by_key.contains(*args,**kwargs)

    def __setitem__(self,key,obj): 
        self._insert(key,obj)

    def insert(self,key,obj):
        self._insert(key,obj)

    def _insert(self,key,obj):
        self._by_key[obj.object_id]=obj
        self._objects.insert(key,obj)
    
    def __delitem__(self,key):
        object_id=self._objects[key].object_id
        self._objects.__delitem__(key)
        self._by_key.__delitem__(object_id)


class ObjectDuplicateException(Exception): pass

class ObjectCollection(ListDictCollection,abc.ABC):
    def __init__(self,conf):
        ListDictCollection.__init__(self)
        for src in [ self.factory(src) for src in conf ]: self.append(src)

    @staticmethod
    def factory(desc):
        if type(desc["class"]) is str:
            cls=common.load_class(desc["class"])
        else:
            cls=desc["class"]
        return cls(desc)

    def __serialize__(self):
        return self._objects

    def __call__(self,**kwargs):
        for obj in self:
            found=True
            for k in kwargs:
                if not hasattr(obj,k): 
                    found=False
                    break
                if obj.__getattribute__(k)!=kwargs[k]: 
                    found=False
                    break
            if found: return obj
        return None


