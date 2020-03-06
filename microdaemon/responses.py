# -*- coding: utf-8 -*-

"""Response objects for isambard server. 

All response classes inherit from abstract class AbstractResponse, who
enforces the interface needed  to `IsambardServer` to respect the
WSGI protocol.

The interface requires three properties/attributes:

*status* (str)
    HTTP response status, in the form "num_code msg".
*headers* (list)
    List of tuples (key, value)  of HTTP response headers. Every tuple
    will become the line `key: value` in HTTP response header.
*body_iterable* (iterable)
    List of bytes forming the response body.

"""

import wsgiref.util
import mimetypes
mimetypes.add_type('application/json',".map")
mimetypes.add_type('application/x-font-woff2',".woff2")
mimetypes.add_type('application/x-font-opentype',".otf")
mimetypes.add_type('application/x-font-truetype',".ttf")
mimetypes.add_type('text/x-less',".less")

import json
import abc

## Responses

## https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie
class Cookie(object):
    def __init__(self,name,value):
        self._name=name
        self._value=value

    def __str__(self):
        t=[self._name+"="+self._value]
        t.append("Path=/")
        t.append("SameSite=Strict")
        return "; ".join(t)

    def __repr__(self):
        S="<%s.%s(%s=%s)>" % (self.__class__.__module__,self.__class__.__qualname__,
                              self._name,self._value)
        return S

    def __eq__(self,other): 
        return (self._name==other._name) and (self._value==other._value)

    def __ne__(self,other): return not self.__eq__(other)

    def __hash__(self): return hash(self._name+"="+self._value)

class AbstractResponse(abc.ABC):
    """ Abstract class.

    *content_type*
        Mime type of the response.
    *status*
        HTTP response status, in the form "num_code msg".

    """

    def __init__(self,content_type,status="200 OK",cookies=[]):
        self._content_type=content_type
        self.status=status
        self._cookies=set(cookies)

    def add_cookie(self,cookie):
        self._cookies.add(cookie)

    @property
    @abc.abstractmethod
    def body_iterable(self): 
        """ The response body as iterable of bytes."""
        return []

    @property
    def headers(self): 
        """ The response headers as list of (key,value) tuples."""
        ret=[
            ('Content-Type', self._content_type),
        ]
        for cookie in self._cookies:
            ret.append(("Set-Cookie",str(cookie)))
        return ret

class Response(AbstractResponse):
    """ Generic response with a body (a "normal" response).

    *body* (str/bytes)
        Response body.
    *content_type* (str)
        Mime type of the response.
    *status* (str)
        HTTP response status, in the form "num_code msg".

    """

    def __init__(self,body,content_type='text/html; charset=utf-8',status="200 OK",cookies=[]):
        AbstractResponse.__init__(self,content_type,status=status,cookies=cookies)
        self._body=body

    @property
    def headers(self):
        ret =AbstractResponse.headers.fget(self)
        ret += [
            ('Content-Length', str(len(self._body)))
        ]
        return ret

    @property
    def body_iterable(self):
        return [self._body]

class JsonResponse(Response):
    """ Response for json object to serialize.

    *jobj* (object)
        A json serializable object.
    *content_type* (str)
        Mime type of the response.
    *status* (str)
        HTTP response status, in the form "num_code msg".

    """

    def __init__(self,jobj,content_type='application/json',status="200 OK",cookies=[]):
        body=json.dumps(jobj).encode('utf-8')
        Response.__init__(self,body,content_type=content_type,status=status,cookies=cookies)

class RedirectResponse(AbstractResponse):
    """Response for redirect.

    *url*
          The url to redirect.
    *content_type* (str)
        Mime type of the response.

    This response  has status "303 See  other". New url is  written in
    the header field "Location" and body is empty.

    """

    def __init__(self,url,content_type='text/html; charset=utf-8',cookies=[]):
        AbstractResponse.__init__(self,content_type,status="303 See other",cookies=cookies)
        self._url=url

    @property
    def body_iterable(self):
        return []

    @property
    def headers(self):
        ret =AbstractResponse.headers.fget(self)
        ret += [
            ('Location', self._url)
        ]
        return ret

class FoundResponse(AbstractResponse):
    """Response for data not ready yet.

    *wait_time*
          The time in seconds a client should wait before retry.
    *content_type* (str)
        Mime type of the response.

    This response  has status "302 Found".  Wait time is written  in the
    header field "Retry-After" and body is empty.

    """


    def __init__(self,wait_time,content_type='text/html; charset=utf-8',cookies=[]):
        AbstractResponse.__init__(self,content_type,status="302 Found",cookies=cookies)
        self._wait_time=wait_time

    @property
    def body_iterable(self):
        return []

    @property
    def headers(self):
        ret =AbstractResponse.headers.fget(self)
        ret += [
            ('Retry-After', str(self._wait_time))
        ]
        return ret

class StaticResponse(AbstractResponse):
    """Response for serving static content (i.e. content from file system).

    *path*
          The full path of file to serve.

    Mime type is inferred.

    """

    def __init__(self,file_path,cookies=[]):
        self.file_path=file_path
        c_type,c_enc=mimetypes.guess_type(self.file_path)
        if c_type is not None:
            AbstractResponse.__init__(self,c_type,cookies=cookies)
        else:
            AbstractResponse.__init__(self,"text/plain",cookies=cookies)

    @property
    def body_iterable(self):
        fd=open(self.file_path,"rb")
        return wsgiref.util.FileWrapper(fd)
