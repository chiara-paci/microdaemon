#!/usr/bin/env python3

import sys
import os
import pydoc
import inspect

import docutils.core



OUT_DIR=os.path.abspath(os.path.join(os.path.dirname(__file__), "docs","_modules"))

class TargetDoc(object):
    def __init__(self,name,target):
        self.name=name
        self.doc=inspect.getdoc(target)
        if self.doc is None: self.doc=""
        self.signature=None
        self._target=target

    @property
    def header(self):
        return self.name+self._str_signature()

    def print_doc(self,prefix=""):
        print(prefix+self.header)
        print(prefix+"    "+self.doc)

    def _get_classes(self,item=None):
        if item is None:
            item=self._target
        output = list()
        for cl in inspect.getmembers(item, inspect.isclass):
            if cl[0] == "__class__": continue
            if cl[0].startswith("_"): continue
            output.append( ClassDoc(cl[0],cl[1]) )
        return output

    def _get_functions(self,item=None):
        if item is None:
            item=self._target
        output=[]
        for func in inspect.getmembers(item, inspect.isfunction):
            output.append(FunctionDoc(func[0],func[1]))
        return output

    def _str_signature(self):
        if self.signature is None:
            return "()"
        ret=[]
        for param in self.signature.parameters.values():
            if param.name=="self": continue
            ret.append(str(param))
        return "("+",".join(ret)+")"

    @property
    def doc_html(self):
        #t=self.doc.split("\n")
        #ret="\n".join([ "<p>"+x+"</p>" for x in t ]) 
        ret=docutils.core.publish_parts(self.doc, writer_name='html')['html_body']
        return ret

class ModuleDoc(TargetDoc):
    def __init__(self,name,target):
        TargetDoc.__init__(self,name,target)
        self.classes=self._get_classes()
        self.functions=self._get_functions()
        self.fpath=os.path.join(OUT_DIR,self.name+".html")

    def _str_signature(self): return ""

    def print_doc(self,prefix=""):
        TargetDoc.print_doc(self,prefix=prefix)
        for f in self.functions:
            f.print_doc(prefix=prefix+"    ")
        for c in self.classes:
            c.print_doc(prefix=prefix+"    ")

    def html(self):
        ret="<h1>"+self.name+"</h1>"
        ret+="<div>%s</div>" % self.doc_html
        return ret
        
class ClassDoc(TargetDoc):
    def __init__(self,name,target):
        TargetDoc.__init__(self,name,target)
        self.signature=None
        self.classes=self._get_classes()
        self.methods=self._get_functions()

    def _get_functions(self,item=None):
        if item is None:
            item=self._target
        output=[]
        for func in inspect.getmembers(item, inspect.isfunction):
            fdoc=FunctionDoc(func[0],func[1])
            if fdoc.name=="__init__":
                self.signature=fdoc.signature
                continue
            output.append(fdoc)
        return output

    def print_doc(self,prefix=""):
        TargetDoc.print_doc(self,prefix=prefix)
        for f in self.methods:
            f.print_doc(prefix=prefix+"    ")
        for c in self.classes:
            c.print_doc(prefix=prefix+"    ")

class FunctionDoc(TargetDoc):
    def __init__(self,name,target):
        TargetDoc.__init__(self,name,target)
        self.signature=inspect.signature(target)

sys.path.append(os.getcwd())

microdaemon = pydoc.safeimport("microdaemon")

if microdaemon is None:
    print("Module not found")
    sys.exit(1)
    
modlist = [] #getfunctions(microdaemon) + getclasses(microdaemon)

for entry in os.scandir("microdaemon"):
    fname=entry.name
    if fname=="__init__.py": continue
    if not fname.endswith(".py"): 
        continue
    modname="microdaemon.%s" % fname.replace(".py","")
    
    module = pydoc.safeimport(modname)

    if module is None:
        print("Module %s not found" % modname)
        continue
    
    modlist.append(ModuleDoc(modname,module))


for mod in modlist:
    with open(mod.fpath,"w") as fd:
        fd.write("---\n")
        fd.write("name: %s\n" % mod.name)
        fd.write("---\n")

        fd.write(mod.html())

