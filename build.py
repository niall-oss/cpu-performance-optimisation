from zipfile import ZipFile
from argparse import ArgumentParser
from py_compile import compile
import xml.etree.ElementTree as ET
import os
import sys

USERNAME = "ANIALLATOR"

# "release": published as a GitHub Release when master is pushed. The
# profiler is only ever a CI artifact.
MODS = {
    "profiler": {
        "name": "CPU Profiler",
        "version": "0.2.0",
        "description": "Records frame times, Python time per entry point and lag spikes "
        "during a battle or replay. Development tool, not for distribution.",
        "folder": "profiler/res",
        "release": False,
    },
}

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(PROJECT_DIR, "build")


def mod_id(mod):
    return USERNAME + "." + mod["name"].replace(" ", "_")


def package_path(mod, version):
    return os.path.join(BUILD_DIR, mod_id(mod) + "_" + version + ".wotmod")


def _add_folder(zip_file, folder, res_folder):
    for elem in sorted(os.listdir(folder)):
        full_path = os.path.join(folder, elem)
        if os.path.isdir(full_path):
            _add_folder(zip_file, full_path, res_folder)
            continue
        archive_path = "res/" + os.path.relpath(full_path, res_folder).replace("\\", "/")
        if os.path.splitext(full_path)[1] == ".py":
            compile(full_path, doraise=True)
            pyc_path = full_path + "c"
            zip_file.write(pyc_path, archive_path + "c")
            os.remove(pyc_path)
        else:
            zip_file.write(full_path, archive_path)


def build(key, version=None):
    mod = MODS[key]
    version = version or mod["version"]

    root = ET.Element("root")
    ET.SubElement(root, "id").text = mod_id(mod)
    ET.SubElement(root, "version").text = version
    ET.SubElement(root, "name").text = mod["name"]
    ET.SubElement(root, "description").text = mod["description"]

    res_folder = os.path.join(PROJECT_DIR, os.path.normpath(mod["folder"]))
    if not os.path.isdir(res_folder):
        raise ValueError("Incorrect path to a res folder: %s" % res_folder)
    if not os.path.exists(BUILD_DIR):
        os.mkdir(BUILD_DIR)

    meta_path = os.path.join(BUILD_DIR, "meta.xml")
    ET.ElementTree(root).write(meta_path)
    path = package_path(mod, version)
    package = ZipFile(path, "w")
    package.write(meta_path, "meta.xml")
    _add_folder(package, res_folder, res_folder)
    package.close()
    os.remove(meta_path)
    print("Built %s" % path)


def print_release_outputs():
    """GITHUB_OUTPUT lines for the mod to release, or nothing if none is."""
    for key in sorted(MODS):
        mod = MODS[key]
        if mod["release"]:
            relative = os.path.relpath(package_path(mod, mod["version"]), PROJECT_DIR)
            print("version=%s" % mod["version"])
            print("wotmod=%s" % relative.replace("\\", "/"))
            return


def main():
    parser = ArgumentParser()
    parser.add_argument("mod", nargs="?", choices=sorted(MODS) + ["all"], default="all",
                        help="Which mod to build (default: all)")
    parser.add_argument("-v", "--version", help="Override the mod version")
    parser.add_argument("--release-outputs", action="store_true",
                        help="Print the release mod's version and path for GitHub Actions")
    args = parser.parse_args()

    if args.release_outputs:
        print_release_outputs()
        return

    if sys.version_info[:2] != (2, 7):
        sys.stderr.write(
            "Error: Python 2.7 is required to compile WoT mod bytecode.\n"
            "Install Python 2.7.18 from https://www.python.org/downloads/release/python-2718/\n"
            "Then run: C:\\Python27\\python.exe build.py [mod]\n"
        )
        sys.exit(1)

    keys = sorted(MODS) if args.mod == "all" else [args.mod]
    for key in keys:
        build(key, args.version)


main()
