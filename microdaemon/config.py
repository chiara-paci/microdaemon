# -*- coding: utf-8 -*-

import collections
import collections.abc
import json
import os
import re
import pytz
import datetime
import logging
import logging.config
import sys
import pwd,grp

from . import jsonlib,configurator

class LogConfig(dict):
    def _log_handler_rot(self,fname,formatter="simple"):
        return {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": formatter,
            "filename": os.path.join(self.log_dir,fname),
            "when": "d",
            "interval": 1,
            "backupCount": 3
        }

    def _log_logger(self,*handlers,level="INFO"):
        return {
            "level": level,
            "handlers": handlers,
            "propagate": True
        }

    class ErrorOnlyFilter(logging.Filter):
        def __init__(self): pass
        def filter(self,record):
            if record.levelno >= logging.ERROR:
                return record
            return None

    def __init__(self,config):
        self.log_dir=config.LOG_DIR
        self._config=config
        dict.__init__(self)
        self["version"]=1
        
        self["formatters"]={
            "simple": {
                "format": '%(asctime)s [%(levelname)s] %(message)s',
            },
            "with_logger": {
                "format": '%(asctime)s [%(name)s:%(levelname)s] %(message)s',
            }
        }

        self["filters"]= {
            "error_only": {
                "()": self.ErrorOnlyFilter,
            }
        }

        if self._config.DAEMON:
            console=self._log_handler_rot("console.log",formatter="with_logger")
            console_error=self._log_handler_rot("errors.log",formatter="with_logger")
            console_error["filters"]=[ "error_only" ]
        else:
            console={
                "class": "logging.StreamHandler",
                "formatter": "with_logger",
                "stream": "ext://sys.stdout",
            }
            console_error={
                "class": "logging.StreamHandler",
                "formatter": "with_logger",
                "stream": "ext://sys.stdout",
                "filters": [ "error_only" ],
            }

        self["handlers"]= {
            "console":           console,
            "console_error":     console_error,
            "socketio.log":      self._log_handler_rot("socketio.log"),
            "engineio.log":      self._log_handler_rot("engineio.log"),
            "common.log":        self._log_handler_rot("common.log"),
            "onshow.log":  self._log_handler_rot("onshow.log"),
            "pages_access.log":  self._log_handler_rot("pages_access.log"),
            "pages_error.log":   self._log_handler_rot("pages_error.log"),
            
        }

        self["loggers"]={
            "socketio":                       self._log_logger("socketio.log",level="INFO"),
            "engineio":                       self._log_logger("socketio.log",level="INFO"),
            "isambard_lib.server.onshow":    self._log_logger("onshow.log"),
            "isambard_lib.pages.access":    self._log_logger("pages_access.log"),
            "isambard_lib.pages.error":     self._log_logger("pages_error.log"),
            "root":                           self._log_logger("console","common.log"),
            "": {
                "level": "ERROR",
                "handlers": ["console_error"],
                "propagate": False
            },
        }


class _Config(object):

    class ConfigurationError(Exception): pass

    STATIC_REL_PATH = "static"  #: Static path, relative to base url (=script name in wsgi invocation)
    FAVICON="img/logo-isambard.png" #: Favicon, relative to static path

    TEMPLATE_NAMES = {                           #: Template names
        "homepage":         "index.html",
        "object_list":         "object_list.html",
        "418":              "418.html",
        "error":            "error.html",
        "text":             "text.html",
    }

    ## change even in share/isambard/htdocs static files
    COPY_NAME="Gianozia Orientale"
    COPY_URL="http://www.gianoziaorientale.org"


    def __init__(self):

        self.BASE_DIR=os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.SERVER_NAME="Isambard" #: Server name

        ## daemon
        self.VAR_DIR=self._base_rel("var","isambard")
        self.CONFIG_DIR=self._base_rel("etc","isambard")
        self.CONFIG_FILE=self._config_rel("isambard.conf")
        self.PID_FILE_NAME="isambard.pid"

        self.UID=None
        self.GID=None
        self.UMASK=None

        ## wsgi server
        self.HOST="localhost"
        self.PORT=8001
        
        ## business logic
        self.TZ_LABEL="Europe/Rome"      #: Timezone name
        self.LOCALE="it-IT"              #: Locale definition
        self.DEBUG=False
        self.DAEMON=True

        self.USER=pwd.getpwuid(os.getuid())
        self.GROUP=grp.getgrgid(os.getgid())
        self.UMASK= os.umask(0) # a bit odd, but that's
        os.umask(self.UMASK)

        self.default={
            ## running mode
            "debug": self.DEBUG,
            "daemon": self.DAEMON,
            ## process
            "var": self._base_rel("var"),
            "etc": self._base_rel("etc"),
            "pid_file_name": self.PID_FILE_NAME,
            "user": self.USER,
            "group": self.GROUP,
            "umask": self.UMASK,
            ## wsgi server
            "host": self.HOST,
            "port": self.PORT,
            ## business logic
            "time_zone": self.TZ_LABEL,
            "locale": self.LOCALE,
        }

        self.configurator=configurator.Configurator(self)


    def setup_config(self,options):
        configuration_file=options.conf_file

        with open(configuration_file) as fd:
            try:
                conf=jsonlib.json_fd_load(fd)
            except json.decoder.JSONDecodeError as e:
                raise self.ConfigurationError(e)

        self.CONFIG_FILE=configuration_file

        if options.port is not None:
            self.PORT=options.port
        elif "port" in conf:
            self.PORT=conf["port"]

        if options.host is not None:
            self.HOST=options.host
        elif "host" in conf:
            self.HOST=conf["host"]

        if options.daemon is not None:
            self.DAEMON=options.daemon
        elif "daemon" in conf:
            try:
                self.DAEMON=bool(conf["daemon"])
            except ValueError as e:
                raise self.ConfigurationError(e)

        if "time_zone" in conf:
            self.TZ_LABEL=conf["time_zone"]
            try:
                self.TZ
            except ValueError as e:
                raise self.ConfigurationError(e)

        if "debug" in conf:
            try:
                self.DEBUG=bool(conf["debug"])
            except ValueError as e:
                raise self.ConfigurationError(e)

        if "user" in conf:
            if os.getuid()==0 or os.geteuid()==0:
                if isinstance(conf["user"],int):
                    self.USER=pwd.getpwuid(conf["user"])
                else:
                    self.USER=pwd.getpwnam(conf["user"])

        if "group" in conf:
            if os.getgid()==0 or os.getegid()==0:
                if isinstance(conf["group"],int):
                    self.GROUP=pwd.getgrgid(conf["group"])
                else:
                    self.GROUP=pwd.getgrnam(conf["group"])

        if "umask" in conf:
            try:
                self.UMASK=int(conf["umask"],base=8)
            except ValueError as e:
                raise self.ConfigurationError(e)

        if "locale" in conf:
            self.LOCALE=conf["locale"]

        if "var" in conf:
            if conf["var"].startswith("/"):
                self.VAR_DIR=conf["var"]
            else:
                self.VAR_DIR=self._base_rel(*(conf["var"].split("/")))

            os.makedirs(self.VAR_DIR,exist_ok=True)

        if "etc" in conf:
            if conf["etc"].startswith("/"):
                self.CONFIG_DIR=conf["etc"]
            else:
                self.CONFIG_DIR=self._base_rel(*(conf["etc"].split("/")))

        if "config_dir" in conf:
            if conf["config_dir"].startswith("/"):
                self.CONFIG_DIR=conf["config_dir"]
            else:
                self.CONFIG_DIR=self._base_rel(*(conf["config_dir"].split("/")))

        if "pid_file_name" in conf:
            self.PID_FILE_NAME=conf["pid_file_name"]

        os.makedirs(self._var_rel("run"),exist_ok=True)

        self.configurator.reset_params()

    def setup_log(self):
        os.makedirs(self.LOG_DIR,exist_ok=True)
        logging.basicConfig(level=logging.DEBUG,
                            format="%(asctime)s [%(name)s:%(levelname)s] %(message)s")
        logging.config.dictConfig(LogConfig(self))

    def _base_rel(self,*rel):
        return os.path.join(self.BASE_DIR,*rel)

    def _var_rel(self,*rel):
        return os.path.join(self.VAR_DIR,*rel)

    def _db_rel(self,*rel):
        return os.path.join(self.VAR_DIR,"db",*rel)

    def _config_rel(self,*rel):
        return os.path.join(self.CONFIG_DIR,*rel)

    def _share_rel(self,*rel):
        return os.path.join(self.BASE_DIR,"share","isambard",*rel)

    @property
    def COPY_YEAR(self):
        year=datetime.datetime.today().year
        if year==2018:
            copy_year="2018" 
        else:
            copy_year="2018-%d" % year
        return copy_year

    @property
    def VERSION(self):
        version_file=self._base_rel("VERSION")
        try:
            with open(version_file, "r") as fd:
                version=fd.read().strip()      
        except FileNotFoundError as e:
            version="0.0.1"
        return version

    @property
    def TZ(self):
        return pytz.timezone(self.TZ_LABEL)

    @property
    def LOG_DIR(self): return self._var_rel("log")                     

    @property
    def WORKING_DIR(self): return self.VAR_DIR

    @property
    def PID_FILE(self): return self._var_rel("run",self.PID_FILE_NAME)                     

    @property
    def DATABASE_DIR(self): return self._var_rel("db")                     

    @property
    def DEFAULT_DIR(self): return self._db_rel("default")

    @property
    def PICTURES_DIR(self): return self._db_rel("pictures")

    @property
    def VIDEOS_DIR(self): return self._db_rel("videos")

    @property
    def PRESENTATIONS_DIR(self): return self._db_rel("presentations")

    @property
    def MUSIC_DIR(self): return self._db_rel("music")

    @property
    def TEMPLATE_DIR(self): return self._share_rel("templates")                #: Template dir

    @property
    def STATIC_DIR(self): return self._share_rel("static")                     #: Static dir


sys.modules[__name__]=_Config()
