# -*- coding: utf-8 -*-
"""
scn.plugins.middleware.utils.redisFeature
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:copyright: Copyright (c) 2015, National Institute of Information and Communications Technology.All rights reserved.
:license: GPL3, see LICENSE for more details.
"""

import redis
from fluent import event, sender

from pox.core import core
from replay import LogFile
import json

replay_log = LogFile("redis_ofc")
log = core.getLogger()


class RedisFeature:
    """Redis client Feature.
        we can use that save to redis, delete from redis and publish.
    """
    def __init__(self):
        host = core.parser.getValue('REDIS', 'host')
        port = core.parser.getValue('REDIS', 'port')
        self.log = core.parser.getValue('REDIS', 'log')
        self.fluent = core.parser.getValue('REDIS', 'fluent')
        self.redis = None
        self.strict_redis = None

        if host and port:
            self.redis = redis.Redis(host = str(host), port = int(port), db = 0)
            self.strict_redis = redis.StrictRedis(host = str(host), port = int(port), db = 0)
            log.debug(self.redis.info())
            self.redis.flushdb()
        else:
            log.warn("no redis")

        if self.fluent:
            sender.setup('scnm', host=host, port=24224)

    def __push__(self, key, data):
        """save to redis list.
        """
        if self.log:
            replay_log.write(json.dumps({"type":"push","key":key,"data":data}))

        if self.fluent:
            log.info("hoge")
            event.Event('redis', {"type":"push","key":key,"data":data})

        else:
            if self.redis:
                self.redis.rpush(key, data)

    def __pop__(self, key):
        """get from redis list.
        """
        if self.redis:
            self.redis.rpop(key)

    def __save_state__(self, key, data):
        """save to redis set.
        """
        if self.redis:
            self.redis.sadd(key, data)

    def __delete_state__(self, key, data):
        """delete from redis set.
        """
        if self.redis:
            self.redis.srem(key, data)

    def __publish__(self, channel, data):
        """publish to redis channel.
            use StrictRedis instance because redis.py dosen't have pub method.
        """
        if self.log:
            replay_log.write(json.dumps({"type":"publish","key":channel,"data":data}))

        if self.fluent:
            log.info("fuga")
            event.Event('redis', {"type":"publish","key":channel,"data":data})

        else:
            if self.strict_redis:
                self.strict_redis.publish(channel, data)

    def __save_hash__(self, key, field, data):
        """save to redis hash.
        """
        if self.redis:
            self.redis.hset(key, field, data)

    def __delete_hash__(self, key, field):
        """delete from redis hash.
        """
        if self.redis:
            self.redis.hdel(key, field)

