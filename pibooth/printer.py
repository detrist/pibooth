# -*- coding: utf-8 -*-

"""Pibooth printer handling.
"""

try:
    import cups
    from cups_notify import Subscriber, event
except ImportError:
    cups = None  # CUPS is optional

import tempfile
import os.path as osp
import requests

import pygame
from PIL import Image
from pibooth.utils import LOGGER
from pibooth.pictures import get_picture_factory


PRINTER_TASKS_UPDATED = pygame.USEREVENT + 2

PAPER_FORMATS = {
    '2x6': (2, 6),      # 2x6 pouces - 5x15 cm - 51x152 mm
    '3,5x5': (3.5, 5),  # 3,5x5 pouces - 9x13 cm - 89x127 mm
    '4x6': (4, 6),      # 4x6 pouces - 10x15 cm - 101x152 mm
    '5x7': (5, 7),      # 5x7 pouces - 13x18 cm - 127x178 mm
    '6x8': (6, 8),      # 6x8 pouces - 15x20 cm - 152x203 mm
    '6x9': (6, 9),      # 6x9 pouces - 15x23 cm - 152x229 mm
}


class Printer(object):

    def __init__(self, name='default', max_pages=-1, counters=None):
        self._conn = cups.Connection() if cups else None
        self._notifier = Subscriber(self._conn) if cups else None
        self.name = None
        self.max_pages = max_pages
        self.count = counters
        if not cups:
            LOGGER.warning("No printer found (pycups or pycups-notify not installed)")
            return  # CUPS is not installed

        if not name or name.lower() == 'default':
            self.name = self._conn.getDefault()
            if not self.name and self._conn.getPrinters():
                self.name = list(self._conn.getPrinters().keys())[0]  # Take first one
        elif name in self._conn.getPrinters():
            self.name = name

        if not self.name:
            if name.lower() == 'default':
                LOGGER.warning("No printer configured in CUPS (see http://localhost:631)")
            else:
                LOGGER.warning("No printer named '%s' in CUPS (see http://localhost:631)", name)
        else:
            LOGGER.info("Connected to printer '%s'", self.name)

    def _on_event(self, evt):
        """
        Call for each new printer event.
        """
        LOGGER.info(evt.title)
        pygame.event.post(pygame.event.Event(PRINTER_TASKS_UPDATED,
                                             tasks=self.get_all_tasks()))

    def is_installed(self):
        """Return True if the CUPS server is available for printing.
        """
        return cups is not None and self.name is not None

    def is_available(self):
        """Return False if paper/ink counter is reached or printing is disabled.
        """
        if not self.is_installed():
            return False
        if self.max_pages < 0 or self.count is None:  # No limit
            return True
        return self.count.printed < self.max_pages

    def print_file(self, filename, copies=1):
        """Send a file to the CUPS server to the default printer.
        """
        if not self.name:
            raise EnvironmentError("No printer found (check config file or CUPS config)")
        if not osp.isfile(filename):
            raise IOError("No such file or directory: {}".format(filename))
        
        self.print_file_rest(filename, copies)
        LOGGER.debug("File '%s' sent to the printer", filename)
    
    def print_file_rest(self, filename, copies= 1):
        url = 'http://192.168.250.1:8080/api/v1/printing/'
        files = {'file': open(filename, 'rb')}
        
        for i in range(copies):
            r = requests.post(url, files = files)
            print(r.status_code)

    def cancel_all_tasks(self):
        """Cancel all tasks in the queue.
        """
        if not self.name:
            raise EnvironmentError("No printer found (check config file or CUPS config)")
        self._conn.cancelAllJobs(self.name)

    def get_all_tasks(self):
        """Return a dict (indexed by job ID) of dicts representing all tasks
        in the queue.
        """
        if not self.name:
            return {}  # No printer found
        return self._conn.getJobs(my_jobs=True, requested_attributes=["job-id", "job-name",
                                                                      "job-uri", "job-state"])

    def quit(self):
        """Do cleanup actions.
        """
        if self._notifier:
            self._notifier.unsubscribe_all()
