=============
インストール
=============

依存ライブラリのインストール
-----------------------------

.. _Python: http://www.python.org
.. _pip: https://pip.pypa.io/
.. _setuptools: https://pypi.python.org/pypi/setuptools
.. _twisted: https://twistedmatrix.com/trac/
.. _fluent-logger: http://www.fluentd.org/
.. _POX: http://www.noxrepo.org/pox/about-pox/


SCN OpenFlow Driverの前に、以下のライブラリをインストールする必要があります。

#.  `Python`_ バージョン2.7。

#.  `pip`_ 、`setuptools`_ Pythonのパッケージ管理ツール。 `setuptools`_ は、 `pip`_ のインストール時に自動でインストールされます。

#.  `twisted`_ Pythonで記述されたイベント駆動型のネットワークプログラミングフレームワーク。

#.  `fluent-logger`_ Python用のFluentdロガーライブラリ。

#.  `POX`_ Python実装によるOpenFlowコントローラ。



SCN OpenFlow Driverのインストール
----------------------------------

*  POXのインストール。

::

    $ git clone https://github.com/noxrepo/pox.git


*  GitHubリポジトリからソースコードをコピーします。

::

    $ cd pox
    $ git clone git://github.com/nict-isp/scn-openflow-driver.git
    $ mv scn-openflow-driver ext


プラットフォーム別のインストール手順
-------------------------------------

Ubuntu 12.0 以上
^^^^^^^^^^^^^^^^^

*   `twisted`_ 、 `fluent-logger`_ のインストール。
    ::

        $ sudo pip install twisted fluent-logger


