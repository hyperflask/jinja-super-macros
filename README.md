# Jinja Super Macros

Jinja Super Macros introduces a new syntax to call macros as well as an automatic macro loader.

## Example

In *app.py*:

    from jinja2 import Environment, PackageLoader
    from jinja_super_macros import configure_environment

    env = Environment(loader=PackageLoader(__name__, 'templates'))
    configure_environment(env)
    env.macros.register_file('macros.html')

    print env.get_template('form.html').render()

In *macros.html*:

    {% macro Form(action) %}
        <form action="{{ action }}" method="post">
            {{ caller() }}
        </form>
    {% endmacro %}

    {% macro FormInput(name) %}
        <input type="text" name="{{ name }}">
    {% endmacro %}

In *templates/form.html*:

    <{Form action="/" }>
        <{FormInput name="email" }/>
    </{Form}>

## Installation

    pip install jinja-super-macros

## Usage

To start using super macros, configure the environment with additional
extensions and settings and register your macros:

    from jinja2 import Environment, PackageLoader
    from jinja_super_macros import configure_environment

    env = Environment(loader=PackageLoader(__name__, 'templates'))
    configure_environment(env)

    env.macros.register_from_template("macros.html")

You can register macros from templates available through your loader:

 - `register_from_template(template)`: register all macros defined in the template
 - `register(name, template)`: register the specified macro located in the template
 - `register_from_env()`: look for macros in all templates:
    - by default, only look in templates named `__macros__.html`
    - pass `filter_func=False` to register fromm ALL templates
    - provide a custom `filter_func` (will receive the template name as argument)

You can also register macros using templates not accessible from your environment loader:

 - `register_file(filename)`
 - `register_directory(path)`
 - `register_package(package_name, package_path='macros')`

## New macro tags syntax

Macro tags allow you to use Jinja's macros with a syntax similar
to html tags. There are two types of macro tags: inline and block.
Inline is the equivalent of calling the macro using `{{ macro_name() }}`
and block is equivalent to the `{% call %}` directive.

Inline directives are enclosed in `<{` and `}/>`. Arguments
can be provided the same was as html attributes but their values are
Jinja expressions.

Inline tag example:

    <{macro_name arg1=value1 arg2=value2 }/>

is equivalent to:

    {{ macro_name(arg1=value1, arg2=value2) }}

Block tags, start with an opening directive enclosed in `<{` and `}>`
and must be closed with a closing directive `</{macro_name}>` (note
that the macro name is optional in the closing directive).

Block tag example:

    <{macro_name arg1=value1 arg2=value2 }>
        my macro content
    </{macro_name}>

is equivalent to:

    {% call macro_name(arg1=value1, arg2=value2) %}
        my macro content
    {% endcall %}

The list of attributes acts almost the same as a function call but with spaces instead of comma. This means that values can be single expressions with no operators or a full expression enclosed in parentheses.

    <{macro_name arg1 arg2 kw_arg1=single_value kw_arg2=("a" if True else "b") **kwargs }/>

By default, when a macro tag is used but no macro is found matching the name,
it will fallback to rendering the html tag:

    <{input type="checkbox" checked=is_checked() }/>

## New ways to define macros

Jinja Super Macros registry's also gives you the possibility to create macros from new sources.

- `create_from_file(filename)`: wrap the content of the file in a macro directive and register it
- `create_from_directory(path)`: create macros from all files in the directory (recursively):
    - by default, only files with the extension `.macro.html`
    - pass `filter_func=False` to register fromm ALL files
    - provide a custom `filter_func` (will receive the template name as argument)
    - files starting with a dot or un underscore are always ignored
- `create_from_global(global_name, macro_name)`: create a macro that calls a context variable
- `create_from_func(func)`: create a macro from a function
- `@env.macros.macro` decorator: create using the decorated function

When creating from files, use `kwargs.something` to access keyword arguments passed to the macro.  
Use `caller()` as usual for inner content.

When creating from function, pass `receive_caller=True` to receive the `caller` argument.