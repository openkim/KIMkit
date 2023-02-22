from setuptools import setup, find_packages

setup(
    name="KIMkit",
    version="0.1",
    description="KIM Interatomic Model storage and management system",
    author="Brendon Waters",
    author_email="bwaters@umn.edu",
    packages=find_packages("KIMkit"),
    install_requires=["pytz", "kim_edn", "packaging", "pygments"],
)
