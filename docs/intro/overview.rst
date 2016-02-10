============
What is SCN?
============
* Service-Controlled Networking (SCN) is the technology providing the capability to configure network resources automatically according to application requests, and to cooperate efficiently with various information services that configure applications.
* This will enable the user to analyze sensor data or social data cross-sectionally in various fields, and to create services that discover new value.
* Furthermore, when an unexpected event is detected by the sensor data, it enables the intensive collection and analysis of sensor data that collects various information around the area.

.. image:: img/fig-overview-1.png
      :width: 700px
      :align: center


Features of SCN
================

Service search/service cooperation
----------------------------------
* It enables the user to find information services that match the specified search criteria from among the information services that are running separately on each node.
* Additionally, it enables users to collect needed data as much as necessary by cooperating with the information services that were found.

.. image:: img/fig-overview-2.png
      :width: 600px
      :align: center

In-Network Data Processing
---------------------------
* When collecting data by cooperating with information services, it enables the user to perform processes such as filtering or putting together the network.
* It enables the user to assign the optimum node to execute a Channel function, and to perform routing of the route that passes through the node.

.. image:: img/fig-overview-3.png
      :width: 600px
      :align: center

Data communication route control
--------------------------------
* When congestion occurs on the network, it provides the capability to switch the data communication route dynamically to avoid congestion.

.. image:: img/fig-overview-4.png
      :width: 600px
      :align: center


Declarative definition of Service search/Service cooperation
------------------------------------------------------------
* It enables the user to define service search and service cooperation declaratively with the following Declarative Service Networking (DSN).

::

    state do
        @jmarain: discovery(category=sensor, type=rain)
        @traffic: discovery(category=sensor, type=traffic)
        @store:   discovery(type=store, key=heavyrain)

        scratch: s_jmarain, @jmarain
        scratch: s_traffic, @traffic
        channel: c_store,   @store
    end

    bloom do
        c_store <~ s_jmarain.filter(rain >= 25 && range(latitude, 33.0, 37.0) && range(longitude, 134.0, 137.0)).meta(Table=JMA1hRainFall)

        event_heavyrain <+ c_store.trigger(30, count > 130)

        event_heavyrain.in do
            c_store <~ s_traffic.filter(not like(Condition, ".*Normal operation..*").meta(Table=YahooTrafficInformation)
        end
    end



About SCN development
=====================
SCN is an open source project that is being developed by the Information Services Platform Laboratory at the National Institute of Information and Communications Technology (http://nict.go.jp/univ-com/isp/index.html).

