#!/usr/bin/env python

import argparse
import time
import os
import sys

import csv

import MainInterface
import SettingsDialog
import AboutDialog

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox, QTableWidgetItem, QDialog

from ADBInterface import ADBInterface
from PIDTools import PIDTool
from SysLoggerInterface import SysLogger
from SystemMetrics import SystemMetrics
from TraceCMDParser import TracecmdProcessor
from TraceProcessor import TraceProcessor
from Tracer import Tracer

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

parser = argparse.ArgumentParser()

parser.add_argument("-c", "--commandline", required=False,
                    help="Enables the use of command line arguments")
parser.add_argument("-a", "--app", required=False,
                    help="Specifies the name of the game to be traced")
parser.add_argument("-d", "--duration", required=False, type=float,
                    help="The duration to trace")
parser.add_argument("-e", "--events", required=False,
                    help="Events that are to be traced")
parser.add_argument("-s", "--skip-clear", action='store_true',
                    help="Skip clearing trace settings")
parser.add_argument("-g", "--draw", action='store_true',
                    help="Enables the drawing of the generated graph")
parser.add_argument("-te", "--test", action='store_true',
                    help="Tests only a few hundred events to speed up testing")
parser.add_argument("-sub", "--subgraph", action='store_true',
                    help="Enable the drawing of node subgraphs")
parser.add_argument("-p", "--preamble", required=False,
                    help="Specifies the number of seconds that be discarded at the begining of tracing")

args = parser.parse_args()

class AboutDialog(QDialog, AboutDialog.Ui_Dialog):

    def __init__(self, parent=None):
        super(QDialog, self).__init__(parent)
        self.setupUi(self)

class SettingsMenu(QDialog, SettingsDialog.Ui_DialogSettings):


    def __init__(self, settings, parent=None):
        super(QDialog, self).__init__(parent)
        self.setupUi(self)

        self.settings = settings
        self.lineEditApplicationName.setText(settings.value("DefaultApplication", defaultValue=""))
        self.doubleSpinBoxDuration.setValue(float(settings.value("DefaultDuration", defaultValue=0.0)))
        self.doubleSpinBoxPreamble.setValue(float(settings.value("DefaultPreamble", defaultValue=0.0)))
        self.checkBoxDrawGraph.setChecked(bool(int(settings.value("DefaultDrawGraph", defaultValue=0))))
        self.checkBoxWakeUp.setChecked(bool(int(settings.value("DefaultEventWakeUp", defaultValue=0))))
        self.checkBoxSchedSwitch.setChecked(bool(int(settings.value("DefaultEventSchedSwitch", defaultValue=1))))
        self.checkBoxCPUIdle.setChecked(bool(int(settings.value("DefaultEventCPUIdle", defaultValue=0))))
        self.checkBoxBinderTransaction.setChecked(bool(int(settings.value("DefaultEventBinderTransaction", defaultValue=1))))
        self.checkBoxSyslogger.setChecked(bool(int(settings.value("DefaultEventSyslogger", defaultValue=1))))


    def accept(self):
        self.settings.setValue("DefaultApplication", self.lineEditApplicationName.text())
        self.settings.setValue("DefaultDuration", self.doubleSpinBoxDuration.value())
        self.settings.setValue("DefaultPreamble", self.doubleSpinBoxPreamble.value())
        self.settings.setValue("DefaultDrawGraph", int(self.checkBoxDrawGraph.isChecked()))
        self.settings.setValue("DefaultEventSchedSwitch", int(self.checkBoxSchedSwitch.isChecked()))
        self.settings.setValue("DefaultEventCPUIdle", int(self.checkBoxCPUIdle.isChecked()))
        self.settings.setValue("DefaultEventBinderTransaction", int(self.checkBoxBinderTransaction.isChecked()))
        self.settings.setValue("DefaultEventSyslogger", int(self.checkBoxSyslogger.isChecked()))
        self.settings.setValue("DefaultEventWakeUp", int(self.checkBoxWakeUp.isChecked()))

        super(SettingsMenu, self).accept()

    def reject(self):
        super(SettingsMenu, self).reject()


class MainInterface(QMainWindow, MainInterface.Ui_MainWindow):

    def __init__(self, parent=None):
        super(QMainWindow, self).__init__(parent)

        self.setupUi(self)
        self.setupbuttons()
        self.setupmenu()
        self.settings = None
        self.setupsettings()
        self.getsettings()
        self.show()


        self.results_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "results/")
        self.trace_file = None
        self.results_file = None
        self.graph_file = None
        self.binder_log_file = None
        self.binder_log = []

        self.current_debugger = None

        self.application_name = None
        self.events = []
        self.duration = 0  # TODO defaults
        self.events_to_process = 0
        self.preamble = 2
        self.graph = False
        self.subgraph = False

    def getsettings(self):
        self.lineEditApplicationName.setText(self.settings.value("DefaultApplication", defaultValue=""))
        self.doubleSpinBoxDuration.setValue(float(self.settings.value("DefaultDuration", defaultValue=0.0)))
        self.doubleSpinBoxPreamble.setValue(float(self.settings.value("DefaultPreamble", defaultValue=0.0)))
        if float(self.settings.value("DefaultPreamble", defaultValue=0.0)) != 0.0:
            self.checkBoxPreamble.setChecked(True)
        self.checkBoxDrawGraph.setChecked(bool(int(self.settings.value("DefaultDrawGraph", defaultValue=0))))
        self.checkBoxWakeUp.setChecked(bool(int(self.settings.value("DefaultEventWakeUp", defaultValue=0))))
        self.checkBoxSchedSwitch.setChecked(bool(int(self.settings.value("DefaultEventSchedSwitch", defaultValue=1))))
        self.checkBoxCPUIdle.setChecked(bool(int(self.settings.value("DefaultEventCPUIdle", defaultValue=0))))
        self.checkBoxBinderTransaction.setChecked(
            bool(int(self.settings.value("DefaultEventBinderTransaction", defaultValue=1))))
        self.checkBoxSyslogger.setChecked(bool(int(self.settings.value("DefaultEventSyslogger", defaultValue=1))))

    def setupsettings(self):
        self.settings = QSettings("HoffSoft", "Android Energy Debugger")


    def setupbuttons(self):
        self.pushButtonRun.clicked.connect(self.buttonrun)
        self.pushButtonKillADB.clicked.connect(self.buttonkilladb)

    def setupmenu(self):
        self.actionOpenResults.triggered.connect(self.openresults)
        self.actionOpenBinderLog.triggered.connect(self.openbinderlog)
        self.actionOpenSettings.triggered.connect(self.opensettingsmenu)
        self.actionAbout.triggered.connect(self.openaboutdialog)

    def openresults(self):
        if self.lineEditApplicationName.text() is None:
            QMessageBox.warning(self, "Error", "Application is not specified", QMessageBox.Ok)
            return

        self.application_name = self.lineEditApplicationName.text()
        results_filename = os.path.join(self.results_path, self.application_name + "_results.csv")

        col_count = 0
        row_count = 0
        with open(results_filename, "r") as fileInput:
            for row in csv.reader(fileInput):
                row_count += 1
                if len(row) > col_count:
                    col_count = len(row)

            fileInput.seek(0)
            self.tableWidgetResults.setColumnCount(col_count)
            self.tableWidgetResults.setRowCount(row_count)

            for i, row in enumerate(csv.reader(fileInput)):
                for j, col in enumerate(row):
                    self.tableWidgetResults.setItem(i, j, QTableWidgetItem(col))

    def opensettingsmenu(self):
        settings_menu = SettingsMenu(self.settings)
        settings_menu.exec_()

    def openaboutdialog(self):
        dialog = AboutDialog()
        dialog.exec_()

    def opengraph(self):
        pass

    def openbinderlog(self):
        if self.lineEditApplicationName.text() is None:
            QMessageBox.warning(self, "Error", "Application is not specified", QMessageBox.Ok)
            return

        self.application_name = self.lineEditApplicationName.text()

        try:
            self.binder_log_file = open(os.path.join(self.results_path, self.application_name + ".tlog"), "r")
        except Exception:
            QMessageBox.warning(self, "Error", "Binder log does not exist", QMessageBox.Ok)
            return

        self.binder_log = []
        for line in self.binder_log_file:
            self.binder_log.append(line)
            self.textBrowserBinderLog.append(line)

        self.textBrowserBinderLog.verticalScrollBar().setValue(0)

    def checkrun(self):

        error = False
        error_str = "The following required parameters are missing:\n\n"
        if not self.lineEditApplicationName.text():
            error = True
            error_str += "Application Name\n"
        if self.doubleSpinBoxDuration.value() == 0.0:
            error = True
            error_str += "Duration"

        if error:
            QMessageBox.warning(self, "Error", error_str, QMessageBox.Ok)

        return error

    def buttonrun(self):
        if self.checkrun():
            return
        if self.current_debugger:
            self.current_debugger.clear()

        self.application_name = self.lineEditApplicationName.text()
        self.duration = self.doubleSpinBoxDuration.value()
        self.events = []
        if self.checkBoxBinderTransaction.isCheckable():
            self.events.append("binder_transaction")
        if self.checkBoxCPUIdle.isChecked():
            self.events.append("cpu_idle")
        if self.checkBoxSchedSwitch.isChecked():
            self.events.append("sched_switch")
        if self.checkBoxSysLogger.isChecked():
            self.events.append("sys_logger")
        if self.checkBoxWakeUp.isChecked():
            self.events.append("sched_wakeup")
        if self.checkBoxEvents.isChecked():
            self.events_to_process = self.spinBoxEvents.value()
        else:
            self.events_to_process = 0
        self.preamble = self.doubleSpinBoxPreamble.value()
        self.subgraph = self.checkBoxSubGraph.isChecked()
        self.graph = self.checkBoxDrawGraph.isChecked()

        self.current_debugger = EnergyDebugger(
            application=self.application_name,
            duration=self.duration,
            events=self.events,
            event_count=self.events_to_process,
            preamble=self.preamble,
            graph=self.graph,
            subgraph=self.subgraph
        )

        self.current_debugger.run()

    def buttonkilladb(self):
        os.system("killall adb")


class CommandInterface:

    def __init__(self):
        pass

    def checkrun(self):
        if not args.app:
            return False
        if not args.duration:
            return False

    def run(self):
        pass


class EnergyDebugger:

    def __init__(self, application, duration, events, event_count, preamble, graph, subgraph):

        self.application = application
        self.duration = duration
        self.events = []
        self.event_count = event_count
        self.preamble = preamble
        self.graph = graph
        self.subgraph = subgraph

        """ Required objects for tracking system metrics and interfacing with a target system, connected
        via an ADB connection.
        """
        self.adb = ADBInterface()
        self.pid_tool = PIDTool(self.adb, self.application)
        self.trace_processor = TraceProcessor(self.pid_tool, self.application)
        self.sys_metrics = SystemMetrics(self.adb)


        """ The tracer object stores the configuration for the ftrace trace that is to be performed on the
        target system.
        """

        print "Creating tracer, starting sys_logger and running trace"

        self.tracer = Tracer(adb_device=self.adb,
                             name=application,
                             metrics=self.sys_metrics,
                             events=events,
                             duration=duration
                             )

        if self.duration > 6:
            print "WARNING: Running traces over 6 seconds can cause issue due to data loss from trace buffer size " \
                "limitations"
            QMessageBox.warning(self, "Warning", "Running traces over 6 seconds can cause issue due to data loss from trace buffer size limitations",
                                QMessageBox.Ok)

        self.sys_logger = SysLogger(self.adb)

        self.run()

    def clear(self):
        # TODO
        pass

    def run(self):
        """ Entry point into the debugging tool.
        """
        """ As the energy debugger depends on the custom trace points implemented in the syslogger module,
        it must be loaded before tracing begins. It must then be unloaded and finished before the results
        are pulled from the target system.
        """
        self.start_time = time.time()

        self.sys_logger.start()
        self.tracer.run_tracer(self.preamble, args.skip_clear)
        self.sys_logger.stop()
        self.tracer.get_trace_results()

        """ The tracecmd data pulled (.dat suffix) is then iterated through and the trace events are systematically
        processed. Results are generated into a CSV file, saved to the working directory under the same name as the target
        application with the suffix _results.csv.
        """

        print "Loading tracecmd data and processing"

        dat_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "results/" + self.application + ".dat")
        self.tc_processor = TracecmdProcessor(dat_path, self.preamble)

        self.tc_processor.print_event_count()
        self.trace_processor.process_trace(self.sys_metrics, self.tc_processor,
                                           self.duration, self.graph, self.event_count, self.subgraph)

        print "Run took a total of %s seconds to run" % (time.time() - self.start_time)


if __name__ == '__main__':
    if not args.commandline:
        app = QApplication(sys.argv)
        interface = MainInterface()
        sys.exit(app.exec_())
    else:
        app = CommandInterface()
        app.run()
