import argparse
import os
import re
import time

from ADBInterface import ADBInterface
from PIDTools import PIDTool
from SysLoggerInterface import SysLogger
from SystemMetrics import SystemMetrics
from TraceCMDParser import TracecmdProcessor
from TraceProcessor import TraceProcessor

parser = argparse.ArgumentParser()

parser.add_argument("-a", "--app", required=True,
                    help="Specifies the name of the game to be traced")
parser.add_argument("-d", "--duration", required=True, type=float,
                    help="The duration to trace")
parser.add_argument("-e", "--events", required=True,
                    help="Events that are to be traced")
parser.add_argument("-s", "--skip-clear", action='store_true',
                    help="Skip clearing trace settings")
parser.add_argument("-g", "--draw", action='store_true',
                    help="Enables the drawing of the generated graph")
parser.add_argument("-te", "--test", action='store_true',
                    help="Tests only a few hundred events to speed up testing")
parser.add_argument("-sub", "--subgraph", action='store_true',
                    help="Enable the drawing of node subgraphs")

args = parser.parse_args()


class Tracer:
    """ A tracer is responsible for setting up the underlying system to perform a trace for a certain duration,
    then retrieving the results. What and for how long the tracer traces is given through the program's
    arguments.

    """
    tracing_path = '/d/tracing/'

    def __init__(self, adb_device, name, functions=None, events=None,
                 trace_type="nop", duration=1, metrics=None):

        if functions is None:
            functions = []
        if events is None:
            events = []

        self.metrics = metrics
        self.adb = adb_device
        self.name = name
        self.filename = os.path.dirname(os.path.realpath(__file__)) + '/' \
            + name + "_tracer.trace"
        self.trace_type = trace_type
        self.functions = functions
        self.events = events
        self.start_time = 0
        self.duration = duration

    def run_tracer(self):
        """ Runs the tracer by getting all of the appropriate flags set in the /d/tracing directory on the
        target system, then starting the trace by writing to the tracing_on file in the tracing directory.
        """

        if not args.skip_clear:
            self._clear_tracer()
            self.adb.clear_file(self.tracing_path + "set_event")
        self._set_available_events(self.events)
        self._set_available_tracer(self.trace_type)
        self._trace_for_time(self.duration)

    def _enable_tracing(self, on=True):
        """ Enables tracing on the system connected to the current ADB connection.

        :param on: Boolean to set if tracing should be on or off
        """
        if on is True:
            self.adb.write_file(self.tracing_path + "tracing_on", "1")
        else:
            self.adb.write_file(self.tracing_path + "tracing_on", "0")

    def _trace_for_time(self, duration):
        """ The system time is firstly recorded such that the start time is known in system time.
        The trace is then let to run for the specified duration.

        :param duration: Time for which the trace should run
        """
        sys_time = self.adb.command("cat /proc/uptime")  # Get timestamp when test started
        self.start_time = int(float(re.findall(r"(\d+.\d{2})", sys_time)[0]) * 1000000)

        start_time = time.time()
        self._enable_tracing(True)
        while (time.time() - start_time) < duration:
            pass

        self._enable_tracing(False)

    def get_trace_results(self):
        """ Retrieves, through the ADB connection, both the tracecmd binary data and the ASCII ftrace data
        generated by tracecmd.
        """
        self.adb.pull_file("/data/local/tmp/trace.dat", self.name + ".dat")
        self.adb.pull_file("/data/local/tmp/trace.report", self.name + ".report")

    def _get_available_events(self):
        """ Retrieves all the events that are able to be traced on the target system

        :return: A list of traceable events
        """
        return self.adb.read_file(self.tracing_path + "available_events")

    def _set_available_events(self, events):
        """ Checks that the specified events are valid, if so then the events are set to be traced.

        :param events: List of event name strings that are to be traced
        """
        if events is None:
            return

        avail_events = self._get_available_events()

        if isinstance(events, list):
            for f in range(0, len(events)):
                if events[f] in avail_events:
                    self.adb.append_file(self.tracing_path + "set_event",
                                         events[f])
        else:
            if events in avail_events:
                self.adb.append_file(self.tracing_path + "set_event", events)

    def _set_event_filter(self, event, filter_contents):
        """ Sets the ftrace event filter for a particular event.

        :param event: The string representation of the event that is to be filtered
        :param filter_contents: State of the event filter to be set
        """
        event_dir = self.adb.command(
            "find " + self.tracing_path + "/events -name " + event)
        if event_dir is None:
            return

        self.adb.append_file(self.tracing_path + event_dir + "/filter",
                             filter_contents)

    def _clear_event_filter(self, event):
        """ Clears the ftrace event filter for a particular event.

        :param event: Event whoes filter is to be cleared
        """
        event_dir = self.adb.command(
            "find " + self.tracing_path + "/events -name " + event)
        if event_dir is None:
            return

        self.adb.clear_file(self.tracing_path + event_dir + "/filter")

    def _get_event_format(self, event):
        """ Retrieves the format string for a particular event.

        :param event: Event whoes format string is to be retrieved
        :return: String representation of the event's format. Empty string otherwise.
        """
        event_dir = self.adb.command(
            "find " + self.tracing_path + "/events -name " + event)
        if event_dir is None:
            return ""

        return self.adb.read_file(self.tracing_path
                                  + event_dir + "/format")

    def _get_available_tracer(self):
        """ Gets a list of the available tracers on the target system.

        :return: An unprocessed string of all the available tracers on the target system
        """
        return self.adb.read_file(self.tracing_path + "available_tracers")

    def _set_available_tracer(self, tracer):
        """ Checks if the desired tracers is valid before setting the given tracer.

        :param tracer: The tracer that is to be set on the target system.
        """
        available_tracers = self._get_available_tracer()
        if tracer in available_tracers:
            self.adb.write_file(self.tracing_path
                                + "current_tracer", tracer)

    def _clear_tracer(self):
        """ Resets the current tracer by setting the current tracer to 'nop'.
        """
        self.adb.write_file(self.tracing_path + "current_tracer", "nop")
        self.adb.clear_file(self.tracing_path + "trace")


def main():
    """ Entry point into the debugging tool.
    """

    """ Required objects for tracking system metrics and interfacing with a target system, connected
    via an ADB connection.
    """
    adb = ADBInterface()
    pid_tool = PIDTool(adb, args.app)
    trace_processor = TraceProcessor(pid_tool, args.app)
    sys_metrics = SystemMetrics(adb)

    """ The tracer object stores the configuration for the ftrace trace that is to be performed on the
    target system.
    """

    print "Creating tracer, starting sys_logger and running trace"

    tracer = Tracer(adb,
                    args.app,
                    metrics=sys_metrics,
                    events=args.events.split(','),
                    duration=args.duration
                    )

    """ As the energy debugger depends on the custom trace points implemented in the syslogger module,
    it must be loaded before tracing begins. It must then be unloaded and finished before the results
    are pulled from the target system.
    """

    # sys_logger = SysLogger(adb)
    # sys_logger.start()
    # tracer.run_tracer()
    # sys_logger.stop()
    # tracer.get_trace_results()

    """ The tracecmd data pulled (.dat suffix) is then iterated through and the trace events are systematically
    processed. Results are generated into a CSV file, saved to the working directory under the same name as the target
    application with the suffix _results.csv.
    """

    print "Loading tracecmd data and processing"

    dat_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), args.app + ".dat")

    tc_processor = TracecmdProcessor(dat_path)
    tc_processor.print_event_count()
    trace_processor.process_trace(sys_metrics, tc_processor, args.duration, args.draw, args.test, args.subgraph)


if __name__ == '__main__':
    main()
