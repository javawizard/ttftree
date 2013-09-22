from setuptools import setup
from subprocess import Popen, PIPE
from time import gmtime, strftime

timestamp = strftime("%Y.%m.%d.%H.%M.%S", gmtime(int(Popen(["git", "log", "-1", "--format=%ct"], stdout=PIPE).communicate()[0])))

setup(
    name="ttftree",
    version="0.1." + timestamp,
    description="A 2-3 finger tree library for Python",
    author="Alexander Boyd",
    author_email="alex@opengroove.org",
    modules=["ttftree"]
)
