#!/usr/bin/env python3

import sys
import os
import pydoc
import inspect
import collections
import json

import docutils.core

OUT_DIR=os.path.abspath(os.path.join(os.path.dirname(__file__), "docs","_modules"))

CLASS_TREE_FILE=os.path.abspath(os.path.join(os.path.dirname(__file__), "docs","assets","json","class_tree.json"))

class TargetDoc(object):
    def __init__(self,name,target):
        self.name=name
        self.doc=inspect.getdoc(target)
        if self.doc is None: self.doc=""
        self.signature=None
        self._target=target
        self.lines,self.line_no=inspect.getsourcelines(target)

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

        self.classes.sort(key=lambda x: x.line_no)
        self.functions.sort(key=lambda x: x.line_no)

        #self.tree=inspect.getclasstree([c._target for c in self.classes])

    def class_tree(self):
        ret=[]
        for c in self.classes:
            ret+=c.recursive_tree()
        return ret

    def class_tree_data(self,tree=None):
        if tree is None:
            tree=self.class_tree()
        links=set()
        mod_nodes=collections.OrderedDict()
        ext_nodes=collections.OrderedDict()

        for cname,cls,parents in tree:
            if cname=="object": continue
            if cname in ext_nodes: del(ext_nodes[cname])
            mod_nodes[cname]={"id": cname}
            for pname,pcls,pparents in parents:
                if pname=="object": continue
                links.add( (pname,cname) )
            p_mod_nodes,p_ext_nodes,p_links=self.class_tree_data(parents)
            links=links.union(p_links)
            for mnode in p_mod_nodes:
                if mnode["id"] in mod_nodes: continue
                if mnode["id"] in ext_nodes: continue
                ext_nodes[mnode["id"]]=mnode
            for mnode in p_ext_nodes:
                if mnode["id"] in mod_nodes: continue
                if mnode["id"] in ext_nodes: continue
                ext_nodes[mnode["id"]]=mnode

        mod_nodes=list(mod_nodes.values())
        ext_nodes=list(ext_nodes.values())

        return mod_nodes,ext_nodes,links

    def _str_signature(self): return ""

    def print_doc(self,prefix=""):
        TargetDoc.print_doc(self,prefix=prefix)
        for f in self.functions:
            f.print_doc(prefix=prefix+"    ")
        for c in self.classes:
            c.print_doc(prefix=prefix+"    ")


    # def tree_html(self,tree=None):
    #     if tree is None: tree=self.tree
    #     print(type(self.tree))
    #     ret="<ul>"
    #     k=tree[0]
    #     children=tree[1]
    #     print(k)
    #     cl,parents=k
    #     parstr=",".join([c.__name__ for c in parents])
    #     ret+="<li>%s(%s)" % (cl.__name__,parstr)
    #     if children:
    #         ret+=self.tree_html(children)
    #     ret+="</li>\n"
            
    #     ret+="</ul>"
    #     return ret
            
    def html(self):
        ret="<h1 class='title'>"+self.name+"</h1>\n"
        ret+="<section>\n"
        ret+="%s</section>\n" % self.doc_html

        if self.functions:
            ret+="<section>\n"
            ret+="<h1>Functions</h1>\n"
            for f in self.functions:
                ret+="<section>\n"
                ret+=f.html(level=2)
                ret+="</section>\n" 
            ret+="</section>\n" 

        if self.classes:
            ret+="<section>\n"
            ret+="<h1>Classes</h1>\n"
            for c in self.classes:
                ret+="<section>\n"
                ret+=c.html(level=2)
                ret+="</section>\n" 
            ret+="</section>\n" 

        return ret

    def write_doc(self):
        with open(self.fpath,"w") as fd:
            fd.write("---\n")
            fd.write("name: %s\n" % self.name)
            fd.write("---\n")
            fd.write(self.html())
        
class ClassDoc(TargetDoc):
    def __init__(self,name,target):
        TargetDoc.__init__(self,name,target)
        self.signature=None
        self.classes=self._get_classes()
        self.methods=self._get_functions()
        self.signature=inspect.signature(target.__init__)
        self.parents=[ self.fullname(c) for c in target.__bases__ ]
        self.tree=self.build_tree(target)

    def recursive_tree(self):
        ret=[ (self.fullname(self._target),self._target,self.build_tree(self._target)) ]
        for c in self.classes:
            ret+=c.recursive_tree()
        return ret

    def build_tree(self,target):
        ret=[]
        parents=target.__bases__
        for p in parents:
            if p is object: 
                #ret.append( (self.fullname(p),p,[]) )
                continue
            ret.append( (self.fullname(p),p,self.build_tree(p)) )
        return ret
        
    def html_tree(self,tree=None):
        if tree is None:
            tree=self.build_tree(self._target)
        ret="<ul>"
        for name,p,parents in tree:
            ret+="<li>"+".".join(name)
            if parents:
                ret+=self.html_tree(parents)
            ret+="</li>"
        ret+="</ul>"
        return ret

    def fullname(self,cls):
        # o.__module__ + "." + o.__class__.__qualname__ is an example in
        # this context of H.L. Mencken's "neat, plausible, and wrong."
        # Python makes no guarantees as to whether the __module__ special
        # attribute is defined, so we take a more circumspect approach.
        # Alas, the module name is explicitly excluded from __qualname__
        # in Python 3.
        
        module = cls.__module__
        if module is None or module == str.__class__.__module__:
            return (cls.__qualname__,)  # Avoid reporting __builtin__
        else:
            return (module,cls.__qualname__)

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

    def html(self,level=1):
        ret="<h%(level)d class='title'>%(name)s%(sign)s</h%(level)s>\n" % {"level": level, "name": self.name,"sign": self.signature} 
        ret+="<section>\n"
        ret+="%s\n" % self.doc_html
        ret+="</section>\n"

        ret+="<section>\n"
        ret+="<h%(level)d>Parents</h%(level)d>\n" % {"level": level, "name": self.name} 
        ret+="<p>Bases: %s</p>" % ", ".join([ ".".join(p) for p in  self.parents ])
        ret+=self.html_tree()
        ret+="</section>\n"


        if self.methods:
            ret+="<section>\n"
            ret+="<h%(level)d>Methods</h%(level)d>\n" % {"level": level, "name": self.name} 
            for f in self.methods:
                ret+="<section>\n"
                ret+=f.html(level=level+1)
                ret+="</section>\n" 
            ret+="</section>\n" 

        if self.classes:
            ret+="<section>\n"
            ret+="<h%(level)d>Classes</h%(level)d>\n" % {"level": level, "name": self.name} 
            for c in self.classes:
                ret+="<section>\n"
                ret+=c.html(level=level+1)
                ret+="</section>\n" 
            ret+="</section>\n" 

        return ret


class FunctionDoc(TargetDoc):
    def __init__(self,name,target):
        TargetDoc.__init__(self,name,target)
        self.signature=inspect.signature(target)

    def html(self,level=1):
        ret="<h%(level)d class='title'>%(name)s%(sign)s</h%(level)s>\n" % {"level": level, "name": self.name,"sign": self.signature} 
        #ret="<h1 class='title'>"+self.name+"</h1>\n"
        ret+="<section>\n"
        ret+="%s</section>\n" % self.doc_html
        return ret


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
    mod.write_doc()

colors={
    "python": { "fg":"#909090", "bg": "#f0f0f0" },
    "default": { "fg":"#000000", "bg": "#ffffff" },
    "microdaemon.pages": { "fg": "#009000", "bg": "#e0ffa0" },
    "microdaemon.database": { "fg": "#900070", "bg": "#ffb0f0" },
    "microdaemon.configclass": { "fg": "#900000", "bg": "#ffe0a0" },
    "microdaemon.abstracts": { "fg": "#303040", "bg": "#e8e8f0" },
    "microdaemon.configurator": { "fg": "#202070", "bg": "#c0d0ff" },
    "microdaemon.server": { "fg": "#000000", "bg": "#ffffff" },
    "microdaemon.channels": { "fg": "#900000", "bg": "#ffe0e0" },
    "microdaemon.responses": { "fg": "#406070", "bg": "#b0ffff" },
    "microdaemon.common": { "fg": "#402070", "bg": "#d0c0ff" },
    "microdaemon.threads": { "fg": "#904000", "bg": "#ffff90" },
    "microdaemon.jsonlib": { "fg": "#209040", "bg": "#c0ffd0" },
}

nodes=collections.OrderedDict()
links=set()

for mod in modlist:
    if mod.name in colors:
        color=mod.name
    else:
        color="default"

    mod_nodes,ext_nodes,mod_links=mod.class_tree_data()
    links=links.union(mod_links)

    for mnode in ext_nodes:
        if mnode["id"] in nodes: continue
        mnode["color"]="python"
        nodes[mnode["id"]]=mnode

    for mnode in mod_nodes:
        if mnode["id"] not in nodes:
            mnode["color"]=color
            nodes[mnode["id"]]=mnode
            continue
        #if nodes[mnode["id"]]["color"]=="python":
        nodes[mnode["id"]]["color"]=color

nodes=list(nodes.values())
for node in nodes: 
    node["color"]=colors[node["color"]]
    if len(node["id"])==1:
        node["name"]=node["id"][0]
        node["module"]="__builtin__"
    else:
        node["name"]=node["id"][1]
        node["module"]=node["id"][0]
    node["id"]=".".join(node["id"])

links=[ {"source":".".join(s), "target":".".join(t)} for s,t in links ]

data={
    "nodes": nodes, "links": links
}
        

with open(CLASS_TREE_FILE,"w") as fd:
    json.dump(data,fd)
        

