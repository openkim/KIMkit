import os
import subprocess
from setuptools import setup, find_packages
from distutils.command.install import INSTALL_SCHEMES

for scheme in INSTALL_SCHEMES.values():
    scheme["data"] = scheme["purelib"]

setup(
    name="kimkit",
    version="1.1.0",
    author="Claire Waters",
    author_email="bwaters@umn.edu",
    include_package_data=True,
    packages=find_packages(),
    install_requires=["pytz", "kim_edn", "packaging", "pygments", "pymongo", "numpy"],
    setup_requires=["pytz", "kim_edn", "packaging", "pygments", "pymongo", "numpy"],
)
