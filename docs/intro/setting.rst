==========================
SCN environmental settings
==========================

Example of topology
===================
Based on the example of topology shown below, it describes the SCN operating environment.

.. image:: img/fig-setting-1.png
      :width: 800px
      :align: center


OpenFlow network consists of two networks of the data flow by which the data packet flows and the control flow by which the control packet flows.
At the data flow, data packets that are sent and received between service nodes flow just as they do in a normal network. 
At the control flow, OpenFlow specific message packets (such as Flow-Mod or Packet-In) flow between OpenFlow controller and OpenFlow switch.

Service node
===============

Settings for Network Interface
---------------------------------
The settings for ”/etc/network/interfaces” file of “10.0.1.1” service node are described below. 
For each service node, edit the contents of this file to match the respective IP addresses.

::

    auto lo
    iface lo inet loopback

    auto eth1
    iface eth1 inet static
        address 10.0.1.1
        netmask 255.255.255.0
        network 10.0.1.0
        broadcast 10.0.1.255
        up route add -net 10.0.0.0 netmask 255.0.0.0 gw 10.0.1.254
        post-up ethtool -K $IFACE tso off gso off gro off


Run the following commands after editing interface files.

::

    $ sudo /etc/init.d/networking restart


OpenFlow switch node
=======================


Install Open vSwitch
---------------------------

Run the following commands

::

$ sudo apt-get install libssl1.0.0 autoconf automake libtool
$ cd
$ wget http://69.56.251.103/releases/openvswitch-2.1.2.tar.gz
$ tar zxf openvswitch-2.1.2.tar.gz
$ cd openvswitch-2.1.2
$./boot.sh
$./configure --with-linux=/lib/modules/`uname -r`/build
$ make
$ sudo make modules_install
$ sudo /sbin/modprobe openvswitch 
$ sudo echo "openvswitch" >>  /etc/modules
$ sudo mkdir -p /usr/local/etc/openvswitch /usr/local/var/run/openvswitch
$ sudo ./ovsdb/ovsdb-tool create /usr/local/etc/openvswitch/conf.db vswitchd/vswitch.ovsschema


Settings for Network Interface
---------------------------------
The settings for “/etc/network/interfaces” file of OpenFlow switch node at “172.18.210.254” are described below. For each OpenFlow switch, edit the contents of this file to match the respective IP addresses.

::

    auto lo
    iface lo inet loopback
    
    auto eth0
    iface eth0 inet static
        address 172.18.210.254
        netmask 255.255.0.0
        network 172.18.0.0
        broadcast 172.18.255.255
        gateway 172.18.254.254
        post-up ethtool -K $IFACE tso off gso off gro off
    
    auto eth1
    iface eth1 inet manual
        pre-up ifconfig $IFACE up
        post-down ifconfig $IFACE down
        post-up ethtool -K $IFACE tso off gso off gro off
    
    auto eth1.1001
    iface eth1.1001 inet manual
        pre-up ifconfig $IFACE up
        pre-up ifconfig $IFACE hw ether 00:00:00:00:10:01
        post-down ifconfig $IFACE down
        post-up ethtool -K $IFACE tso off gso off gro off
    
    auto eth1.1002
    iface eth1.1002 inet manual
        pre-up ifconfig $IFACE up
        pre-up ifconfig $IFACE hw ether 00:00:00:00:10:02
        post-down ifconfig $IFACE down
        post-up ethtool -K $IFACE tso off gso off gro off
    
    auto eth2
    iface eth2 inet manual
        pre-up ifconfig $IFACE up
        post-down ifconfig $IFACE down
        post-up ethtool -K $IFACE tso off gso off gro off
    
    auto eth2.2751
    iface eth2.2751 inet manual
        pre-up ifconfig $IFACE up
        post-down ifconfig $IFACE down
        post-up ethtool -K $IFACE tso off gso off gro off
    
    auto eth2.2752
    iface eth2.2752 inet manual
        pre-up ifconfig $IFACE up
        post-down ifconfig $IFACE down
        post-up ethtool -K $IFACE tso off gso off gro off


Settings for disabling IPv6
----------------------------

Add the following settings to “etc/sysctl.conf” file of each OpenFlow switch.

::

    net.ipv6.conf.all.disable_ipv6 = 1
    net.ipv6.conf.default.disable_ipv6 = 1


Run the following command.

::

    $ sudo reboot




OpenFlow Controller Node
===========================

Settings for Network Interface
---------------------------------

Edit “/etc/network/interfaces”of OpenFlow Controller Node as follows.

::

    auto lo
    iface lo inet loopback

    auto eth0
    iface eth0 inet static
            address 172.18.210.255
            netmask 255.255.0.0
            network 172.18.0.0
            broadcast 172.18.255.255
            gateway 172.18.254.254
            post-up ethtool -K $IFACE tso off gso off gro off

Run the following command, after editing interfaces files.

::

    $ sudo /etc/init.d/networking restart

Settings for POX setting file
-----------------------------

Set the topology definition of “pox_sample.ini” as follows.

::

    [TOPOLOGY]
    SWITCHS=S1,S2,S3
    
    [S1]
    IP=172.18.210.254
    PORTS=S1E1.1001,S1E1.1002,S1E2.2751,S1E2.2752
    
    [S1E1.1001]
    NAME=eth1.1001
    IP=10.0.1.254
    
    [S1E1.1002]
    NAME=eth1.1002
    IP=10.0.2.254
    
    [S1E2.2751]
    NAME=eth2.2751
    SPEED=50M
    
    [S1E2.2752]
    NAME=eth2.2752
    SPEED=50M
    
    [S2]
    IP=172.18.212.254
    PORTS=S2E1.1201,S2E1.1202,S2E2.2751, S2E2.2753
    
    [S2E1.1201]
    NAME=eth1.1201
    IP=10.2.1.254
    
    [S2E1.1202]
    NAME=eth1.1202
    IP=10.2.2.254
    
    [S2E2.2751]
    NAME=eth2.2751
    SPEED=50M
    
    [S2E2.2753]
    NAME=eth2.2753
    SPEED=50M
    
    [S3]
    IP=172.18.214.254
    PORTS=S3E1.1401,S3E1.1402,S3E2.2752,S3E2.2753
    
    [S3E1.1401]
    NAME=eth1.1401
    IP=10.4.1.254
    
    [S3E1.1402]
    NAME=eth1.1402
    IP=10.4.2.254
    
    [S3E2.2752]
    NAME=eth2.2752
    SPEED=50M
    
    [S3E2.2753]
    NAME=eth2.2753
    SPEED=50M


