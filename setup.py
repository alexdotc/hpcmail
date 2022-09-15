from setuptools import setup
from setuptools import find_packages

setup(
    name='hpcmail',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'psutil',
        'paramiko',
    ],
)
