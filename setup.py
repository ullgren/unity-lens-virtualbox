#!/usr/bin/env python
#
from distutils.core import setup
#from DistUtilsExtra.command import *
import os

setup(name="unity-lens-vbox",
    version="0.1",
    author="Pontus Ullgren, Fredrik Steen",
    author_email="ullgren@gmail.com, stone4x4@gmail.com",
    url="https://github.com/ullgren/unity-lens-virtualbox",
    license="GNU General Public License (GPL)",
    data_files=[
        ('share/unity/lenses/vbox', ['vbox.lens']),
        ('share/dbus-1/services', ['unity-lens-vbox.service']),
        ('lib/unity-lens-vbox', ['unity-lens-vbox.py']),
    ])
#cmdclass={"build":  build_extra.build_extra, })

os.system('setsid unity')
