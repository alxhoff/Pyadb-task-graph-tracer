import time

from enum import Enum


class SysLoggerStatus(Enum):
    INIT = 1
    SETUP = 2
    START = 3
    STOP = 4
    FINISH = 5


class SysLogger:
    def __init__(self, adb):
        self.adb = adb
        self.status = SysLoggerStatus.INIT

    # The internal buffers on the Odroid XU3 only allow you to increment them slowly
    def _get_da_buffers_up(self, buffer_val):
        cur_val = int(
            self.adb.command("cat /sys/kernel/debug/tracing/buffer_size_kb"))
        attempts = 0
        while cur_val < buffer_val:
            self.adb.command('echo "' + str(cur_val + 500) +
                             '" > /sys/kernel/debug/tracing/buffer_size_kb')
            time.sleep(0.1)
            prev_val = cur_val
            cur_val = int(
                self.adb.command(
                    "cat /sys/kernel/debug/tracing/buffer_size_kb"))
            if prev_val == cur_val:
                attempts += 1
                if attempts == 3:
                    return
            else:
                attempts = 0

    def start(self):
        # self.stop()
        self._setup()
        print "--- Syslogger starting"
        self.adb.command("./data/local/tmp/sys_logger.sh start")
        print "--- Syslogger started"
        self.status = SysLoggerStatus.START

    def stop(self):
        print "--- Syslogger stopping"
        self.adb.command("./data/local/tmp/sys_logger.sh stop")
        print "--- Syslogger stopped"
        self.status = SysLoggerStatus.STOP
        time.sleep(0.5)
        self._finish()

    def _setup(self):
        print "--- Syslogger setting up"
        self._get_da_buffers_up(17000)
        self.adb.command("./data/local/tmp/sys_logger.sh setup -nt")
        print "--- Syslogger setup"
        self.status = SysLoggerStatus.SETUP

    def _finish(self):
        print "--- Syslogger finishing"
        self.adb.command("./data/local/tmp/sys_logger.sh finish")
        print "--- Syslogger finished"
        self.status = SysLoggerStatus.FINISH
