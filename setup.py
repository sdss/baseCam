# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['basecam', 'basecam.actor']

package_data = \
{'': ['*']}

install_requires = \
['astropy>=3.2.1,<4.0.0',
 'numpy>=1.17,<2.0',
 'sdss-clu @ git+https://github.com/sdss/clu@master',
 'sdsstools>=0.1.0,<0.2.0']

setup_kwargs = {
    'name': 'sdss-basecam',
    'version': '0.1.0a0',
    'description': 'A base library for camera wrapping and actor.',
    'long_description': 'basecam\n=======\n\n![Versions](https://img.shields.io/badge/python-3.8-blue)\n[![Documentation Status](https://readthedocs.org/projects/sdss-basecam/badge/?version=latest)](https://sdss-basecam.readthedocs.io/en/latest/?badge=latest)\n[![Travis (.org)](https://img.shields.io/travis/sdss/basecam)](https://travis-ci.org/sdss/basecam)\n[![Coverage Status](https://codecov.io/gh/sdss/basecam/branch/master/graph/badge.svg)](https://codecov.io/gh/sdss/basecam)\n\n``basecam`` provides a wrapper around CCD camera APIs with an SDSS-style TCP/IP actor. The main benefits of using `basecam` are:\n\n- Simplifies the creation of production-level camera libraries by providing all the common boilerplate so that you only need to focus on implementing the parts that are specific to your camera API.\n\n- Provides a common API regardless of the underlying camera being handled.\n\n- Powerful event handling and notification.\n',
    'author': 'José Sánchez-Gallego',
    'author_email': 'gallegoj@uw.edu',
    'maintainer': None,
    'maintainer_email': None,
    'url': 'https://github.com/sdss/basecam',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'python_requires': '>=3.7,<4.0',
}


setup(**setup_kwargs)

# This setup.py was autogenerated using poetry.
