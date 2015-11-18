#!/usr/bin/python
#:-*- coding: utf-8 -*-
"""
scn.plugins.middleware.utils.replay
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""
import sys
import heapq

import datetime
import time
import threading

ARGUMENT_FORMAT = "%Y-%m-%dT%H:%M:%S"
LOG_FILE_FORMAT = "%Y%m%d-%H%M%S-%f"
LOG_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S,%f"
LOG_TIME_LENGTH = 26


def total_seconds(td):
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


class LogFile():
    """ ログファイルクラス
    ログファイルへの書き込み機能を提供する。
    入力されたデータは、タイムスタンプと共に書き出される。

    指定データ件数でログのローテートを行なう。
    """
    def __init__(self, name, linemax=100000):
        """ 初期化
        name    [str] -- ログファイル名
        linemax [int] -- 1ファイルの最大行数
        """
        self.name = name
        self.fp = None
        self.linemax = linemax
        self.open()


    def open(self):
        """ オープン
        """
        if self.fp is not None:
            self.fp.close()
        self.fp = open("{0}_{1}.log".format(self.name, datetime.datetime.now().strftime(LOG_FILE_FORMAT)), 'w')
        self.count = 0


    def write(self, data):
        """ 書き込み
        data [str] -- データ本体（改行を含まないこと）
        """
        if self.count >= self.linemax:
            self.open()     # ログローテート

        self.fp.write("{0} {1}\n".format(datetime.datetime.now().strftime(LOG_TIME_FORMAT), data))
        self.count += 1


class LogPlayer():
    """ ログ再生クラス
    ログを再生する機能を提供する。
    ログファイルクラスの作成したログファイルを読み込み、
    ログファイルに書き出されたデータ本体を、タイムスタンプの時間に、
    再生処理用のファンクションへ渡す。

    再生時処理：
    1. ログのタイムスタンプ＞再生の基準時間＋（再生の開始時間－現在時間）の時、
       ログのタイムスタンプまでの差分時間 sleep
    2, ログのデータ本体を再生処理用のファンクションへ渡す。
    3. すべてのログファイルを読み出すまで、1.～2.を繰り返し。
    """
    def __init__(self, logs, start, end, speed, func):
        """ 初期化
        logs  [list<str>]     -- 再生するログファイル名の一覧（再生順）
        start [str]           -- 再生の開始時間
        end   [str]           -- 再生の終了時間
        speed [int]           -- 再生速度の倍率
        func  [function<str>] -- 再生処理用のファンクション
        """
        self.func = func
        self.logs = logs
        self.start = datetime.datetime.strptime(start, ARGUMENT_FORMAT)
        self.end = datetime.datetime.strptime(end, ARGUMENT_FORMAT)
        self.speed = speed


    def play(self):
        """ ログ再生
        スレッドでログ再生を開始する。

        return [Thread] -- ログを再生するスレッド
        """
        thread = threading.Thread(target=self.do)
        thread.setDaemon(True)
        thread.start()
        return thread


    def do(self):
        """ ログ再生処理
        """
        delay = 5
        print "start: {0}".format(self.start)
        print "end: {0}".format(self.end)
        print "start after {0}seconds.".format(delay)
        time.sleep(delay);
        basis = datetime.datetime.now()
        time.sleep(0.1);

        targets = [open(filename) for filename in self.logs]
        for line in heapq.merge(*targets):
            line = line.rstrip()
            try:
                logtime = datetime.datetime.strptime(line[:LOG_TIME_LENGTH], LOG_TIME_FORMAT)
                if self.start > logtime:
                    continue    # 開始時間まで読み飛ばし
                if self.end < logtime:
                    print "finished."
                    break       # 再生を終了

                nowtime = self.start + (datetime.datetime.now() - basis) * self.speed
                if logtime > nowtime:
                    diff = total_seconds(logtime - nowtime)
                    if diff > 1.0:
                        print "log: {0}".format(logtime)
                        print "now: {0} (waiting {1}sec)".format(nowtime, diff)
                    time.sleep(diff / self.speed)

                self.func(line[LOG_TIME_LENGTH + 1:])
            except:
                print "invalid line: {0}".format(line)
                raise


if __name__ == '__main__':
    if len(sys.argv) < 4:
        exit(
            "Usage: # {0} replay_speed start_time end_time file..\n"
            "\n"
            "   replay_speed - magnification of the replay speed. ex: 1\n"
            "   start_time   - start time for replay. ex: 2014-04-25T16:50:10\n"
            "   end_time     - end time of replay. ex: 2014-04-25T16:55:10\n"
            "   file..       - log files.\n"
            .format(sys.argv[0])
        )

    def preview(data):
        """ 再生処理用のファンクション（サンプル）
        data [str] -- ログファイルから読み込んだデータ本体
        """
        print data

    th = LogPlayer(sys.argv[4:], sys.argv[2], sys.argv[3], int(sys.argv[1]), preview).play()
    while th.isAlive():
        th.join(0.1)    # Ctrl^Cを受け付ける為、ループにする

