#!/usr/bin/env python

from setuptools import setup

import dbar4gun

setup(name=dbar4gun.__title__,
      version=dbar4gun.__version__,
      description="dbar4gun is a Linux userspace driver for the wiimote.",
      url=dbar4gun.__repo___,
      author=dbar4gun.__author__,
      author_email=dbar4gun.__email__,
      license=dbar4gun.__license__,
      long_description="dbar4gun is a Linux userspace driver for the wiimote.",
      entry_points={
        "console_scripts": ["dbar4gun=dbar4gun.dbar4gun:dbar4gun_run"]
      },
      packages=[
          "dbar4gun",
          "dbar4gun.calibration"
      ],
      install_requires=[
          "evdev>=0.3.0",
          "pyudev>=0.16",
      ],
      classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: Games/Entertainment"
      ]
)

