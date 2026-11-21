DEFS_DIR = "scripts/entity_defs/"
INTERFACES_DIR = DEFS_DIR + "interfaces/"


def _child_names(section, name):
    child = section[name]
    return list(child.keys()) if child is not None else []


def _interfaces(section):
    implements = section["Implements"]
    if implements is None:
        return []
    return [value.asString.strip() for value in implements.values()]


def engine_method_names(def_name, open_section):
    """Client methods and property setters the engine calls for one entity type."""
    names = set()
    pending = [DEFS_DIR + def_name + ".def"]
    seen = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        section = open_section(path)
        if section is None:
            continue
        names.update(_child_names(section, "ClientMethods"))
        for prop in _child_names(section, "Properties"):
            names.add("set_" + prop)
            names.add("setSlice_" + prop)
            names.add("setNested_" + prop)
        pending.extend(INTERFACES_DIR + name + ".def" for name in _interfaces(section))
    return names


def def_name_for(cls):
    name = cls.__name__
    if name.startswith("Player") and len(name) > len("Player"):
        return name[len("Player"):]
    return name
