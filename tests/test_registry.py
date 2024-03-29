import os


def test_register_macro_from_template(env):
    env.macros.register_from_template("__macros__.html")
    assert env.macros.exists("panel")


def test_register_macro_from_env(env):
    env.macros.register_from_env()
    assert env.macros.exists("panel")


def test_register_macro_from_file(env, templates_path):
    env.macros.register_from_file(os.path.join(templates_path, "__macros__.html"))
    assert env.macros.exists("panel")


def test_create_from_template(env):
    env.macros.create_from_template("codeblock.macro.html")
    assert env.macros.exists("codeblock")
    assert env.macros.codeblock(caller=lambda: "1 + 2") == "<pre><code>1 + 2</code></pre>"


def test_create_from_env(env):
    env.macros.create_from_env()
    assert env.macros.exists("codeblock")
