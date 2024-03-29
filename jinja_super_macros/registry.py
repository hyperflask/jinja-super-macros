from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    PrefixLoader,
    FileSystemLoader,
    PackageLoader,
    DictLoader,
    TemplateNotFound,
    nodes,
)
from jinja2.ext import Extension
import re
import os
import uuid
import inspect


class MacroRegistry:
    macro_regexp = re.compile(r"\{%\s*macro\s+([a-zA-Z_0-9]+)")

    @classmethod
    def find_macro_defs(cls, source):
        for m in cls.macro_regexp.finditer(source):
            yield m.group(1)

    def __init__(self, environment, registry_loader=None):
        self.environment = environment
        self.macro_templates = {}
        self.macros = {}
        self.call_temlates = {}

        environment.macros = self
        environment.macro_registry_default_replace = True
        environment.macro_registry_case_insensitive = False
        environment.macro = self.macro

        if not registry_loader:
            registry_loader = MacroRegistryLoader(environment.loader)
            environment.loader = registry_loader
        self.loader = registry_loader

    def register(self, macro_name, template, alias=None, prefix=None, replace=None):
        if not alias:
            alias = macro_name
        if prefix:
            alias = prefix + alias
        if self.environment.macro_registry_case_insensitive:
            alias = alias.lower()
        if (
            replace is False
            or replace is None
            and not self.environment.macro_registry_default_replace
        ) and alias in self.macros:
            raise Exception(
                "Macro '%s' is already declared in '%s'"
                % (macro_name, self.macro_templates[macro_name])
            )
        self.macro_templates[macro_name] = template
        self.macros[alias] = macro_name
        return alias

    def parse_source(self, source, template, **register_kwargs):
        registered = []
        for name in self.find_macro_defs(source):
            registered.append(self.register(name, template, **register_kwargs))
        return registered

    def register_from_source(self, source, filename=None, **register_kwargs):
        template = self.loader.add_string_template(source, filename)
        return self.parse_source(source, template, **register_kwargs)

    def register_from_template(self, template, **register_kwargs):
        source, _, _ = self.environment.loader.get_source(self.environment, template)
        return self.parse_source(source, template, **register_kwargs)

    def register_from_env(self, extensions=None, filter_func=None, **register_kwargs):
        if not extensions and not filter_func:
            filter_func = lambda tpl: tpl == "__macros__.html"  # noqa
        if filter_func is False:
            filter_func = None
        try:
            templates = self.environment.list_templates(
                extensions=extensions, filter_func=filter_func
            )
        except TypeError:
            return
        registered = []
        for tpl in templates:
            registered.extend(self.register_from_template(tpl, **register_kwargs))
        return registered

    def register_from_env_path(self, path, **register_kwargs):
        return self.register_from_env(
            filter_func=lambda tpl: tpl.strip("/").startswith(path.strip("/")), **register_kwargs
        )

    def register_from_loader(self, loader, loader_prefix=None, filter_func=None, **register_kwargs):
        if loader_prefix:
            loader = PrefixLoader(dict([(loader_prefix, loader)]))
        self.loader.add_macro_loader(loader)
        registered = []
        for tpl in loader.list_templates():
            if filter_func and not filter_func(tpl):
                continue
            registered.extend(
                self.register_from_template(
                    os.path.join(self.loader.prefix, tpl), **register_kwargs
                )
            )
        return registered

    def register_from_file(self, path, path_alias=None, **register_kwargs):
        return self.register_from_loader(FileLoader(path, path_alias), **register_kwargs)

    def register_from_directory(self, path, loader_prefix=None, **register_kwargs):
        return self.register_from_loader(FileSystemLoader(path), loader_prefix, **register_kwargs)

    def register_from_package(
        self, package_name, package_path="macros", loader_prefix=None, **register_kwargs
    ):
        return self.register_from_loader(
            PackageLoader(package_name, package_path), loader_prefix, **register_kwargs
        )

    def create(self, name, source, filename=None, **register_kwargs):
        template = self.loader.add_string_template(wrap_source_as_macro(name, source), filename)
        self.register(name, template, **register_kwargs)
        return name

    def create_from_template(self, template, name=None, **register_kwargs):
        template = self.environment.get_template(template)
        return self.create_from_file(template.filename, name, **register_kwargs)

    def get_macro_name_from_path(self, path):
        return os.path.basename(path).split(".", 1)[0]

    def create_from_env(self, extensions=None, filter_func=None, **register_kwargs):
        if not extensions and not filter_func:
            filter_func = lambda tpl: tpl.endswith(".macro.html")  # noqa
        if filter_func is False:
            filter_func = None
        try:
            templates = self.environment.list_templates(
                extensions=extensions, filter_func=filter_func
            )
        except TypeError:
            return
        created = []
        for tpl in templates:
            created.append(self.create_from_template(tpl, **register_kwargs))
        return created

    def create_from_file(self, filename, name=None, **register_kwargs):
        return self.register_from_loader(
            MacroFileLoader(filename, name or self.get_macro_name_from_path(filename)), **register_kwargs
        )[0]

    def create_from_directory(self, path, filter_func=None, **register_kwargs):
        if filter_func is None:
            filter_func = lambda f: f.endswith(".macro.html")  # noqa
        created = []
        for root, _, files in os.walk(path):
            for f in files:
                if (
                    not f.startswith(".")
                    and not f.startswith("_")
                    and (not filter_func or filter_func(f))
                ):
                    created.append(self.create_from_file(os.path.join(root, f), **register_kwargs))
        return created

    def create_from_global(
        self,
        global_name,
        name,
        receive_caller=False,
        caller_alias="caller",
        resolve_caller=False,
        **register_kwargs,
    ):
        signature = ["*varargs", "**kwargs"]
        if receive_caller:
            signature.insert(
                1,
                "%s=caller%s" % (caller_alias, "() if caller else None" if resolve_caller else ""),
            )
        source = "{{ %s(%s) }}" % (global_name, ", ".join(signature))
        return self.create(name, source, **register_kwargs)

    def create_from_func(self, func, name=None, global_name=None, **kwargs):
        if not global_name:
            global_name = f"__macrofunc__{name or func.__name__}"
        self.environment.globals[global_name] = func
        return self.create_from_global(global_name, name or func.__name__, **kwargs)

    def macro(
        self, func=None, name=None, caller_alias="inner", resolve_caller=True, **register_kwargs
    ):
        def decorator(func):
            if not is_comment_only_func(func):
                self.create_from_func(func, name=name, caller_alias=caller_alias, resolve_caller=resolve_caller, **register_kwargs)
                return self.get(name)
            
            sig = inspect.signature(func)
            macro_name = name or func.__name__
            macro_sig = []
            dyn_args = None
            dyn_kwargs = None
            for param in sig.parameters.values():
                if param.kind == param.VAR_POSITIONAL:
                    dyn_args = param.name
                elif param.kind == param.VAR_KEYWORD:
                    dyn_kwargs = param.name
                else:
                    macro_sig.append(str(param.replace(annotation=param.empty)))
            body = "{%% set %s = caller%s %%}\n%s" % (
                caller_alias,
                "() if caller else ''" if resolve_caller else "",
                inspect.getdoc(func),
            )
            if dyn_args and dyn_args != "varargs":
                body = "{%% set %s = varargs %%}\n%s" % (dyn_args, body)
            if dyn_kwargs and dyn_kwargs != "kwargs":
                body = "{%% set %s = kwargs %%}\n%s" % (dyn_kwargs, body)
            source = "{%% macro %s(%s) -%%}\n%s\n{%%- endmacro %%}" % (
                macro_name,
                ", ".join(macro_sig),
                body,
            )
            template = self.loader.add_string_template(source)
            self.register(macro_name, template, **register_kwargs)
            return self.get(macro_name)

        if func:
            return decorator(func)
        return decorator

    def alias(self, name, alias):
        if self.environment.macro_registry_case_insensitive:
            alias = alias.lower()
        self.macros[alias] = name

    def get_aliases(self, real_name):
        return list([alias for alias, real in self.macros.items() if real == real_name])

    def resolve_name(self, name):
        if self.environment.macro_registry_case_insensitive:
            name = name.lower()
        return self.macros.get(name)

    def resolve(self, name):
        name = self.resolve_name(name)
        if not name:
            return None, None
        tpl = self.macro_templates.get(name)
        if not tpl:
            return None, None
        return name, tpl

    def resolve_template(self, name):
        return self.resolve(name)[1]

    def exists(self, name):
        return name in self.macros

    def __contains__(self, name):
        return self.exists(name)

    def get(self, name):
        name, template = self.resolve(name)
        return MacroCall(self.environment, template, name)

    def __getitem__(self, name):
        return self.get(name)

    def __getattr__(self, name):
        return self.get(name)

    def __iter__(self):
        return [(alias, self.macro_templates[name]) for alias, name in self.macros.items()]
    

class MacroCall:
    def __init__(self, env, template, macro_name):
        self.env = env
        self.template = template
        self.macro_name = macro_name

    def __call__(self, *args, **kwargs):
        template = self.env.get_template(self.template)
        return getattr(template.module, self.macro_name)(*args, **kwargs)


class MacroRegistryLoader(ChoiceLoader):
    def __init__(self, loader=None, prefix="__macros__"):
        self.loader = loader
        self.prefix = prefix
        self.string_templates = {}
        self.macro_loaders = [DictLoader(self.string_templates)]
        self.prefix_loader = PrefixLoader({self.prefix: ChoiceLoader(self.macro_loaders)})
        super().__init__([self.loader, self.prefix_loader])

    def add_macro_loader(self, loader):
        self.macro_loaders.insert(0, loader)

    def add_string_template(self, source, filename=None):
        if not filename:
            filename = f"{uuid.uuid4()}.html"
        self.string_templates[filename] = source
        return os.path.join(self.prefix, filename)


class MacroRegistryExtension(Extension):
    tags = set(["use_macro"])

    def __init__(self, environment):
        super().__init__(environment)
        if not hasattr(environment, "macros"):
            MacroRegistry(environment)

    def parse(self, parser):
        lineno = next(parser.stream).lineno

        args = []
        require_comma = False
        while parser.stream.current.type != "block_end":
            if require_comma:
                parser.stream.expect("comma")
                # support for trailing comma
                if parser.stream.current.type == "block_end":
                    break
            args.append(parser.parse_expression())
            require_comma = True

        if not args:
            return []

        templates = {}
        for arg in args:
            if not isinstance(arg, nodes.Name):
                raise Exception("use_macro expects a list of macro names")
            if not self.environment.macros.exists(arg.name):
                # jinja will raise an error at runtime
                continue
            name, tpl = self.environment.macros.resolve(arg.name)
            if name is None:
                continue
            if tpl == parser.name:
                # macro definition is in the same file as macro call, nothing to import
                pass
            else:
                templates.setdefault(tpl, set())
                templates[tpl].add(name)

        imports = []
        for tpl, macros in templates.items():
            imports.append(nodes.FromImport(nodes.Const(tpl), macros, True, lineno=lineno))

        return imports


class FileLoader(BaseLoader):
    def __init__(self, filename, alias=None):
        self.filename = filename
        alias = alias or os.path.basename(filename)
        if not isinstance(alias, (tuple, list)):
            alias = [alias]
        self.aliases = alias

    def get_source(self, environment, template):
        if template not in self.aliases:
            raise TemplateNotFound(template)
        source = self._get_source()
        mtime = os.path.getmtime(self.filename)
        return source, self.filename, lambda: mtime == os.path.getmtime(self.filename)

    def _get_source(self):
        with open(self.filename) as f:
            return f.read()

    def list_templates(self):
        return self.aliases


class MacroFileLoader(FileLoader):
    def __init__(self, filename, macro_name):
        super().__init__(filename)
        self.macro_name = macro_name

    def _get_source(self):
        source = super()._get_source()
        return wrap_source_as_macro(self.macro_name, source)


def wrap_source_as_macro(name, source):
    return "{%% macro %s() %%}{%% set props = kwargs %%}%s{%% endmacro %%}" % (name, source)


def is_comment_only_func(func):
    """Checks if func is an empty function with only a python doc"""
    doc = inspect.getdoc(func)
    src = inspect.getsource(func).strip(' "\n\r')
    return doc and src.endswith(func.__doc__)