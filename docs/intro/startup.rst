==========
SCNの起動
==========

OpenFlowスイッチの起動
-----------------------

各OpenFlowスイッチ上で下記のコマンドを実行します。

::

    $ sudo ./ovsdb/ovsdb-server --remote=punix:/usr/local/var/run/openvswitch/db.sock --remote=db:Open_vSwitch,Open_vSwitch,manager_options --private-key=db:Open_vSwitch,SSL,private_key --certificate=db:Open_vSwitch,SSL,certificate --bootstrap-ca-cert=db:Open_vSwitch,SSL,ca_cert --pidfile --detach
    $ sudo ./utilities/ovs-vsctl --no-wait init
    $ bsudo ./vswitchd/ovs-vswitchd --pidfile


各OpenFlowスイッチ上で下記のコマンドを実行します。

::

    $ cd ~/openvswitch-2.1.2
    $ sudo ./utilities/ovs-vsctl add-br ofs1
    $ sudo ./utilities/ovs-vsctl add-port ofs1 eth1.1001
    $ sudo ./utilities/ovs-ofctl mod-port ofs1 eth1.1001 no-flood
    $ sudo ./utilities/ovs-vsctl add-port ofs1 eth1.1002
    $ sudo ./utilities/ovs-ofctl mod-port ofs1 eth1.1002 no-flood
    $ sudo ./utilities/ovs-vsctl add-port ofs1 eth2.2751
    $ sudo ./utilities/ovs-ofctl mod-port ofs1 eth2.2751 no-flood
    $ sudo ./utilities/ovs-vsctl add-port ofs1 eth2.2752
    $ sudo ./utilities/ovs-ofctl mod-port ofs1 eth2.2752 no-flood

    ※上記コマンド中の「ofs1」は、各OpenFlowスイッチノード毎に異なる名前を設定します。



各OpenFlowスイッチ上で下記のコマンドを実行します。


::

    $ sudo ./utilities/ovs-vsctl set-controller ofs1 tcp:172.18.210.255:6633
    $ sudo ./utilities/ovs-vsctl set bridge ofs1 other-config:datapath-id=0000000000000001

    ※上記コマンド中の「ofs1」は、各OpenFlowスイッチノード毎に異なる名前を設定します。



OpenFlowコントローラの起動
---------------------------

OpenFlowコントローラ上で下記のコマンドを実行します。

::

    $ cd ~/pox
    $ ./pox.py --no-cli scn.nwgn --inifile=ext/pox_sample.ini



SCNミドルウェアの起動
---------------------------

サービスノード上で下記のコマンドを実行します。"10.0.1.1"のサービスノードの例を示します。

::

    $ cd ~/scnm/scn/core
    $ ~/.rvm/bin/ruby main.rb 10.0.1.1/24


    ※10.0.1.1/24：自ノードのIPアドレス/サブネットマスク


