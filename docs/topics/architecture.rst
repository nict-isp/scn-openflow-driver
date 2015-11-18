===============
アーキテクチャ
===============

.. _POX: http://www.noxrepo.org/pox/about-pox/


ネットワーク構成
=================
* SCN OpenFlow Driverは、プログラミング可能なネットワークとして、OpenFlowを利用します。
* 各情報サービスが動作するサービスノードは、OpenFlowネットワークを介して接続されます。
* OpenFlowスイッチはOpenFlowコントローラと接続し、各サービスノードは1つのOpenFlowスイッチと接続します。
* SCN OpenFlow Driverは、サービス連携の定義に従い、各OpenFlowスイッチのフローテーブルにデータの転送ルールを設定します。
* SCN OpenFlow Driverがネットワークの負荷状況に応じてフローを動的に切り替え、特定の経路にトラフィックが集中することを回避することで、
  ネットワークリソースの利用を最適化することができます。

.. image:: img/fig-architecture-1.png
      :width: 500px
      :align: center


ソフトウェア構成
=================
* サービスノード上では、SCN Coreが動作し、その上で、SCNを利用するサービスプログラムが複数動作します。
* OpenFlowスイッチとOpenFlowコントローラ上では、OpenFlowを実現するためにそれぞれ「Open vSwitch」と「 `POX`_ 」というソフトウェアを動作させます。
* SCN OpenFlow Driverは、OpenFlowコントローラ上の `POX`_ プラグインとして動作させます。

.. image:: img/fig-architecture-2.png
      :width: 500px
      :align: center


SCN OpenFlow Driverの構成
==========================
* SCN OpenFlow Driverは、OpenFlowコントローラ「 `POX`_ 」を拡張して実装しています。

.. image:: img/fig-architecture-3.png
      :width: 200px
      :align: center

POX
^^^^
* フリーのOpenFlowコントローラです。
* OpenFlowコントローラが持つ標準の機能
  (OpenFlowスイッチの検出、Flowテーブルの書き換え、PacketInの受信、PacketOutの送信、OpenFlowスイッチから統計情報の取得など)
  を提供します。


SCN OpenFlow Driver
^^^^^^^^^^^^^^^^^^^^
* SCN用に、 `POX`_ が持つクラスを継承したり `POX`_ のプラグインとして機能を追加しています。
* 主に、以下のイベントドリブンで動作します。

  * OpenFlowスイッチ接続
  * PacketIn
  * SCN Coreからのメッセージ受信
  * タイマーなど


SCN OpenFlow Driverの機能
==========================

SCN Core通信機能
^^^^^^^^^^^^^^^^^
* SCN OpenFlow Driverは、SCN Coreとの間で以下のメッセージをやりとりします。

=============== ==================================================================================
メッセージ種別  メッセージ内容
=============== ==================================================================================
INITIALIZE      SCN Coreの起動通知。SCN CoreのIPアドレス、及びポートが含まれます。
CREATE_BI_PATH  パス生成通知。データの送信元および送信先のIPアドレス、通信のバンド幅が含まれます。
UPDATE_PATH     通信バンド幅変更通知。変更後の通信のバンド幅が含まれます。
DELETE_PATH     パス削除通知。削除対象のパスIDが含まれます。
OPTIMIZE        通信経路の最適化実施通知。
=============== ==================================================================================

* SCN CoreからSCN OpenFlow DriverへのINITIALIZE通知はUDP、それ以外のメッセージはTCPで通信します。


サービスサーバ通知機能
^^^^^^^^^^^^^^^^^^^^^^^
* SCN上で動作するサービスの情報は1つのサービスサーバで管理し、SCN Coreがサービスを検索する際は
  そのサーバに対して問い合わせます。SCN　OpenFlow Driverは、SCN CoreのINITIALIZEメッセージの
  レスポンスで、そのサーバのIPアドレスを返します。

パス管理機能
^^^^^^^^^^^^^
* SCN Coreから指示された「データ送信元IPアドレス」、「データ送信先IPアドレス」、「通信のバンド幅」を基に、
  データ送信元ノードからデータ送信先ノードへの経路を計算します(通信経路は「ダイクストラ法」を使用します)。
  そして、経路中のOpenFlowスイッチに対して、Flowテーブルの設定を行います。

パス最適化機能
^^^^^^^^^^^^^^^
* 定期的にOpenFlowスイッチからネットワークの統計情報を取得し、データの通信経路の最適化を実施します。
* ネットワークの統計情報の取得は、標準のOpenFlowの仕組みを使用します。
* 最適化は、パス生成時と同様に「ダイクストラ法」にて通信経路を計算します。
  計結果を基に、OpenFlowスイッチのFlowテーブルを設定し、通信経路を再設定します。


コンフィグ
===========
* `POX`_ の実行時に、以下のような内容を記述したiniファイルを指定することで、設定情報を入力することができます。

::

    [stats]
    MONITOR_FLOW_PERIOD=10
    UNIT_OF_VALUE="bit"

* 新規に開発したプラグインを追加する際は、iniファイルの以下に、追加したプラグインのファイル名(suffixを除いたもの)を記述してください。

::

    [PLUGINS]
    flowBw
    middleware
    jsonLogger
    bwFlowBalancing
    virtualNode
    stats

