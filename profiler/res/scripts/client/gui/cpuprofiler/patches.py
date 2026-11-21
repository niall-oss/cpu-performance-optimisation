import types

from gui.cpuprofiler.code_names import callable_key, code_key


class Patches(object):
    def __init__(self):
        self._applied = []

    def __len__(self):
        return len(self._applied)

    def add(self, holder, name, replacement):
        # getattr on a Python 2 class returns an unbound method, not the
        # function that has to be put back.
        original = _own_attribute(holder, name)
        self._applied.append((holder, name, original, replacement))
        setattr(holder, name, replacement)

    def restore_all(self):
        """Undoes every patch except ones another mod has since replaced."""
        while self._applied:
            holder, name, original, replacement = self._applied.pop()
            if _own_attribute(holder, name) is replacement:
                setattr(holder, name, original)


def _own_attribute(holder, name):
    if isinstance(holder, type):
        return vars(holder).get(name)
    return getattr(holder, name, None)


def patch_callback(patches, tracer, bigworld):
    original = bigworld.callback

    def callback(delay, fn, *args, **kwargs):
        key = callable_key(fn)

        def run(*call_args, **call_kwargs):
            return tracer.run("callback", key, fn, call_args, call_kwargs)

        return original(delay, run, *args, **kwargs)

    patches.add(bigworld, "callback", callback)


def patch_events(patches, tracer, event_module):
    """Replaces Event and SafeEvent dispatch with copies that time each handler.

    The loops match common/Event.py; see docs/DECOMPILED_REFERENCE.md.
    """
    log_exception = event_module.LOG_CURRENT_EXCEPTION
    run = tracer.run

    def event_call(self, *args, **kwargs):
        for delegate in self[:]:
            try:
                run("event", callable_key(delegate), delegate, args, kwargs)
            except:  # noqa: E722 - same as the original
                log_exception()
                raise

    def safe_event_call(self, *args, **kwargs):
        for delegate in self[:]:
            try:
                run("event", callable_key(delegate), delegate, args, kwargs)
            except:  # noqa: E722 - same as the original
                log_exception()

    for class_name, replacement in (("Event", event_call), ("SafeEvent", safe_event_call)):
        cls = getattr(event_module, class_name, None)
        if cls is not None and "__call__" in vars(cls):
            patches.add(cls, "__call__", replacement)


def _timed_function(tracer, kind, key, fn):
    def timed(*args, **kwargs):
        return tracer.run(kind, key, fn, args, kwargs)

    return timed


def _defining_class(cls, name):
    for base in cls.__mro__:
        if name in vars(base):
            return base
    return None


def patch_entity_methods(patches, tracer, cls, names, already_patched):
    """Times the methods the engine calls on an entity class.

    Only engine entry points are patched: a public method that is also used
    as an event handler would stop matching on unsubscribe once replaced.
    """
    for name in names:
        owner = _defining_class(cls, name)
        if owner is None or (owner, name) in already_patched:
            continue
        fn = vars(owner)[name]
        if not isinstance(fn, types.FunctionType):
            continue
        already_patched.add((owner, name))
        key = code_key(fn.__code__, owner.__name__)
        patches.add(owner, name, _timed_function(tracer, "entity", key, fn))


def patch_module_functions(patches, tracer, module, names):
    for name in names:
        fn = getattr(module, name, None)
        if isinstance(fn, types.FunctionType):
            key = code_key(fn.__code__, module.__name__)
            patches.add(module, name, _timed_function(tracer, "engine", key, fn))
