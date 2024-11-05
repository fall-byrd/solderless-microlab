"""
Contains function for starting up the microlab process
"""
import logging
import time
import traceback
import signal
import sys

import hardware.devicelist
import recipes.core
import recipes.state

from multiprocessing import Queue, Process
from typing import Optional
from queue import Empty

from config import microlabConfig as config
from hardware.core import MicroLabHardware


LOGGER = logging.getLogger(__name__)


class MicrolabHardwareManager(Process):

    def __init__(
        self, in_queue: Queue, out_queue: Queue,
        *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._microlab_hardware: MicroLabHardware = MicroLabHardware.get_microlab_hardware_controller()
        self._in_queue = in_queue
        self._out_queue = out_queue
        self._should_run = True

        self._command_dict = {
                "start": recipes.core.start,
                "status": recipes.core.status,
                "stop": recipes.core.stop,
                "selectOption": recipes.core.selectOption,
                "reloadConfig": config.reloadConfig,
                "reloadHardware": self._reload_hardware,
            }

        self._execution_exception = None

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        LOGGER.debug('Begining microlab shutdown process.')
        self._should_run = False

    def _close_out_queue(self):
        while True:
            try:
                self._out_queue.get_nowait()
            except Empty:
                self._out_queue.close()
                break

    def _cleanup(self):
        LOGGER.info("Shutting down microlab.")
        self._microlab_hardware.turnOffEverything()
        LOGGER.info("Shutdown completed.")

        LOGGER.debug('Begining purge of MicrolabHardwareManager out queue')
        self._close_out_queue()
        LOGGER.debug('Completed purge of MicrolabHardwareManager out queue')

        sys.exit(0)

    def _run_command(self, command_string: str, command_args: Optional[str]) -> Optional[str]:
        result = None
        command = self._command_dict[command_string]

        if command_args:
            result = command(command_args)
        else:
            result = command()

        return result

    def _update_queue_data(self):
        if not self._in_queue.empty():
            data = self._in_queue.get(timeout=5)  # Receive data
            result = self._run_command(data["command"], data.get("args", None))
            if result is not None:
                self._out_queue.put(result, timeout=5)  # Send data back

    def _update_microlab(self):
        if recipes.state.currentRecipe:
            recipes.state.currentRecipe.tickTasks()
            recipes.state.currentRecipe.checkStepCompletion()

    def _reload_hardware(self):
        LOGGER.info("Reloading microlab device configuration")
        hardwareConfig = hardware.devicelist.loadHardwareConfiguration()
        deviceDefinitions = hardwareConfig['devices']
        return self._microlab_hardware.loadHardware(deviceDefinitions)

    def run(self):
        self._setup_signal_handlers()

        while self._should_run:
            time.sleep(0.01)
            try:
                self._update_queue_data()
                self._update_microlab()
            except Exception as e:
                self._execution_exception = e
                LOGGER.error(f'While running microlab hardware encountered exception: {e}. Shutting down microlab.')
                LOGGER.debug(traceback.print_exc())
                break

        self._cleanup()
