import logging
import re

class PID:

    def __init__(self, pid, user, time, pname, tname):
        self.pid = pid
        self.user = user
        self.time = time
        self.pname = pname
        self.tname = tname


class PIDtracer:

    def __init__(self, adb_device, name):
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("PID tracer created")

        self.adb_device = adb_device
        self.name = name
        self.mainPID = self.findMainPID()
        self.allPID = []
        self.findAllPID()

    def __del__(self):
        self.logger.debug("PID tracer closed")

    def findMainPID(self):
        res = self.adb_device.runCommand("ps | grep " + self.name)
        res = res.split()
        self.logger.debug("Found main PID of " + res[1] + " for process "
                + res[8])
        ret = PID(res[1], res[0], 0, res[7], "main")

    def findAllPID(self):
        res = self.adb_device.runCommand("busybox ps -T | grep " + self.name)
        res = res.splitlines()
        for line in res:
            if "grep" in line:
                continue
            split_line = re.split('{|}', line)
            before_name = split_line[0].split()
            after_name = split_line[2].split()
            self.allPID.append(PID(before_name[0], before_name[1],
                before_name[2], after_name[0], split_line[1]))
            self.logger.debug("Found related process:  " + before_name [0] + "  "
                    + split_line[1])



