import collections
import abc

class HtmlElem(collections.OrderedDict):
    def __init__(self,tag,content=None,attrs=[]):
        self._tag=tag
        self._content=content
        collections.OrderedDict.__init__(self,attrs)

    def __str__(self):
        ret="<%s" % self._tag
        for k in self:
            if self[k] is not None:
                ret+=' %s="%s"' % (k,str(self[k]))
            else:
                ret+=' %s' % (k)
                
        if self._content is not None:
            ret+=">%s</%s>" % (self._content,self._tag)
        else:
            ret+="/>"
        return ret

class AbstractField(abc.ABC):
    def __init__(self,name,value=None,description=None,default=None,subfield=False):
        self.name=name
        self._id="%s_id" % name
        self._title=name.capitalize().replace("_"," ")
        self._value=value
        self._description=description
        self._default=default
        self._subfield=subfield

    @property
    def value(self):
        if self._value is not None:
            return self._value
        return self._default

    @property
    def label(self):
        content=self._title
        elem=HtmlElem("label",content=content,attrs=[ ("for",self._id) ])
        return str(elem)

    def _clone_args(self):
        args=(self.name,)
        kwargs={
            "description": self._description,
            "default": self._default,
            "subfield": self._subfield
        }
        return args,kwargs

    def clone(self,value=None):
        args,kwargs=self._clone_args()
        if value is None:
            kwargs["value"]=self._value
        else:
            kwargs["value"]=value
        return type(self)(*args,**kwargs)

    @property
    def widget(self):
        elem=self._make_widget()
        return str(elem)

    @property
    def description(self):
        ret=""
        if self._description is not None:
            ret=self._description
        if self._default is not None:
            if ret: ret+=", "
            ret+="default: %s" % str(self._default)
        return ret

class InputField(AbstractField):
    _type="text"

    def _make_widget(self):
        elem=HtmlElem("input",attrs=[
            ("data-field_type",self._type),
            ("type",self._type),
            ("name",self.name),
            ("id",self._id)
        ])
        if self._subfield:
            elem["class"]="subfield"
        else:
            elem["class"]="field"
        if self.value is not None:
            elem["value"]=str(self.value)
        return elem


class ObjectField(AbstractField):
    _field_type="object"

    def __init__(self,name,description=None,fields=[]):
        AbstractField.__init__(self,name,description=description)

        self._fields=fields
        for field in self._fields:
            field._subfield=True

    def clone(self,value=None):
        if value is None:
            return type(self)(self.name,description=self._description,fields=self._fields)
        new_fields=[]
        for field in self._fields:
            if field.name in value:
                new_fields.append(field.clone(value=value[field.name]))
            else:
                new_fields.append(field)
        return type(self)(self.name,description=self._description,fields=new_fields)

    @property
    def value(self):
        ret=collections.OrderedDict()
        for field in self._fields:
            ret[field.name]=field.value
        return ret

    def _make_widget_field(self,field):
        th=HtmlElem("th",content=field.label)
        td1=HtmlElem("td",content=field.widget)
        td2=HtmlElem("td",content=field.description)
        tr=HtmlElem("tr",content=str(th)+str(td1)+str(td2))
        tbody=HtmlElem("tbody",content=str(tr))
        return tbody

    def _make_widget(self):
        rows=[]
        for field in self._fields:
            tbody=self._make_widget_field(field)
            rows.append(str(tbody))
        elem=HtmlElem("table",
                      content="".join(rows),
                      attrs=[
                          ("class","field"),
                          ("name",self.name),
                          ("data-field_type",self._field_type),
                          ("id",self._id)
                      ])
        return elem

class ProxyField(ObjectField):
    _field_type="proxy"

    def _create_field(self,name,value_dict,default_dict):
        value=None
        default=None
        if name in value_dict: value=value_dict[name]
        if name in default_dict: default=default_dict[name]
        if name=="type":
            if value is None: value=default
            return ChoiceField("type",[
                "environment",
                "no proxy",
                "authenticate",
                "non authenticate"
            ], value=value)
        if name in [ "host","username","exclude" ]:
            return InputField(name,value=value,default=default)
        if name=="password":
            return PasswordField(name,value=value,default=default)
        if default is None: default=3128
        return NumberField("port",value=value,default=default,
                           value_min=1,value_max=65535,value_step=1)
        
            

    def __init__(self,name,description=None,value=None,default=None):
        fields=[ self._create_field(k,value,default) for k in [ "type","host","port",
                                                                "username","password","exclude" ] ]

        ObjectField.__init__(self,name,description=description,fields=fields)

    def _make_widget_field(self,field):
        tbody=ObjectField._make_widget_field(self,field)
        cl_list=[ "proxy_tbody","authenticate" ]
        if field.name in [ "type" ]:
            cl_list.append("no_proxy")
        if field.name in [ "type","exclude" ]:
            cl_list.append("environment")
        if field.name in [ "type","exclude","host","port"]:
            cl_list.append("non_authenticate")
        tbody["class"]=" ".join(cl_list)
        return tbody

class ChoiceField(AbstractField):
    _field_type="choice"

    def __init__(self,name,object_list,value=None,description=None,subfield=False):
        if type(value) is not list:
            if type(value) is tuple:
                value=list(value)
            else:
                value=[value]
        AbstractField.__init__(self,name,value=value,description=description,subfield=subfield)
        self._object_list=object_list

    def _clone_args(self):
        args=(self.name,self._object_list)
        kwargs={
            "description": self._description,
            "subfield": self._subfield
        }
        return args,kwargs

    def _make_widget(self):
        rows=[]
        for cl in self._object_list:
            elem=HtmlElem("option",
                          content=cl,
                          attrs=[ ("value",cl) ])
            if self._value is not None and cl in self._value:
                elem["selected"]="selected"
            rows.append(str(elem))
        elem=HtmlElem("select",
                      content="".join(rows),
                      attrs=[
                          ("data-field_type",self._field_type),
                          ("name",self.name),
                          ("id",self._id)
                      ])
        if self._subfield:
            elem["class"]="subfield"
        else:
            elem["class"]="field"
        return elem

class ClassField(ChoiceField):
    _field_type="class"

class MultipleChoiceField(ChoiceField):
    _field_type="multiple_choice"

    def _make_widget(self):
        elem=ChoiceField._make_widget(self)
        elem["multiple"]=None
        return elem
 
class UrlField(InputField):
    _type="url"

class PasswordField(InputField):
    _type="text"

class IncludeField(InputField):
    _type="text"

    def __init__(self,file_path,value=None,description=None,subfield=False):
        InputField.__init__(self,"include",value=None,description=None,subfield=False)
        self._file_path=file_path

    def clone(self,value=None):
        if value is None:
            return type(self)(self._file_path,value=self._value,description=self._description,
                              subfield=self._subfield)
        return type(self)(self._file_path,value=value,description=self._description,
                          subfield=self._subfield)

    def _make_widget(self):
        elem=InputField._make_widget(self)
        elem["name"]="__include__"
        return elem

    @property
    def value(self):
        if self._value is not None:
            return self._value
        return self._file_path

class NumberField(InputField):
    _type="number"

    def __init__(self,name,value=None,description=None,default=None,
                 value_min=None,value_max=None,value_step=None,subfield=False):
        InputField.__init__(self,name,value=value,description=description,default=default,subfield=subfield)
        self._value_min=value_min
        self._value_max=value_max
        self._value_step=value_step

    def clone(self,value=None):
        if value is None:
            return type(self)(self.name,value=self._value,description=self._description,default=self._default,
                              value_min=self._value_min,value_max=self._value_max,
                              value_step=self._value_step,subfield=self._subfield)
        return type(self)(self.name,value=value,description=self._description,default=self._default,
                          value_min=self._value_min,value_max=self._value_max,value_step=self._value_step,
                          subfield=self._subfield)
        
    def _make_widget(self):
        elem=InputField._make_widget(self)
        for attr,val in [ ("min",self._value_min),
                          ("max",self._value_max),
                          ("step",self._value_step) ]:
            if val is not None:
                elem[attr]=val
        return elem

class BooleanField(InputField):
    _type="checkbox"

    def _make_widget(self):
        elem=HtmlElem("input",attrs=[
            ("data-field_type","boolean"),
            ("type",self._type),
            ("name",self.name),
            ("id",self._id),
        ])
        if self._subfield:
            elem["class"]="subfield"
        else:
            elem["class"]="field"
        if self.value:
            elem["value"]="true"
            elem["checked"]=None
        return elem

class Configurator(object):
    def reset_params(self):
        self.parameters=[
            BooleanField("debug",value=self._config.DEBUG,default=self._config.default["debug"]),
            BooleanField("daemon",value=self._config.DAEMON,default=self._config.default["daemon"]),

            InputField("host",default=self._config.default["host"],value=self._config.HOST),
            NumberField("port",default=self._config.default["port"],value=self._config.PORT,
                        value_min=1,value_max=65535,value_step=1),

            InputField("pid_file_name",default=self._config.default["pid_file_name"],
                       value=self._config.PID_FILE_NAME),
            InputField("var",value=self._config.VAR_DIR,default=self._config.default["var"]),
            InputField("etc",value=self._config.CONFIG_DIR,default=self._config.default["etc"]),
            InputField("user",value=self._config.USER.pw_name,default=self._config.default["user"].pw_name),
            InputField("group",value=self._config.GROUP.gr_name,default=self._config.default["group"].gr_name),
            InputField("umask",value="%04o" % self._config.UMASK,
                       default="%04o" % self._config.default["umask"]),

            InputField("locale",value=self._config.LOCALE,default=self._config.default["locale"]),
            InputField("time_zone",value=self._config.TZ_LABEL,default=self._config.default["time_zone"]),
        ]


    def __init__(self,config):
        self._config=config
        self.reset_params()

    
