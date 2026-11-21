from zipfile import ZipFile
from argparse import ArgumentParser
from py_compile import compile
import xml.etree.ElementTree as ET
import os
import sys

USERNAME = "ANIALLATOR"

MODS = {
    "profiler": {
        "name": "CPU Profiler",
        "version": "0.2.0",
        "description": "Records frame times, Python time per entry point and lag spikes "
        "during a battle or replay. Development tool, not for distribution.",
        "folder": "profiler/res",
    },
}

parser = ArgumentParser()
parser.add_argument("mod", choices=sorted(MODS), help="Which mod to build")
parser.add_argument("-v", "--version", help="Override the mod version")
args = parser.parse_args()

if sys.version_info[:2] != (2, 7):
    sys.stderr.write(
        "Error: Python 2.7 is required to compile WoT mod bytecode.\n"
        "Install Python 2.7.18 from https://www.python.org/downloads/release/python-2718/\n"
        "Then run: C:\\Python27\\python.exe build.py <mod>\n"
    )
    sys.exit(1)

mod = MODS[args.mod]
version = args.version or mod["version"]
mod_id = USERNAME + "." + mod["name"].replace(" ", "_")

root = ET.Element("root")
ET.SubElement(root, "id").text = mod_id
ET.SubElement(root, "version").text = version
ET.SubElement(root, "name").text = mod["name"]
ET.SubElement(root, "description").text = mod["description"]

project_dir = os.path.dirname(os.path.abspath(__file__))
res_folder = os.path.join(project_dir, os.path.normpath(mod["folder"]))
if not os.path.isdir(res_folder):
    raise ValueError("Incorrect path to a res folder: %s" % res_folder)

build_dir = os.path.join(project_dir, "build")
if not os.path.exists(build_dir):
    os.mkdir(build_dir)

meta_path = os.path.join(build_dir, "meta.xml")
ET.ElementTree(root).write(meta_path)


def add_folder(zip_file, folder):
    for elem in sorted(os.listdir(folder)):
        full_path = os.path.join(folder, elem)
        if os.path.isdir(full_path):
            add_folder(zip_file, full_path)
            continue
        archive_path = "res/" + os.path.relpath(full_path, res_folder).replace("\\", "/")
        if os.path.splitext(full_path)[1] == ".py":
            compile(full_path, doraise=True)
            pyc_path = full_path + "c"
            zip_file.write(pyc_path, archive_path + "c")
            os.remove(pyc_path)
        else:
            zip_file.write(full_path, archive_path)


package_path = os.path.join(build_dir, mod_id + "_" + version + ".wotmod")
package = ZipFile(package_path, "w")
package.write(meta_path, "meta.xml")
add_folder(package, res_folder)
package.close()
os.remove(meta_path)

print("Built %s" % package_path)
