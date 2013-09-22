from setuptools import setup
from subprocess import Popen, PIPE
from time import gmtime, strftime

setup(
    name="ttftree",
    version="0.2.1",
    description="A 2-3 finger tree library for Python",
    author="Alexander Boyd",
    author_email="alex@opengroove.org",
    modules=["ttftree"]
)
