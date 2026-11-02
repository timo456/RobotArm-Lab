"""Qt worker boundary. Only this thread touches the authoritative simulation."""

import queue
import threading
from collections import deque
from time import perf_counter as monotonic

from PySide6.QtCore import QThread, Signal

from ..model import HOME, CommandError
from .engine import Engine


class ControlWorker(QThread):
    changed = Signal(object)
    failed = Signal(str)
    responded = Signal(str, float, str)
    acknowledged = Signal(str, float)

    def __init__(self, config, output, parent=None):
        super().__init__(parent)
        self.config, self.output = config, output
        self.commands = queue.Queue(maxsize=32)
        self.cancel, self.shutdown = threading.Event(), threading.Event()
        self.latencies = deque(maxlen=2048)

    def submit(self, name, *args):
        if name == "freeze":
            self.cancel.set()
            return
        try:
            self.commands.put_nowait((name, args, monotonic()))
        except queue.Full:
            self.failed.emit("Command queue is full; wait for the current operation")

    def stop_worker(self):
        self.shutdown.set()
        self.cancel.set()

    def run(self):
        engine = None
        try:
            engine = Engine(self.config, self.output, self.cancel)
            self.changed.emit(engine.snapshot())
            previous = monotonic()
            accumulated = 0.0
            published = 0.0
            while not self.shutdown.is_set():
                if self.cancel.is_set():
                    while True:
                        try:
                            self.commands.get_nowait()
                        except queue.Empty:
                            break
                    engine.freeze()
                    self.changed.emit(engine.snapshot())
                try:
                    name, args, requested = self.commands.get_nowait()
                except queue.Empty:
                    name = ""
                if name:
                    self.acknowledged.emit(name, requested)
                    error = ""
                    try:
                        if name in (
                            "preview_joint",
                            "preview_pose",
                            "execute",
                            "home",
                            "demo",
                            "jog",
                            "teach_preview",
                            "program",
                        ):
                            engine.phase = "PLANNING"
                            self.changed.emit(engine.snapshot())
                        if name == "home":
                            engine.move(HOME)
                        elif name == "teach_preview":
                            if args[0] not in engine.teach:
                                raise CommandError("Select an existing teach point")
                            engine.preview_joint(engine.teach[args[0]])
                        elif name == "program":
                            engine.program(list(engine.teach.values()))
                        elif name in {
                            "preview_joint",
                            "preview_pose",
                            "execute",
                            "jog",
                            "pause",
                            "resume",
                            "set_speed",
                            "set_mode",
                            "demo",
                            "add_box",
                            "update_box",
                            "remove_box",
                            "blocker",
                            "clear_boxes",
                            "reset",
                            "teach_save",
                            "teach_delete",
                            "invalidate",
                        }:
                            getattr(engine, name)(*args)
                        else:
                            raise CommandError(f"Unknown workstation command: {name}")
                    except (ValueError, OSError, RuntimeError, TypeError) as exc:
                        error = engine.error = str(exc)
                        engine.notify("rejected", error)
                        self.failed.emit(error)
                    finally:
                        engine.phase = ""
                    elapsed = (monotonic() - requested) * 1000
                    self.latencies.append((name, elapsed, not error))
                    self.changed.emit(engine.snapshot())
                    self.responded.emit(name, elapsed, error)
                    previous = monotonic()
                    accumulated = 0.0
                now = monotonic()
                accumulated = min(accumulated + now - previous, 0.05)
                previous = now
                try:
                    while accumulated >= self.config.control_dt:
                        engine.tick(self.config.control_dt)
                        accumulated -= self.config.control_dt
                except (ValueError, OSError, RuntimeError) as exc:
                    engine.error = str(exc)
                    engine.notify("fault", str(exc))
                    engine.sequence.clear()
                    self.failed.emit(str(exc))
                    if engine.control.state == "RUNNING":
                        try:
                            engine.freeze()
                        except (ValueError, OSError):
                            pass
                if now - published >= 1 / 30:
                    self.changed.emit(engine.snapshot())
                    published = now
                self.shutdown.wait(0.002)
        except Exception as exc:
            self.failed.emit(f"Control worker stopped: {exc}")
        finally:
            if engine is not None:
                engine.close()
