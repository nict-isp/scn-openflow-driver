=============
Installation
=============

Install dependent libraries
-----------------------------

.. _Python: http://www.python.org
.. _pip: https://pip.pypa.io/
.. _setuptools: https://pypi.python.org/pypi/setuptools
.. _twisted: https://twistedmatrix.com/trac/
.. _fluent-logger: http://www.fluentd.org/
.. _POX: http://www.noxrepo.org/pox/about-pox/


Before installing SCN OpenFlow Driver, the following libraries must be installed.

#.  `Python`_ ver. 2.7

#.  `pip`_ ,`setuptools`_ Package management tool of Python. setuptools will be installed when pip is installed automatically.

#.  `twisted`_ Even driven network programming framework described by Python.

#.  `fluent-logger`_ Fluentd logger library for Python

#.  `POX`_ OpenFlow controller with installing Python


Install SCN OpenFlow Driver
----------------------------------

*  Install POX.

::

    $ git clone https://github.com/noxrepo/pox.git


*  Copy source code from GitHub repository.

::

    $ cd pox
    $ git clone git://github.com/nict-isp/scn-openflow-driver.git
    $ mv scn-openflow-driver ext


Installation procedure for the platform
---------------------------------------

Ubuntu 12.0 or above
^^^^^^^^^^^^^^^^^^^^

*   Install `twisted`_ and `fluent-logger`_ .

    ::

        $ sudo pip install twisted fluent-logger


