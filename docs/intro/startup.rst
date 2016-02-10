============
Starting SCN
============

Starting OpenFlow Switch
------------------------

Run the following commands on each OpenFlow switch.

::

    $ sudo ./ovsdb/ovsdb-server --remote=punix:/usr/local/var/run/openvswitch/db.sock --remote=db:Open_vSwitch,Open_vSwitch,manager_options --private-key=db:Open_vSwitch,SSL,private_key --certificate=db:Open_vSwitch,SSL,certificate --bootstrap-ca-cert=db:Open_vSwitch,SSL,ca_cert --pidfile --detach
    $ sudo ./utilities/ovs-vsctl --no-wait init
    $ bsudo ./vswitchd/ovs-vswitchd --pidfile

Run the following commands on each OpenFlow switch.

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

    ※”ofs1”in the above commands is to set a different name for each OpenFlow switch node.



Run the following commands on each OpenFlow switch.


::

    $ sudo ./utilities/ovs-vsctl set-controller ofs1 tcp:172.18.210.255:6633
    $ sudo ./utilities/ovs-vsctl set bridge ofs1 other-config:datapath-id=0000000000000001

    ※”ofs1”in the above commands is to set a different name for each OpenFlow switch node.



Starting OpenFlow Controller
----------------------------

Run the following commands on the OpenFlow Controller.

::

    $ cd ~/pox
    $ ./pox.py --no-cli scn.nwgn --inifile=ext/pox_sample.ini



Starting SCN Middleware
---------------------------

Run the following commands on the service node. See the example of ”10.0.1.1”service node.

::

    $ cd ~/scnm/scn/core
    $ ~/.rvm/bin/ruby main.rb 10.0.1.1/24


    ※10.0.1.1/24: IP address of its own node/subnet mask


