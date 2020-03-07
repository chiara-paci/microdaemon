# -*- coding: utf-8 -*-

"""Pages for isambard server. 

A page is the abstraction of something returned to user.

The    server   build    a   page,    therefore   call    the   method
`page.dispatch(request)` to obtain a response.

"""

import datetime
import jinja2
import os.path
import abc
import logging
import traceback
import pickle
import http.cookiejar
import pytz

from . import config,common,responses,jsonlib,channels,configurator

logger_access=logging.getLogger("%s.access" % __name__)
logger_error=logging.getLogger("%s.error" % __name__)

## Exceptions

class Http405MethodNotAllowed(Exception):
    """ Raised for request with invalid method. """

    def __init__(self,request):
        self.request=request

    def __str__(self):
        return "Method %s is not allowed for page %s" % (self.request.method,self.request.path)

class Http404NotFound(Exception):
    """ Raised for request for inexistent resource. """

    def __init__(self,request):
        self.request=request

    def __str__(self):
        return "Page %s was not found on this server" % self.request.path

class Http400BadRequest(Exception):
    """ Raised for bad request. """

    def __init__(self,request):
        self.request=request

    def __str__(self):
        return "Bad request on %s" % self.request.path

class Http401Unauthorized(Exception):
    """ Raised for unauthorized. """

    def __init__(self,request):
        self.request=request

    def __str__(self):
        return "Authentication required for access to %s" % self.request.path

class Http403Forbidden(Exception):
    """ Raised for forbidden. """

    def __init__(self,request):
        self.request=request

    def __str__(self):
        return "Resource %s is forbidden" % self.request.path

## Decorators

def log_decorator(func):
    def decorated(request):
        response=func(request)
        if isinstance(response,responses.StaticResponse):
            return response
        if request.accept=="application/json": 
            return response
        params=[request.method,
                response.status,
                request.path,
                "Accept: "+request.accept]
        if request.querystring:
            params.append("Query:")
            params.append(request.querystring)
        if request.cookies:
            params.append("Cookies:")
            params.append(request.cookies)
        logger_access.info(" ".join([str(x) for x in params]))
        if response.status.startswith("5"):
            logger_error.error(" ".join([str(x) for x in params]))
        return response
    return decorated

def exception_decorator(server):
    def decorator(func):
        def decorated(request):
            try:
                try:
                    response=func(request)
                except Http400BadRequest as e:
                    page=Error400Page(server,e)
                    response=page.dispatch(request)
                except Http401Unauthorized as e:
                    page=Error401Page(server,e)
                    response=page.dispatch(request)
                except Http403Forbidden as e:
                    page=Error403Page(server,e)
                    response=page.dispatch(request)
                except Http405MethodNotAllowed as e:
                    page=Error405Page(server,e)
                    response=page.dispatch(request)
                except Http404NotFound as e:
                    page=Error404Page(server,e)
                    response=page.dispatch(request)
                except jsonlib.JsonSerializerError as e:
                    page=Error500Page(server,e)
                    response=page.dispatch(request)
                    logger_error.exception("Json Serializer Error")
            except Exception as e:
                page=Error500Page(server,e)
                response=page.dispatch(request)
                logger_error.exception("Generic Error")
            return response
        return decorated
    return decorator

########################################################################
## Pages

class Page(abc.ABC):
    """Abstract class.

    *server* (server.IsambardServer)
        The server.

    Page provides a method `dispatch`  for all subclasses and requests
    that all subclasses implement a `get_handler` method.

    """

    def __init__(self,server):
        self._server=server

    @abc.abstractmethod
    def get_handler(self,request): 
        """Return the callable that can handle this request.

        *request* (server.Request)
            A request object

        Return a callable with  signature response=f(request) or raise
        a Http405MethodNotAllowed(request) exception if the request is
        invalid.

        """
        raise Http405MethodNotAllowed(request)

    def dispatch(self,request):
        """ Build the response for the request.

        *request* (server.Request)
            The client request.

        Return the response (responses.Response) or raise appropriate exception.
        """

        handler=self.get_handler(request)
        response=handler(request)
        if not request.cookies: return response
        for key in request.cookies:
            if key!="index_panel": continue
            response.add_cookie(responses.Cookie(key,request.cookies[key]))
        return response

class StaticPage(Page):
    """Page for static resource.

    *server* (server.IsambardServer)
        The server.
    *obj_path* (str)
        The path of static resource, relative to `config.STATIC_DIR`.

    HTTP  method  accepted:

       GET, served  by `self.get()`. 

    Response:

        `responses.StaticResponse`.

    Exception:

        `Http405MethodNotAllowed`
             if the http method is not *GET*;
        `Http404NotFound`
             if the resource requested is not available.

    """

    def __init__(self,server,obj_path):
        self._obj_path=obj_path
        Page.__init__(self,server)

    def get_handler(self,request):
        if request.method!="GET":
            raise Http405MethodNotAllowed(request)
        return self.get

    def _get_path(self):
        return os.path.join(config.STATIC_DIR,self._obj_path)

    def get(self,request):
        """ Handler for GET. """
        file_path=self._get_path() #os.path.join(config.STATIC_DIR,self._obj_path)
        if not os.path.isfile(file_path):
            raise Http404NotFound(request)
        if file_path.startswith(".") or "/." in file_path:
            raise Http404NotFound(request)
        response=responses.StaticResponse(file_path)
        return response

class ThumbnailPage(StaticPage):
    def __init__(self,server,media_object):
        StaticPage.__init__(self,server,media_object.thumbnail_path)
        self._object=media_object

    def _get_path(self):
        return self._object.thumbnail_path

class TemplatePage(Page):
    """ Generate a page with a jinja2 template.

    HTTP  method  accepted:

       GET, served  by `self.get()`. 

    Response:

        `responses.Response`.

    Exception:

        `Http405MethodNotAllowed`
             if the http method is not *GET*;

    """


    _template_label="418"
    @property
    def template_name(self):
        """Path of template, relative to config.TEMPLATE_DIR."""
        return config.TEMPLATE_NAMES[self._template_label]
    
    _page_title=""
    @property
    def title(self):
        """ Full title of the page  (to place in "title" element of html)."""
        if not self._page_title:
            return config.SERVER_NAME
        return config.SERVER_NAME+": "+self._page_title

    def _apply_template(self,template_name,context):
        env=jinja2.Environment(loader=jinja2.FileSystemLoader(config.TEMPLATE_DIR))
        template=env.get_template(template_name)
        T=template.render(**context)
        T=T.encode('utf-8')
        return T

    def get_context(self,request):
        """ Generate the context for the template."""
        context={
            "locale": config.LOCALE,
            "server_name": config.SERVER_NAME,
            "title": self.title,
            "base_url": request.script,
            "static_url": request.script+"/"+config.STATIC_REL_PATH,
            "version": config.VERSION,
            "copy_name": config.COPY_NAME,
            "copy_url": config.COPY_URL,
            "copy_year": config.COPY_YEAR,
        }
        return context

    def get_handler(self,request):
        if request.method!="GET":
            raise Http405MethodNotAllowed(request)
        return self.get

    _status="200 OK"
    def get(self,request):
        """ Handler for GET. """
        context=self.get_context(request)
        response=responses.Response(self._apply_template(self.template_name,context),
                                    status=self._status)
        return response

class TextPage(TemplatePage):
    _template_label="text"

    def __init__(self,server,label,title):
        TemplatePage.__init__(self,server)
        self._label=label
        self._title=title

    @property
    def title(self):
        """ Full title of the page  (to place in "title" element of html)."""
        if not self._page_title:
            return config.SERVER_NAME
        return config.SERVER_NAME+": "+self._title

    def get_context(self,request):
        context=TemplatePage.get_context(self,request)
        context["label"]=self._label
        return context

class ErrorPage(TemplatePage):
    """ Generate an error page.

    HTTP  method  accepted:

       all, served  by `self.get()`. 

    """

    _page_title="Error"
    _template_label="error"

    def __init__(self,server,exception):
        self.exception=exception
        TemplatePage.__init__(self,server)

    def get_context(self,request):
        context=TemplatePage.get_context(self,request)
        context["status"]=self._status
        context["error"]=str(self.exception)
        return context

    def get_handler(self,request):
        # Error serves all method, not just GET
        return self.get

class Error404Page(ErrorPage):
    """ Generate an error 404 page."""

    _status="404 Not Found"

class Error400Page(ErrorPage):
    """ Generate an error 400 page."""

    _status="400 Bad Request"

class Error401Page(ErrorPage):
    """ Generate an error 401 page."""

    _status="401 Unauthorized"

class Error403Page(ErrorPage):
    """ Generate an error 403 page."""

    _status="403 Forbidden"

class Error405Page(ErrorPage):
    """ Generate an error 405 page."""

    _status="405 Method Not Allowed"

class Error500Page(ErrorPage):
    """ Generate an error 500 page."""

    _status="500 Internal Server Error"

    def _apply_template(self,template_name,context):
        txt="<html><head><title>{{ title }}</title></head>"
        txt+="<body><h1>Server Error</h1>"
        try:
            debug=config.DEBUG
        except Exception as e:
            debug=False
        if debug:
            txt+="<pre>"
            txt+="{{ stacktrace }}"
            txt+="</pre>"
        txt+="</body></html>"

        template = jinja2.Template(txt)

        T=template.render(**context)
        T=T.encode('utf-8')
        return T

    def get_context(self,request):
        """ Generate the context for the template."""
        context={
            "title": "Isambard: %s" % self._status,
            "stacktrace": traceback.format_exc()
        }
        return context

class HomePage(TemplatePage):
    """ Generate the home page."""

    _template_label="homepage"

    def get_context(self,request):
        context=TemplatePage.get_context(self,request)
        #context["onshow"]=self._server.db.onshow
        return context

class ConfiguratorPage(TemplatePage):
    """ Generate the configurator page."""

    _template_label="configurator"
    _page_title="Configurator"

    def get_context(self,request):
        context=TemplatePage.get_context(self,request)
        context["configurator"]=config.configurator
        return context

class ObjectListPage(TemplatePage):
    """ Generate the home page."""

    _template_label="object_list"

    def __init__(self,server,collection):
        TemplatePage.__init__(self,server)
        self._collection=collection

    def get_context(self,request):
        context=TemplatePage.get_context(self,request)
        context["collection"]=self._collection
        return context


class JsonDataPage(Page,abc.ABC):
    """ Abstract class for output related json data pages.

    *server* (server.IsambardServer)
        The server.

    HTTP  method  accepted:

       GET with accept="application/json", served  by `self.get_json()`. 

    Response:

        `responses.JsonResponse`
            when data are available;
        `responses.FoundResponse`
            when data are loading.

    Exception:

        `Http405MethodNotAllowed`
             if the http method is not *GET* or accept is not "application/json";
        `Http404NotFound`
             if requested data cannot be retrieved.

    """
    _retry_after=2 # secs

    def __init__(self,server): 
        Page.__init__(self,server)

    def get_handler(self,request):
        if (request.method=="GET") and (request.accept=="application/json"):
            return self.get_json
        raise Http405MethodNotAllowed(request)

    @abc.abstractmethod
    def data(self,request):
        """ Generate data to return to the user.

        *request* (server.Request)
            The client request.

        Return a python object to serialize. """

        return None

    def get_json(self,request):
        """ Handle a GET request with accept="application/json"."""
        data=self.data(request)
        response=responses.JsonResponse(data)
        return response

class ActionPage(Page,abc.ABC):
    """Abstract class for pages requesting an action.

    *server* (server.IsambardServer)
        The server.

    An  ActionPage  implements  the PRG  (post/redirect/get)  pattern:
    after doing an  action, it returns a  `RedirectResponse`. The only
    method accepted is POST.

    HTTP  method  accepted:

       POST, served  by `self.post()`. 

    Response:

        `responses.RedirectResponse`.

    Exception:

        `Http405MethodNotAllowed`
             if the http method is not *POST*.

    """

    _success_url="/"

    def get_handler(self,request):
        if request.method!="POST":
            raise Http405MethodNotAllowed(request)
        return self.post
    
    @abc.abstractmethod
    def action(self,request):
        """ Perform action requested by the user.

        *request* (server.Request)
            The client request. """
        pass

    def post(self,request):
        """ Handle a POST request."""
        self.action(request)
        response=responses.RedirectResponse(self._success_url)
        return response



