
def test_tag(env):
    env.macros.register_from_template("__macros__.html")
    tpl = env.get_template("tags.html")
    html = tpl.render()
    assert '<div class="panel-title">test panel</div>' in html
    assert '<div><button type="button" class="btn btn-default">click me</button></div>' in html
    assert '<button type="button" class="btn btn-primary">click me</button>' in html


def test_tag_with_macro(env):
    tpl = env.get_template("tag_with_macro.html")
    html = tpl.render()
    assert html == "\n<pre><code>1 + 2</code></pre>"


def test_tag_with_import(env):
    tpl = env.get_template("tag_with_import.html")
    html = tpl.render()
    assert html == "\n"+'<button type="button" class="btn btn-default">click me</button>'