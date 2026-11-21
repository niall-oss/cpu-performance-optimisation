import functools


def code_key(code, owner=""):
    return (code.co_filename, code.co_firstlineno, code.co_name, owner)


def _unwrap(fn):
    while True:
        if isinstance(fn, functools.partial):
            fn = fn.func
            continue
        # common/WeakMethod.py WeakMethodProxy, the usual event delegate.
        method_ref = getattr(fn, "_methodRef", None)
        if method_ref is not None:
            target = method_ref()
            if target is not None:
                fn = target
                continue
        return fn


def callable_key(fn):
    fn = _unwrap(fn)

    func = getattr(fn, "__func__", None)
    if func is not None:
        bound_to = fn.__self__
        if bound_to is None:
            owner = ""
        elif isinstance(bound_to, type):
            owner = bound_to.__name__
        else:
            owner = type(bound_to).__name__
        return code_key(func.__code__, owner)

    code = getattr(fn, "__code__", None)
    if code is not None:
        return code_key(code)

    call = getattr(type(fn), "__call__", None)
    code = getattr(getattr(call, "__func__", call), "__code__", None)
    if code is not None:
        return code_key(code, type(fn).__name__)
    return ("<native>", 0, getattr(fn, "__name__", repr(type(fn))), "")


def describe(key):
    filename, line, name, owner = key
    qualified = owner + "." + name if owner else name
    return "%s (%s:%d)" % (qualified, filename, line)
