from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.parser import Parser
from .registry import MacroRegistry
import re


class MacroTagsExtension(Extension):
    tags = set(["macro_tag", "call_macro_tag", "local_macro_tag", "call_local_macro_tag"])
    open_tag_regexp = re.compile(r"<\{\s*([a-zA-Z_0-9]+)")
    close_block_regexp = re.compile(r"</\{(\s*([a-zA-Z_0-9]+)\s*)?\}>")
    tag_closing_str = "}/>"
    block_blosing_str = "}>"

    def __init__(self, environment):
        super().__init__(environment)
        self.cache = {}
        environment.extend(auto_import_macro_tags=True, undefined_macro_tag_fallback=False)

    def preprocess(self, source, name, filename=None):
        macro_defs = set(MacroRegistry.find_macro_defs(source))
        imports = re.findall(r"\{\% from .+ \%\}", source)
        if imports:
            env = self.environment.overlay()
            env.extensions = {}
            for imp in imports:
                parser = Parser(env, imp)
                next(parser.stream)
                for imp_name in parser.parse_from().names:
                    if isinstance(imp_name, tuple):
                        macro_defs.add(imp_name[1])
                    else:
                        macro_defs.add(imp_name)

        found_macros = set()
        orig_source = source
        r = self.open_tag_regexp.search(orig_source)
        if r:
            source = ""
            pos = 0
            while r:
                name = r.group(1).replace("-", "_")
                source += orig_source[pos : r.start()]
                pos = r.end()
                close_pos, close_char = find_closing(
                    orig_source, (self.block_blosing_str, self.tag_closing_str), pos
                )
                if close_pos == -1:
                    raise Exception("Missing closing bracket for %s" % name)
                macro_tag_type = "local_macro_tag"
                if name not in macro_defs:
                    found_macros.add(name)
                    macro_tag_type = "macro_tag"
                func = (
                    f"call_{macro_tag_type}"
                    if close_char == self.block_blosing_str
                    else macro_tag_type
                )
                source += (
                    "{% " + func + " " + name + " " + orig_source[pos:close_pos].strip() + " %}"
                )
                pos = close_pos + len(close_char)
                r = self.open_tag_regexp.search(orig_source, pos)
            source += orig_source[pos:]

        source = self.close_block_regexp.sub(r"{% endmacrotag %}", source)
        return source

    def parse(self, parser):
        is_local = parser.stream.current.test("name:local_macro_tag") or parser.stream.current.test(
            "name:call_local_macro_tag"
        )
        is_block = parser.stream.current.test("name:call_macro_tag") or parser.stream.current.test(
            "name:call_local_macro_tag"
        )
        lineno = next(parser.stream).lineno
        tag_name = parser.stream.current.value
        next(parser.stream)

        call_block_node = nodes.CallBlock()
        if is_block and parser.stream.current.test("lparen"):
            parser.parse_signature(call_block_node)

        args, kwargs, dyn_args, dyn_kwargs = self.parse_call_args(parser)

        import_from = None
        macro_name = None
        if not is_local:
            macro_name, import_from = self.resolve_macro(tag_name)

        if not macro_name and not is_local and self.environment.undefined_macro_tag_fallback:
            macro_name, import_from = self.resolve_macro(
                self.environment.undefined_macro_tag_fallback
            )
            if not macro_name:
                raise Exception("Macro tag fallback was not found")
            if args:
                raise Exception(
                    "Cannot use unnamed args with macro tags when fallbacking to html tags"
                )
            args = [nodes.Const(tag_name)]
        elif not macro_name:
            macro_name = tag_name

        out = []
        if import_from and self.environment.auto_import_macro_tags:
            out.append(
                nodes.FromImport(nodes.Const(import_from), [macro_name], True, lineno=lineno)
            )

        call = nodes.Call(
            nodes.Name(macro_name, "load"), args, kwargs, dyn_args, dyn_kwargs, lineno=lineno
        )
        if is_block:
            body = parser.parse_statements(["name:endmacrotag"], drop_needle=True)
            out.append(
                nodes.CallBlock(
                    call,
                    getattr(call_block_node, "args", []),
                    getattr(call_block_node, "defaults", {}),
                    body,
                    lineno=lineno,
                )
            )
        else:
            out.append(nodes.Output([call]))

        return out

    def resolve_macro(self, tag_name):
        if hasattr(self.environment, "macros"):
            return self.environment.macros.resolve(tag_name)
        return tag_name, None

    def parse_call_args(self, parser):
        args = []
        kwargs = []
        dyn_args = None
        dyn_kwargs = None

        def ensure(expr: bool) -> None:
            if not expr:
                parser.fail("invalid syntax for macro tag expression", parser.stream.current.lineno)

        while parser.stream.current.type != "block_end":
            if parser.stream.current.type == "mul":
                ensure(dyn_args is None and dyn_kwargs is None)
                next(parser.stream)
                dyn_args = parser.parse_expression()
            elif parser.stream.current.type == "pow":
                ensure(dyn_kwargs is None)
                next(parser.stream)
                dyn_kwargs = parser.parse_expression()
            else:
                if parser.stream.current.type == "name" and parser.stream.look().type == "assign":
                    ensure(dyn_kwargs is None)
                    key = parser.stream.current.value
                    parser.stream.skip(2)
                    if parser.stream.skip_if("lparen"):
                        value = parser.parse_expression()
                        parser.stream.expect("rparen")
                    else:
                        value = parser.parse_unary()
                    kwargs.append(nodes.Keyword(key, value, lineno=value.lineno))
                else:
                    ensure(dyn_args is None and dyn_kwargs is None and not kwargs)
                    args.append(parser.parse_unary())

        return args, kwargs, dyn_args, dyn_kwargs


def find_closing(source, chars, start=0):
    str_open_pos, str_open_char = find_next_char(source, ("'", '"'), start)
    next_char_pos, next_char = find_next_char(source, chars, start)
    if next_char_pos == -1:
        return (-1, "")
    if str_open_pos == -1 or next_char_pos < str_open_pos:
        return (next_char_pos, next_char)

    pos = str_open_pos + 1
    while True:
        str_close = source.find(str_open_char, pos)
        if str_close == -1:
            return (-1, "")
        if source[str_close - 1] == "\\":  # character is escaped
            pos = str_close + 1
        else:
            break
    return find_closing(source, chars, str_close + 1)


def find_next_char(source, chars, start=0):
    indexes = [(c, source.find(c, start)) for c in chars]
    min_index = None
    char = None
    for c, i in indexes:
        if i > -1 and (min_index is None or i < min_index):
            min_index = i
            char = c
    if min_index is None:
        return (-1, "")
    return (min_index, char)
