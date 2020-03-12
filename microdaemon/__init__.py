import sys

name="microdaemon"

from . import configclass

config=configclass.Config()

__all__ = ["abstracts", "channels", "common", "config","configclass",
           "configurator","database","jsonlib","pages",
           "responses","server","threads"]

