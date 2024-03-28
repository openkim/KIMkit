from setuptools import setup, find_packages
from distutils.command.install import INSTALL_SCHEMES

for scheme in INSTALL_SCHEMES.values():
    scheme["data"] = scheme["purelib"]

setup(
    name="kimkit",
    version="0.1",
    description="KIM Interatomic Model storage and management system",
    author="Brendon Waters",
    author_email="bwaters@umn.edu",
    include_package_data=True,
    packages=find_packages(),
    install_requires=["pytz", "kim_edn", "packaging", "pygments","pymongo"],
)
