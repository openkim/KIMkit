import os
import shutil
import subprocess
import getpass
from setuptools import setup, find_packages
from distutils.command.install import INSTALL_SCHEMES

for scheme in INSTALL_SCHEMES.values():
    scheme["data"] = scheme["purelib"]

setup(
    name="kimkit",
    version="1.0.3",
    author="Claire Waters",
    author_email="bwaters@umn.edu",
    include_package_data=True,
    packages=find_packages(),
    install_requires=["pytz", "kim_edn", "packaging", "pygments", "pymongo", "numpy"],
    setup_requires=["pytz", "kim_edn", "packaging", "pygments", "pymongo", "numpy"],
)

from kimkit import users

# create a kimkit subdirectory in the user's home directory
home_dir = os.path.expanduser("~")
kimkit_dir = os.path.join(home_dir, "kimkit")
os.makedirs(kimkit_dir, exist_ok=True)

# get the paths to the settings files
# relative to this setup script
here = os.path.dirname(os.path.realpath(__file__))
kimkit_root = os.path.join(here, "kimkit")
settings_dir = os.path.join(kimkit_root, "settings")

default_env_file = os.path.join(kimkit_root, "default-environment")
metadata_config_file = os.path.join(settings_dir, "metadata_config.edn")
editors_file = os.path.join(settings_dir, "editors.txt")

# copy settings files into kimkit directory
shutil.copy(metadata_config_file, kimkit_dir)
shutil.copy(editors_file, kimkit_dir)

final_editors_file = os.path.join(kimkit_dir, "editors.txt")

# set user who installed as kimkit administrator
# only they should have read/write permissions to editors.txt
subprocess.check_output(["chmod", "600", final_editors_file])

# add the administrator as an editor
username = users.whoami()
users.add_editor(username)

# copy environment settings file to kimkit dir
NOT_SET_LINE = "KIMKIT_DATA_DIRECTORY=None"

# change name of copy of default-environment to KIMkit-env
kimkit_env_dest = os.path.join(kimkit_dir, "KIMkit-env")

with open(default_env_file, "r") as envfile:
    data = envfile.readlines()

    # set KIMKIT_DATA_DIRECTORY to the new kimkit dir
    for i, line in enumerate(data):
        if NOT_SET_LINE in line:
            line = line.split("=")[0] + "=" + kimkit_dir + "\n"
            data[i] = line

with open(kimkit_env_dest, "w") as outfile:
    outfile.writelines(data)

print("KIMkit has been installed!")
print(f"Access files and settings in {kimkit_dir}")
