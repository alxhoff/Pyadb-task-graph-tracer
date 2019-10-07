#!/usr/bin/env python

import os
import re
import sys
import time


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
        self.filename = os.path.dirname(os.path.realpath(__file__)) + '/' + name + "_tracer.trace"
        self.trace_type = trace_type
        self.functions = functions
        self.events = events
        self.duration = duration

    def run_tracer(self, preamble, skip):
        """ Runs the tracer by getting all of the appropriate flags set in the /d/tracing directory on the
        target system, then starting the trace by writing to the tracing_on file in the tracing directory.
        """

        if not skip:
            self._clear_tracer()
            self.adb.clear_file(self.tracing_path + "set_event")
        self._set_available_events(self.events)
        self._set_available_tracer(self.trace_type)
        self._trace_for_time(self.duration, preamble)

    def _enable_tracing(self, on=True):
        """ Enables tracing on the system connected to the current ADB connection.

        :param on: Boolean to set if tracing should be on or off
        """
        if on is True:
            self.adb.write_file(self.tracing_path + "tracing_on", "1")
        else:
            self.adb.write_file(self.tracing_path + "tracing_on", "0")

    def _trace_for_time(self, duration, preamble):
        """ The system time is firstly recorded such that the start time is known in system time.
        The trace is then let to run for the specified duration.

        :param duration: Time for which the trace should run
        """
        start_time = self._get_device_time()
        self._enable_tracing(True)
        while (self._get_device_time() - start_time) < (duration * 1000000 + preamble * 1000000):
            time.sleep(0.1)

        print("*** Traced for %s seconds ***" % ((self._get_device_time() - start_time) / 1000000.0))
        self._enable_tracing(False)

    def _get_device_time(self):
        sys_time = self.adb.command("cat /proc/uptime")  # Get timestamp when test started
        return int(float(re.findall(r"(\d+.\d{2})", sys_time)[0]) * 1000000)

    def get_trace_results(self):
        """ Retrieves, through the ADB connection, both the tracecmd binary data and the ASCII ftrace data
        generated by tracecmd.
        """
        sys.stdout.write("Pulling /data/local/tmp/trace.dat")
        self.adb.pull_file("/data/local/tmp/trace.dat", "results/" + self.name + ".dat")
        print(" --- Completed")
        sys.stdout.write("Pulling /data/local/tmp/trace.report")
        self.adb.pull_file("/data/local/tmp/trace.report", "results/" + self.name + ".report")
        print(" --- Completed")
        sys.stdout.write("Pulling /d/binder/transaction_log")
        self.adb.pull_file("/d/binder/transaction_log", "results/" + self.name + ".tlog")
        print(" --- Completed")

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
                    self.adb.append_to_file(self.tracing_path + "set_event",
                                            events[f])
        else:
            if events in avail_events:
                self.adb.append_to_file(self.tracing_path + "set_event", events)

    def _set_event_filter(self, event, filter_contents):
        """ Sets the ftrace event filter for a particular event.

        :param event: The string representation of the event that is to be filtered
        :param filter_contents: State of the event filter to be set
        """
        event_dir = self.adb.command(
                "find " + self.tracing_path + "/events -name " + event)
        if event_dir is None:
            return

        self.adb.append_to_file(self.tracing_path + event_dir + "/filter",
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
