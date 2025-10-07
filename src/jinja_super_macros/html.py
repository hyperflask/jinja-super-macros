from markupsafe import Markup


def html_tag(tagname, attrs=None, inner=None, **kwargs):
    attrs = html_attrs(attrs, **kwargs)
    source = "<%s%s>" % (tagname, " " + attrs if attrs else "")
    if inner is None:
        return Markup(source)
    return Markup(f"{source}{inner}</{tagname}>")


def html_attrs(attrs=None, class_=None, class__=None, **kwargs):
    attrs = dict(attrs or {})
    attrs.update(kwargs)
    classes = html_class(class__, class_, kwargs.pop("class", None), attrs.pop("class", None))
    if classes:
        attrs["class"] = classes
    html = []
    for k, v in attrs.items():
        if v is None:
            continue
        if k.endswith("_"):
            k = k[:-1]
        k = k.replace("_", "-")
        if isinstance(v, bool):
            if v:
                html.append(k)
        else:
            html.append('%s="%s"' % (k, str(v).strip()))
    return Markup(" ".join(html))


def html_class(*args, **kwargs):
    classes = set()
    for c in args:
        if not c:
            continue
        if isinstance(c, dict):
            kwargs.update(c)
        elif isinstance(c, (list, tuple, set)):
            classes.update(c)
        elif c:
            classes.update(c.split(" "))
    classes.update([c for c, v in kwargs.items() if v])
    return " ".join(classes)
