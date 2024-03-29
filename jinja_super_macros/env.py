from .registry import MacroRegistryExtension
from .tags import MacroTagsExtension
from .html import html_attrs, html_class, html_tag


def configure_environment(env, auto_register_macros=False):
    env.globals.update(html_attrs=html_attrs, html_class=html_class)
    env.add_extension(MacroRegistryExtension)
    env.add_extension(MacroTagsExtension)
    register_html_tag_as_macro_tag_fallback(env)
    if auto_register_macros:
        env.macros.register_from_env()
        env.macros.create_from_env()


def register_html_tag_as_macro_tag_fallback(env):
    env.globals.update(html_tag=html_tag)
    env.macros.create_from_global(
        "html_tag", "html_tag_macro", receive_caller=True, resolve_caller=True, caller_alias="inner"
    )
    env.undefined_macro_tag_fallback = "html_tag_macro"
