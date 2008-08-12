
import glob
import pysvn
import setuptools
from setuptools import setup

# TODO: Add dependencies to:
# SCons, pyreadline
# Ensymble would be nice too but its not included in PyPI :(
c = pysvn.Client()
revision = c.info(".").data["revision"].number
version = '1.0.%d-svn' % revision

setuptools.find_packages(".")

setup(  name='scons_symbian',
        version=version,
        description = 'SCons build toolchain for Symbian OS',
        author = "Jussi Toivola",
        author_email = "jtoivola@gmail.com",
        url = "http://code.google.com/p/scons-for-symbian",
        license = "MIT",
)


# Check if there are any changes and warn about it( SVN Revision won't match )
if c.diff( ".", ".") != "":
    print "WARNING: There are uncommitted changes!!!"
    