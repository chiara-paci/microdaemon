""" This module define communication bus, channels and exceptions related to message queues.

Exceptions:
    *ChannelDefinitionConflict*
         Raised when a channel is defined more than one time with two different classes.
    *NoReceiverOnChannel*
         Raised when a receiver try to read a message without registration on channel.

Classes:
    *Bus*
         A dictionary of channels.
    *Channel*
         Abstract class for defining a channel.
    *SimpleChannel*
         A channel with one receiver.
    *BroadcastChannel* 
         A channel with multiple receivers.
    *RouterChannel*
         A channel with multiple receivers, where each receiver can read only a subset of messages.
    *SerializerChannel*
         A channel with one receiver, able to requeue objects and serialize it until dismissed*

"""

import socketio
import queue
import abc
import os
import pickle
import logging

from . import common,config

logger=logging.getLogger(__name__)

class ChannelDefinitionConflict(Exception):
    """Raised when a channel is defined more than one time with two different classes"""

    def __init__(self,channel_id,old_channel,new_channel):
        self.channel_id=channel_id
        self.old_channel=old_channel
        self.new_channel=new_channel

    def __str__(self):
        msg="Definition of channel %(channel)s as %(new)s conflict with previous declaration as %(old)s"
        return msg % { "channel": self.channel_id,
                       "new": str(self.new_channel),
                       "old": str(self.old_channel) }

class NoReceiverOnChannel(Exception):
    """Raised when a receiver try to read a message without registration on channel."""

    def __init__(self,receiver_id):
        self.receiver_id=receiver_id

    def __str__(self):
        msg="There is no receiver with id %s" % self.receiver_id
        return msg

class Bus(dict):
    """A dictionary of channels.

    This is a normal dictionary, where each channel is identified by a
    key. You define a channel by assigning an object to a key.

    When you try  to redefine a channel, assigning a  new object to an
    existing key, the Bus can  silently discard the new definition, if
    the new  definition match the  previous defined channel  (i.e., if
    they  result  equals in  pythonic  sense).   Or  it can  raises  a
    ChannelDefinitionConflict when  the two channels don't  match (for
    example,   if  you   try  to   redefine  a   SimpleChannel  as   a
    BroadcastChannel).

    This behaviour allows threads to  define the same channel multiple
    times (so they  can avoid to syncronize), but force  them to do it
    consistently.

    """

    def get_queues(self): 
        keys=list(self.keys())
        keys.sort()
        ret=[ (k,type(self[k]).__name__,self[k].size) for k in keys ]
        return ret

    def __setitem__(self,channel_id,channel):
        if channel_id in self:
            if channel==self[channel_id]: return
            raise ChannelDefinitionConflict(channel_id,self[channel_id],channel)
        dict.__setitem__(self,channel_id,channel)
        for cl in [SerializerChannel,LoggerChannel]:
            if isinstance(channel,cl):
                channel.name=channel_id

class Channel(abc.ABC):
    """Abstract class for defining a channel.

    You must subclass this class to define a type of channel. A subclass must define two methods:

    send_message 
        Method used by a sender to  send a message in the channel.

    read_message 
        Method used by a receiver to  receive a message.

    A Channel  must have  an "equality" definition,  i.e. must  have a
    method __eq__(). The  default is to evaluate as  equal two objects
    if they are  instance of the exact same class,  so allowing Bus to
    consider equivalent  two definitions  of channel  if they  are two
    instance of the same class. A  subclass is not equal to the parent
    class.
    """

    def __eq__(self,other):
        return type(self) is type(other)

    def __str__(self):
        return type(self).__name__

    @abc.abstractmethod
    def send_message(self,*args): 
        """        
        Method used by a sender to  send a message in the channel. 

        The message is the tuple passed as \*args.
        """
        pass

    @abc.abstractmethod
    def read_message(self,block=False,timeout=None): 
        """Method used by a receiver to  receive a message.

        If  the queue  is empty  and block=False  (the default),  this
        method returns None.  If block=True,  it waits until a message
        is available.

        It   returns  the   tuple   \*args   passed  to   corresponding
        send_message.

        """
        pass

    @property
    @abc.abstractmethod
    def size(self): 
        """ Size of the queue. The meaning is channel dependent."""
        return -1

class NullChannel(Channel):
    def send_message(self,*args): 
        pass

    def read_message(self,block=False,timeout=None): 
        return None

    @property
    def size(self): 
        """ Size of the queue. The meaning is channel dependent."""
        return 0

class CounterChannel(Channel):
    def __init__(self):
        self._num=0

    def send_message(self,*args): 
        self._num+=1

    def read_message(self,block=False,timeout=None): 
        return None

    @property
    def size(self): 
        """ Size of the queue. The meaning is channel dependent."""
        return self._num

class LoggerChannel(Channel):
    def __init__(self):
        self._num=0
        self.name="logger_channel"

    def send_message(self,*args): 
        logger_c=logging.getLogger(self.name)
        self._num+=1
        logger_c.info(" ".join([str(x) for x in args]))

    def read_message(self,block=False,timeout=None): 
        return None

    @property
    def size(self): 
        """ Size of the queue. The meaning is channel dependent."""
        return self._num

class BrowserChannel(Channel):
    def __init__(self,namespace=None):
        if namespace is not None:
            self._namespace=namespace
        else:
            self._namespace=socketio.Namespace()

    def send_message(self,*args):
        self._namespace.emit(*args)

    def read_message(self,block=False,timeout=None):
        return None

    @property
    def size(self):
        if hasattr(self._namespace,"size"):
            return self._namespace.size
        return -1

class SimpleChannel(Channel):
    """A channel with one receiver.

    This channel  has just one  queue. The method send_message  puts a
    message in the queue, and  the method read_message reads a message
    from the queue.

    There is no enforcement on the  number of threads reading from the
    queue, so it is to the programmer  to assure than no more than one
    thread read from a SimpleChannel (or to accept than a thread could
    lost some messages).

    """

    def __init__(self):
        self._queue=queue.Queue()

    def send_message(self,*args):
        self._queue.put(args)

    def read_message(self,block=False,timeout=None):
        try:
            msg=self._queue.get(block=block,timeout=timeout)
            self._queue.task_done()
        except queue.Empty as e:
            return None
        return msg

    @property
    def size(self):
        return self._queue.qsize()


class LastOnlyChannel(SimpleChannel):
    """A channel with one receiver forgetting all messages except last.

    This channel  has just one  queue. The method send_message  puts a
    message in the queue, and  the method read_message reads a message
    from the queue.  When a message is read, the  queue is emptied and
    only last message is returned to user.

    This channel  is useful  to record  status change  requests, where
    only last is significant.

    There is no enforcement on the  number of threads reading from the
    queue, so it is to the programmer  to assure than no more than one
    thread read from a SimpleChannel (or to accept than a thread could
    lost some messages).

    """

    def read_message(self,block=False,timeout=None):
        msg=SimpleChannel.read_message(self,block=block,timeout=timeout)
        if msg is None: return msg
        new_msg=msg
        while new_msg is not None:
            new_msg=SimpleChannel.read_message(self)
            if new_msg is not None:
                msg=new_msg
        return msg

class SerializerChannel(SimpleChannel):
    """A channel with one receiver and able to serialize objects.

    This channel  has just one  queue. The method send_message  puts a
    message  in  the queue,  and  save  it  in  a storage  area  under
    STORAGE_SERIALIZER_CHANNELS/queue_name/.

    There is no enforcement on the  number of threads reading from the
    queue, so it is to the programmer  to assure than no more than one
    thread read from  a SerializerChannel (or to accept  than a thread
    could lost some messages).

    The  method  read_message  return  the  message  from  the  queue,
    prefixed  with  a message  id  assigned  by  the channel  (if  the
    original  message is  ('a','b','c')  the returned  object will  be
    (msg_id,'a','b','c') ).  

    Users of SerializerChannel must commit  or rollback the read after
    message  elaboration. With  commit_read(),  the serialized  object
    will  be  deleted.  With  rollback_read(),  the  message  will  be
    requeued. The original order of arriving is preserved.

    """ 

    _suffix=".pickle"

    def __init__(self):
        SimpleChannel.__init__(self)
        self.name=common.random_string(l_min=20,l_max=20)
        self._sequence=common.SerializedSequence("channel_"+self.name)
        self._queue=queue.PriorityQueue()

    @property
    def _storage_path(self):
        return os.path.join(config.STORAGE_SERIALIZER_CHANNELS,self.name)

    def __setattr__(self,attr,value):
        SimpleChannel.__setattr__(self,attr,value)
        if attr != "name":
            return
        self._sequence=common.SerializedSequence("channel_"+value)
        if not os.path.isdir(self._storage_path):
            return 
        for entry in os.scandir(self._storage_path):
            if not entry.is_file(): continue        
            if not entry.name.endswith(self._suffix): continue
            try:
                msg_id,msg=self._unserialize(entry.name)
            except EOFError as e:
                logger.error("Msg %s broken:" % entry.name.replace(self._suffix,""))
                fpath=os.path.join(self._storage_path,entry.name)
                logger.exception(e)
                os.remove(fpath)
                logger.error("File %s removed" % fpath)
                continue
            SimpleChannel.send_message(self,msg_id,*msg)

    def _message_fpath(self,msg_id):
        fpath=os.path.join(self._storage_path,"%d%s" % (msg_id,self._suffix) )
        return fpath

    def _serialize(self,msg_id,*args):
        os.makedirs(self._storage_path,exist_ok=True)
        fpath=self._message_fpath(msg_id)
        fd=open(fpath,"wb")
        pickle.dump(args,fd)
        fd.close()

    def _unserialize(self,fname):
        fpath=os.path.join(self._storage_path,fname)
        msg_id=int(fname.replace(self._suffix,""))
        with open(fpath,"rb") as fd:            
            msg=pickle.load(fd)
        return msg_id,msg

    def send_message(self,*args):
        msg_id=self._sequence()
        self._serialize(msg_id,*args)
        SimpleChannel.send_message(self,msg_id,*args)

    def commit_read(self,msg_id,*args):
        #common.log("COMMIT",self.name,msg_id,*args)

        fpath=self._message_fpath(msg_id)
        os.remove(fpath)

    def rollback_read(self,msg_id,*args):
        self._serialize(msg_id,*args)
        SimpleChannel.send_message(self,msg_id,*args)

class CleanSerializerChannel(SerializerChannel):
    def __setattr__(self,attr,value):
        SimpleChannel.__setattr__(self,attr,value)
        if attr != "name":
            return
        self._sequence=common.SerializedSequence("channel_"+value)
        if not os.path.isdir(self._storage_path):
            return 
        for entry in os.scandir(self._storage_path):
            if not entry.is_file(): continue        
            if not entry.name.endswith(self._suffix): continue
            os.remove(os.path.join(self._storage_path,entry.name))


class BroadcastChannel(Channel):
    """A channel with multiple receivers.

    This channel has  a queue for each receiver. Each  receiver has an
    identifier  and  must  be registered  with  add_receiver()  before
    reading  from the  channel. It  must supply  the receiver  id when
    reading from the channel.

    All messages will be sent to all receivers.

    """

    def __init__(self):
        self._queues={}

    @property
    def size(self):
        ret=[]
        for k,q in self._queues.items():
            ret.append( (k,q.qsize()) )
        ret.sort()
        return ret

    def add_receiver(self,receiver_id):
        """ Register the receiver identified by receiver_id to the channel.
        """
        self._queues[receiver_id]=queue.Queue()

    def send_message(self,*args):
        for rid in self._queues:
            ch=self._queues[rid]
            ch.put(args)

    def read_message(self,receiver_id,block=False,timeout=None):
        """
        This method overrides the default behaviour, with a new parameter:

        receiver_id
            The idenitifier of the receiver, as per add_receiver()

        Return value is the same as other channels.
        """
        if not receiver_id in self._queues:
            raise NoReceiverOnChannel(receiver_id)
        try:
            msg=self._queues[receiver_id].get(block=block,timeout=timeout)
        except queue.Empty as e:
            return None
        return msg

    def reset(self):
        """ Deregister all receivers. """
        self._queues={}

class RouterChannel(BroadcastChannel):
    """A channel with multiple receivers, where each receiver can read only a subset of messages.

    This channel has  a queue for each receiver. Each  receiver has an
    identifier  and  must be  registered  with  add_receiver(), as  in
    BroadcastChannel.  But  the receiver  must  supply  a function  to
    filter messages that they are interested in.

    Messages will only be sent to a receiver when the filter match the
    message.

    """

    def __init__(self):
        self._queues={}
        self._checks={}

    def add_receiver(self,receiver_id,check):
        """This method overrides the behaviour of BroadcastChannel, with a new parameter:

        check 
            A function with the signature f(\*args), that returns True
            if the  receiver is interested  in the message,  and False
            otherwise.

        """

        self._queues[receiver_id]=queue.Queue()
        self._checks[receiver_id]=check

    def send_message(self,*args):
        for rid in self._queues:
            if self._checks[rid](args):
                ch=self._queues[rid]
                ch.put(args)

