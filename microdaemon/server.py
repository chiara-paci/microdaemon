# -*- coding: utf-8 -*-

""" Isambard server, the main isambard object. """

import socketio
import eventlet
import eventlet.wsgi
import urllib.parse
import collections
import mimetypes
import logging
#from eventlet.green import socket
#from eventlet.green.OpenSSL import SSL

mimetypes.add_type('application/json',".map")
mimetypes.add_type('application/x-font-woff2',".woff2")
mimetypes.add_type('application/x-font-opentype',".otf")
mimetypes.add_type('application/x-font-truetype',".ttf")
mimetypes.add_type('text/x-less',".less")

from . import config,common,channels
from . import pages,threads

logger_onshow=logging.getLogger("%s.onshow" % __name__)

class Request(object):
    """ Request from user. 

    *server* (IsambardServer)
        The server serving the request.
    *environ* (dict)
        The wsgi environ object.

    Attributes:
        *method* (str)
            Request methods in uppercase (GET, POST, etc.).
        *path* (str)
            Request path.
        *path_split* (list)
            List of path elements.
        *script* (str)
            Script name.
        *accept* (str)
            Response mimetype requested by client or text/html if client doesn't supply it.
        *body* (str)
            Request body.
        *querystring* (dict)
            Querystring parameters.
        *cookies* (dict)
            Cookies from client.

    """

    def __init__(self,server,environ):
        self._environ=environ
        self._server=server
        self.method=environ["REQUEST_METHOD"].upper()
        self.path=environ["PATH_INFO"]
        self.script=environ["SCRIPT_NAME"]
        if "HTTP_ACCEPT" in environ:
            self.accept=environ["HTTP_ACCEPT"]
        else:
            self.accept="text/html"
        self.path_split=self._path_split()
        self.body=self._body()
        self.querystring=self._querystring()
        self.cookies=self._cookies(environ)

    def _cookies(self,environ):
        if "HTTP_COOKIE" not in environ: return {}
        t=[ x.strip().split("=") for x in environ["HTTP_COOKIE"].split(";") ]
        t=[ (x[0],"=".join(x[1:])) for x in t ]
        return dict(t)

    def _path_split(self):
        t=self.path.split("/")
        if len(t)==0: return []
        if t[0]=="": t=t[1:]
        if len(t)==0: return []
        if t[-1]=="": t=t[:-1]
        return t

    def _body(self):
        try:
            request_body_size = int(self._environ.get('CONTENT_LENGTH', 0))
        except (ValueError):
            request_body_size = 0

        # When the method is POST the variable will be sent
        # in the HTTP request body which is passed by the WSGI server
        # in the file like wsgi.input environment variable.
        request_body = self._environ['wsgi.input'].read(request_body_size)
        return request_body

    def _querystring(self):
        raw_qs=urllib.parse.parse_qsl(self.body)
        qs=collections.OrderedDict()
        for raw_k,raw_val in raw_qs:
            k=raw_k.decode()
            val=common.try_cast(raw_val)
            if '[' not in k:
                key=k
                ind=None
            elif not k.endswith(']'):
                key=k
                ind=None
            else:
                t=k.split('[')
                key=t[0]
                ind=t[1][:-1]
                if ind=="": 
                    ind=-1
                else:
                    try:
                        ind=int(ind)
                    except ValueError as e:
                        print(ind)
                        key=k
                        ind=None
            if key not in qs:
                if ind is None:
                    qs[key]=val
                    continue
                qs[key]=[]
            elif type(qs[key]) is not list:
                qs[key]=[qs[key]]
            if ind==-1 or ind is None:
                qs[key].append(val)
                continue
            qs[key].insert(ind,val)

        return qs

    def _querystring_old(self):
        raw_qs=urllib.parse.parse_qs(self.body)
        print()
        qs=collections.OrderedDict()
        for raw_k in raw_qs:
            raw_val=raw_qs[raw_k]
            print("RAW",raw_k,raw_val)
            k=raw_k.decode()
            if len(raw_val)==1:
                qs[k]=common.try_cast(raw_val[0])
                continue
            qs[k]=[ common.try_cast(x) for x in raw_val ]

        print(qs)
        n_qs={}
        for k in qs:
            val=qs[k]
            if '[' not in k:
                key=k
                ind=None
            elif not k.endswith(']'):
                key=k
                ind=None
            else:
                t=k.split('[')
                key=t[0]
                ind=t[1][:-1]
                if ind=="": 
                    ind=-1
                else:
                    try:
                        ind=int(ind)
                    except ValueError as e:
                        print(ind)
                        key=k
                        ind=None
            if key not in n_qs:
                if ind is None:
                    n_qs[key]=val
                    print(key,n_qs[key])
                    continue
                n_qs[key]=[]
            elif type(n_qs[key]) is not list:
                n_qs[key]=[n_qs[key]]
            if ind==-1 or ind is None:
                n_qs[key].append(val)
                print(key,n_qs[key])
                continue
            n_qs[key].insert(ind,val)
            print(key,n_qs[key])
            continue
            

        return n_qs

class InfoNamespace(socketio.Namespace):
    def __init__(self,server,*args,**kwargs):
        socketio.Namespace.__init__(self,*args,**kwargs)
        self._server=server
        self.size=0

    def on_connect(self,sid, environ):
        common.log('SIO connect %s' % sid)
        self.size+=1
        self.emit("init_onshow",self._server.db.onshow,room=sid)

    def on_disconnect(self,sid):
        common.log('SIO disconnect %s' % sid)
        self.size-=1
        if self.size<0: self.size=0

class IsambardServer(object):
    """Main Isambard object. 

    *bus* (channels.Bus)
        Communication bus common to all objects.
    *port* (int)
        Port to bind.
    *host* (str)
        Host to bind.

    A  `IsambardServer` object  is  the interface  between user  and
    other components of Isambard. It  run a WSGI server listening on
    host *host* and port *port* (default 7373 on localhost).  The user
    can connect with a  browser to "http://*host*:*port*" and interact
    in this way.

    Attributes:
        *bus* (channels.Bus)
            Communication bus common to all objects.

    """

    def __init__(self,db,bus,host="localhost",port=7373):
        self.bus=bus
        self.bus["configuration"]=channels.SimpleChannel()
        self.bus["onshow"]=channels.SimpleChannel()

        self.db=db 

        self._http_host=host
        self._http_port=port

        self.application=pages.log_decorator(pages.exception_decorator(self)(self._application))

        th=threads.WhileTrueThread(target=self._thread_onshow,name="OnShowThread")
        th.start()

    ### Threads

    def _thread_onshow(self):
        msg=self.bus["onshow"].read_message(block=True)
        if msg is None: return
        log_time=common.utc_now()
        onshow=msg[0]
        self.db.onshow.append( (log_time,onshow) )
        logger_onshow.info("[%s] %s" % (log_time,onshow))
        if "browser/info" in self.bus:
            self.bus["browser/info"].send_message("onshow",(log_time,onshow))

    ### Application

    def _application(self,request):
        page=self.page_factory(request)
        response=page.dispatch(request)
        return response

    def page_factory(self,request):
        """Transform a request in a Page object.

        *request* (Request)
            Request from user.

        Return    a   Page    (or    subclass)    object   or    raise
        pages.Http404NotFound(request) if *request* has no valid path.

        """

        if len(request.path_split)==0: 
            return pages.HomePage(self)

        if request.path.startswith("/"+config.STATIC_REL_PATH):
            obj_path=request.path[len(config.STATIC_REL_PATH)+2:]
            return pages.StaticPage(self,obj_path)

        if len(request.path_split)==1:
            if request.path_split[0] == "favicon.ico":
                obj_path=config.FAVICON
                return pages.StaticPage(self,obj_path)
            for req,label,title in [ ("license","gplv3","License"),
                                     ("about","about","About") ]:
                if request.path_split[0] == req:
                    return pages.TextPage(self,label,title)
            for target,p_class,collection in [ ("pictures",pages.ObjectListPage,self.db.pictures),
                                               ("videos",pages.ObjectListPage,self.db.videos),
                                               ("music",pages.ObjectListPage,self.db.music) ]:
                if request.path_split[0] == target:
                    return p_class(self,collection)

            for p,p_class in [ ( "showlist", pages.ShowListPage  ),
                               ( "configurator", pages.ConfiguratorPage  )]:
                if request.path_split[0] == p:
                    return p_class(self)
            raise pages.Http404NotFound(request)

        if len(request.path_split)==2:
            if request.path_split[0] not in ["pictures","videos","music"]:
                raise pages.Http404NotFound(request)
            object_id=request.path_split[1]
            for target,p_class,collection in [ ("pictures",pages.PictureObjectPage,self.db.pictures),
                                               ("videos",pages.VideoObjectPage,self.db.videos),
                                               ("music",pages.MusicObjectPage,self.db.music) ]:
                if request.path_split[0]==target:
                    try:
                        obj=collection[object_id]
                    except KeyError as e:
                        raise pages.Http404NotFound(request)
                    return p_class(self,obj)

        if len(request.path_split)==3:
            if request.path_split[0] not in ["pictures","videos","music"]:
                raise pages.Http404NotFound(request)
            if request.path_split[2]!="thumbnail.jpeg":
                raise pages.Http404NotFound(request)
            object_id=request.path_split[1]
            for target,p_class,collection in [ ("pictures",pages.ThumbnailPage,self.db.pictures),
                                               ("videos",pages.ThumbnailPage,self.db.videos),
                                               ("music",pages.ThumbnailPage,self.db.music) ]:
                if request.path_split[0]==target:
                    try:
                        obj=collection[object_id]
                    except KeyError as e:
                        raise pages.Http404NotFound(request)
                    return p_class(self,obj)

        raise pages.Http404NotFound(request)


    ####################################
    ### main logic

    def start(self):
        """ Main function.

        Run a WSGI simple server with `self.wsgi` as main function.
        """

        common.log("Isambard %s Started on http://%s:%d/ with %s" % (config.VERSION,
                                                                     self._http_host,
                                                                     self._http_port,
                                                                     self.db))

        socket=eventlet.listen((self._http_host, self._http_port))

        eventlet.wsgi.server(socket,
                             self._socketio_decorator(self.wsgi),
                             log_output=False,debug=False)

    def _socketio_decorator(self,wsgi):
        sio=socketio.Server(async_mode="eventlet")
        namespace=InfoNamespace(self,"/info")
        sio.register_namespace(namespace)
        self.bus["browser/info"]=channels.BrowserChannel(namespace=namespace)
        return socketio.Middleware(sio,wsgi)

    def wsgi(self,environ, start_response):
        """WSGI function interface.

        *environ* (dict)
            WSGI environ.
        *start_response* (callable)
            WSGI start_response

        Build  a request  around  *environ*, call  `self.application`,
        obtain   a  response   and   call  (as   per  WSGI   protocol)
        `start_response(response.status, response.headers)`.
        Return `response.body_iterable` (as per WSGI protocol).

        """
        request=Request(self,environ)
        response=self.application(request)
        start_response(response.status, response.headers)
        return response.body_iterable

            
