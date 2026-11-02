"""Professional Qt operator station. Widget state is derived from worker snapshots."""

from collections import deque
from pathlib import Path
from time import perf_counter, strftime

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence, QSurfaceFormat
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..model import LOWER, UPPER
from .viewport import Viewport
from .worker import ControlWorker

STYLE = """
QWidget { background:#101820;
    color:#dfe8ed;
    font-family:'Segoe UI';
    font-size:12px;
    }
QLabel { background:transparent; }
QMainWindow { background:#0c131b;
    }
QFrame#header { background:#131f29;
    border-bottom:1px solid #293944;
    }
QLabel#brand { font-size:21px;
    font-weight:700;
    letter-spacing:1px;
    color:#f6f9fa;
    }
QLabel#eyebrow { color:#51d3ba;
    font-size:10px;
    font-weight:700;
    letter-spacing:2px;
    }
QLabel#muted { color:#7e929f;
    font-size:11px;
    }
QLabel#section { color:#9fb5c2;
    font-size:10px;
    font-weight:700;
    letter-spacing:1px;
    }
QLabel#number { font-family:'Consolas';
    font-size:17px;
    color:#f3f7fa;
    }
QLabel#state { background:#183c36;
    color:#6de2c5;
    padding:7px 14px;
    border-radius:5px;
    font-weight:700;
    }
QLabel#notice { background:#142b34;
    color:#a8cbd8;
    padding:9px;
    border:1px solid #284651;
    border-radius:5px;
    }
QPushButton { background:#1c2b36;
    border:1px solid #334753;
    border-radius:5px;
    padding:7px 10px;
    font-weight:600;
    }
QPushButton:hover { background:#2a3e4d;
    border-color:#5d7e8f;
    }
QPushButton:pressed { background:#344d5a;
    }
QPushButton:disabled { color:#526572;
    background:#17232d;
    border-color:#23333e;
    }
QPushButton#primary { background:#39c5a6;
    color:#071c19;
    border:1px solid #51dcbf;
    }
QPushButton#primary:hover { background:#65ddc2;
    }
QPushButton#primary:disabled { background:#213e39; color:#698c83; border-color:#2d534a; }
QPushButton#danger { background:#512831;
    color:#ff9d9d;
    border:1px solid #87434e;
    }
QDoubleSpinBox,QLineEdit,QComboBox { background:#0c151d;
    border:1px solid #2c414f;
    border-radius:4px;
    padding:6px;
    selection-background-color:#24776f;
    }
QDoubleSpinBox:focus,QLineEdit:focus,QComboBox:focus { border-color:#49c6ad;
    }
QComboBox QAbstractItemView { background:#192a35;
    selection-background-color:#2b685e;
    }
QTabWidget::pane { border:0;
    background:#131e27;
    }
QTabBar::tab { background:#14222d;
    color:#829aa9;
    padding:10px 14px;
    border-bottom:2px solid #223440;
    }
QTabBar::tab:selected { color:#69dfc4;
    border-bottom:2px solid #42c8aa;
    }
QScrollArea { border:0;
    }
QScrollBar:vertical { width:8px;
    background:#121e27;
    }
QScrollBar::handle:vertical { background:#3c525e;
    min-height:25px;
    border-radius:4px;
    }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0;
    }
QProgressBar { border:0;
    border-radius:3px;
    background:#263641;
    max-height:5px;
    }
QProgressBar::chunk { background:#42c7aa;
    border-radius:3px;
    }
QSlider::groove:horizontal { height:4px;
    background:#2c404c;
    border-radius:2px;
    }
QSlider::sub-page:horizontal { background:#3ac8a8;
    }
QSlider::handle:horizontal { background:#87e5d0;
    border:2px solid #183f37;
    width:12px;
    margin:-5px 0;
    border-radius:7px;
    }
QListWidget,QTableWidget { background:#101b24;
    border:1px solid #283c49;
    outline:0;
    }
QListWidget::item { padding:8px;
    }
QListWidget::item:selected { background:#204f48;
    color:#9ef1dc;
    }
QHeaderView::section { background:#1a2934;
    color:#8fa8b8;
    border:0;
    padding:5px;
    font-size:10px;
    }
QTableWidget { gridline-color:#223541;
    }
QSplitter::handle { background:#0d161d;
    width:5px;
    height:5px;
    }
QCheckBox { spacing:7px;
    padding:4px 0;
    }
QToolTip { background:#22333f;
    color:#f2f6f8;
    border:1px solid #496575;
    padding:6px;
    }
"""


def label(text, name="", wrap=False):
    item = QLabel(text)
    item.setObjectName(name)
    item.setWordWrap(wrap)
    return item


def spin(value, minimum, maximum, decimals=2, suffix=""):
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setValue(value)
    box.setSuffix(suffix)
    box.setKeyboardTracking(False)
    box.setMinimumHeight(28)
    return box


def panel():
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)
    return widget, layout


def scroll(widget):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return area


class Workstation(QMainWindow):
    def __init__(self, config: Config, output: Path):
        super().__init__()
        self.output = output
        output.mkdir(parents=True, exist_ok=True)
        self.setWindowTitle("RobotArm-Lab | Professional Workstation 0.2.0")
        self.setMinimumSize(1100, 680)
        self.resize(1540, 940)
        self.snapshot = None
        self.last_event = 0
        self.preview_dirty = False
        self.pending_motion = False
        self.render_fault_held = False
        self.closing = False
        self.heartbeat = deque(maxlen=4096)
        self.last_beat = perf_counter()
        self.buttons = {}
        self.last_teach = ()
        self.last_obstacles = ()
        self.worker = ControlWorker(config, output, self)
        self.setStyleSheet(STYLE)
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(root)
        header = QFrame()
        header.setObjectName("header")
        h = QHBoxLayout(header)
        h.setContentsMargins(22, 9, 22, 9)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(label("RAL / ROBOTARM LAB", "eyebrow"))
        brand.addWidget(label("Professional Workstation", "brand"))
        h.addLayout(brand)
        h.addStretch()
        h.addWidget(label("RAL-6  /  6 AXES\nKINEMATIC SIMULATION", "muted"))
        self.state = label("CONNECTING", "state")
        h.addWidget(self.state)
        self.mode = QComboBox()
        self.mode.addItems(["MANUAL", "AUTO"])
        self.mode.setMinimumWidth(115)
        self.mode.currentTextChanged.connect(lambda v: self.command("set_mode", v))
        h.addWidget(self.mode)
        outer.addWidget(header)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(20, 6, 20, 6)
        toolbar.setSpacing(8)
        for name, title, command, key in (
            ("home", "Home", "home", "F5"),
            ("demo", "Demo cycle", "demo", "F6"),
            ("pause", "Pause", "pause", "Space"),
            ("freeze", "■  Freeze", "freeze", "Escape"),
            ("reset", "Reset scene", "reset", "F9"),
        ):
            button = self.button(
                name,
                title,
                lambda c=command: self.toolbar_action(c),
                "danger" if name == "freeze" else "",
            )
            toolbar.addWidget(button)
            self.shortcut(key, lambda c=command: self.toolbar_action(c))
        toolbar.addStretch()
        toolbar.addWidget(label("SPEED", "section"))
        self.speed = QComboBox()
        self.speed.addItems(["10%", "25%", "50%", "75%", "100%"])
        self.speed.setCurrentText("50%")
        self.speed.currentTextChanged.connect(
            lambda t: self.command("set_speed", int(t[:-1]) / 100)
        )
        toolbar.addWidget(self.speed)
        toolbar.addWidget(self.button("view", "Reset view", lambda: self.viewport.reset_camera()))
        toolbar.addWidget(self.button("capture", "Capture", self.capture))
        outer.addLayout(toolbar)
        self.notice = label("Connecting to isolated control worker…", "notice", True)
        outer.addWidget(self.notice)
        horizontal = QSplitter(Qt.Orientation.Horizontal)
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(285)
        self.tabs.addTab(scroll(self.joint_panel()), "Joint jog")
        self.tabs.addTab(scroll(self.tcp_panel()), "TCP / IK")
        self.tabs.addTab(scroll(self.teach_panel()), "Teach")
        command_panel = QWidget()
        command_layout = QVBoxLayout(command_panel)
        command_layout.setContentsMargins(0, 0, 0, 8)
        command_layout.addWidget(self.tabs, 1)
        command_layout.addWidget(self.button("preview", "Preview target", self.preview_current))
        command_layout.addWidget(
            self.button(
                "execute", "Execute checked target", lambda: self.command("execute"), "primary"
            )
        )
        command_layout.addWidget(
            label("Preview is visual only · execution is collision checked", "muted", True)
        )
        self.tabs.currentChanged.connect(self.target_changed)
        for field in (*self.joint_targets, *self.tcp_targets):
            field.valueChanged.connect(self.target_changed)
        horizontal.addWidget(command_panel)
        center, center_layout = panel()
        center_layout.setContentsMargins(8, 10, 8, 8)
        heading = QHBoxLayout()
        heading.addWidget(label("CELL 01  /  LIVE VIEW", "section"))
        heading.addStretch()
        self.render_health = label("OpenGL initializing", "muted")
        heading.addWidget(self.render_health)
        center_layout.addLayout(heading)
        self.viewport = Viewport()
        center_layout.addWidget(self.viewport, 1)
        hint = QHBoxLayout()
        hint.addWidget(label("Drag: orbit   •   Right drag: pan   •   Wheel: zoom", "muted"))
        hint.addStretch()
        self.proxies = QCheckBox("Collision proxies")
        self.proxies.toggled.connect(self.toggle_proxies)
        hint.addWidget(self.proxies)
        center_layout.addLayout(hint)
        timeline = QHBoxLayout()
        timeline.addWidget(label("TRAJECTORY", "section"))
        self.timeline_value = label("No preview", "muted")
        timeline.addStretch()
        timeline.addWidget(self.timeline_value)
        center_layout.addLayout(timeline)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 1000)
        self.timeline.setValue(1000)
        self.timeline.setToolTip(
            "Inspect the ghost preview. The actual robot is never moved by scrubbing."
        )
        self.timeline.valueChanged.connect(self.scrub)
        center_layout.addWidget(self.timeline)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        center_layout.addWidget(self.progress)
        horizontal.addWidget(center)
        right = QTabWidget()
        self.monitor_tabs = right
        self.monitor_tabs = right
        right.setMinimumWidth(235)
        right.addTab(scroll(self.telemetry_panel()), "Live state")
        right.addTab(scroll(self.scene_panel()), "Scene")
        horizontal.addWidget(right)
        horizontal.setSizes([300, 900, 260])
        horizontal.setStretchFactor(1, 1)
        vertical = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter = vertical
        vertical.addWidget(horizontal)
        log_container, log_layout = panel()
        log_layout.setContentsMargins(18, 8, 18, 8)
        row = QHBoxLayout()
        row.addWidget(label("EVENT STREAM", "section"))
        row.addStretch()
        row.addWidget(label("Bounded to 500 events · full JSONL on disk", "muted"))
        log_layout.addLayout(row)
        self.events = QTableWidget(0, 3)
        self.events.setHorizontalHeaderLabels(["TIME", "EVENT", "DETAIL"])
        self.events.verticalHeader().hide()
        self.events.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.events.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.events.setColumnWidth(0, 80)
        self.events.setColumnWidth(1, 145)
        self.events.setMinimumHeight(65)
        log_layout.addWidget(self.events)
        vertical.addWidget(log_container)
        vertical.setSizes([730, 105])
        outer.addWidget(vertical, 1)
        status = QHBoxLayout()
        status.setContentsMargins(20, 5, 20, 6)
        status.addWidget(
            label("●  LOCAL SIMULATION   |   No hardware safety certification", "muted")
        )
        status.addStretch()
        self.status = label("Starting…", "muted")
        status.addWidget(self.status)
        outer.addLayout(status)
        self.worker.changed.connect(self.receive)
        self.worker.failed.connect(self.show_error)
        self.worker.responded.connect(self.command_finished)
        self.worker.finished.connect(self.worker_finished)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(16)
        self.worker.start()

    def button(self, name, title, callback, style=""):
        b = QPushButton(title)
        b.setObjectName(style or name)
        b.setAccessibleName(name)
        b.clicked.connect(lambda checked=False: callback())
        self.buttons[name] = b
        return b

    def shortcut(self, key, callback):
        a = QAction(self)
        a.setShortcut(QKeySequence(key))
        a.triggered.connect(lambda checked=False: callback())
        self.addAction(a)

    def joint_panel(self):
        widget, layout = panel()
        layout.addWidget(label("JOINT COMMAND", "section"))
        layout.addWidget(
            label(
                "Set targets or jog a single joint. Every move is checked before execution.",
                "muted",
                True,
            )
        )
        self.jog_step = spin(1, 0.1, 10, 1, "°")
        step = QHBoxLayout()
        step.addWidget(label("Jog increment"))
        step.addWidget(self.jog_step)
        layout.addLayout(step)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self.joint_targets = []
        for i in range(6):
            grid.addWidget(label(f"J{i + 1}", "section"), i, 0)
            s = spin(0, float(np.rad2deg(LOWER[i])), float(np.rad2deg(UPPER[i])), 2, "°")
            s.setObjectName(f"joint_target_{i + 1}")
            s.setMinimumWidth(110)
            self.joint_targets.append(s)
            grid.addWidget(s, i, 1)
            grid.addWidget(
                self.button(
                    f"jog_minus_{i}",
                    "−",
                    lambda checked=False, j=i: self.command("jog", j, -self.jog_step.value()),
                ),
                i,
                2,
            )
            grid.addWidget(
                self.button(
                    f"jog_plus_{i}",
                    "+",
                    lambda checked=False, j=i: self.command("jog", j, self.jog_step.value()),
                ),
                i,
                3,
            )
        layout.addLayout(grid)
        layout.addWidget(self.button("copy_joints", "Use current joints", self.copy_joints))
        layout.addWidget(
            label(
                "Preview = ghost only\nExecution = validated quintic motion\n"
                "Freeze = immediate simulation hold",
                "muted",
                True,
            )
        )
        layout.addStretch()
        return widget

    def tcp_panel(self):
        widget, layout = panel()
        layout.addWidget(label("CARTESIAN TARGET", "section"))
        layout.addWidget(
            label(
                "World frame · extrinsic XYZ orientation. "
                "Position and orientation are independently verified.",
                "muted",
                True,
            )
        )
        grid = QGridLayout()
        self.tcp_targets = []
        for i, title in enumerate(("X", "Y", "Z", "Roll", "Pitch", "Yaw")):
            grid.addWidget(label(title), i, 0)
            box = spin(
                0, -2000 if i < 3 else -180, 2000 if i < 3 else 180, 2, " mm" if i < 3 else "°"
            )
            self.tcp_targets.append(box)
            grid.addWidget(box, i, 1)
        layout.addLayout(grid)
        layout.addWidget(self.button("copy_tcp", "Use current TCP", self.copy_tcp))
        layout.addStretch()
        return widget

    def teach_panel(self):
        widget, layout = panel()
        layout.addWidget(label("TEACH LIBRARY", "section"))
        layout.addWidget(
            label(
                "Capture actual joints at rest. Saved locally; replay always rechecks collisions.",
                "muted",
                True,
            )
        )
        self.teach_name = QLineEdit()
        self.teach_name.setPlaceholderText("Pose name")
        self.teach_name.setMaxLength(64)
        layout.addWidget(self.teach_name)
        layout.addWidget(
            self.button(
                "teach_save",
                "Capture current pose",
                lambda: self.command("teach_save", self.teach_name.text()),
            )
        )
        self.teach_list = QListWidget()
        self.teach_list.setMinimumHeight(150)
        layout.addWidget(self.teach_list, 1)
        self.teach_list.currentRowChanged.connect(self.target_changed)
        layout.addWidget(
            self.button(
                "teach_delete",
                "Delete selected",
                lambda: self.command("teach_delete", self.selected_teach()),
            )
        )
        layout.addWidget(
            self.button("program", "Play library sequence", lambda: self.command("program"))
        )
        layout.addWidget(
            label(
                "Sequence playback requires AUTO mode. Library order is the playback order.",
                "muted",
                True,
            )
        )
        return widget

    def telemetry_panel(self):
        widget, layout = panel()
        layout.addWidget(label("JOINT FEEDBACK", "section"))
        self.joint_live = []
        self.joint_bars = []
        for i in range(6):
            row = QHBoxLayout()
            row.addWidget(label(f"J{i + 1}", "section"))
            row.addStretch()
            value = label("—", "number")
            row.addWidget(value)
            layout.addLayout(row)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setTextVisible(False)
            layout.addWidget(bar)
            self.joint_live.append(value)
            self.joint_bars.append(bar)
        layout.addSpacing(10)
        layout.addWidget(label("TOOL CENTER POINT", "section"))
        self.tcp_live = label("—", "number")
        self.tcp_live.setWordWrap(True)
        layout.addWidget(self.tcp_live)
        self.orientation_live = label("—", "muted", True)
        layout.addWidget(self.orientation_live)
        self.velocity_live = label("—", "muted", True)
        layout.addWidget(self.velocity_live)
        layout.addSpacing(8)
        self.safety = label("SAMPLED PATH CHECKS\nEnabled at command and execution", "notice", True)
        layout.addWidget(self.safety)
        layout.addStretch()
        return widget

    def scene_panel(self):
        widget, layout = panel()
        layout.addWidget(label("OBSTACLE BOX", "section"))
        self.obstacle_selection = QComboBox()
        self.obstacle_selection.currentIndexChanged.connect(self.select_box)
        layout.addWidget(self.obstacle_selection)
        layout.addWidget(label("Center and full dimensions in world millimetres.", "muted", True))
        self.box_fields = []
        grid = QGridLayout()
        for i, (title, value) in enumerate(
            zip(
                ("X", "Y", "Z", "Width", "Depth", "Height"),
                (400, 400, 200, 160, 160, 400),
                strict=True,
            )
        ):
            grid.addWidget(label(title), i, 0)
            s = spin(value, -2000 if i < 3 else 1, 2000, 0, " mm")
            grid.addWidget(s, i, 1)
            self.box_fields.append(s)
        layout.addLayout(grid)
        layout.addWidget(self.button("add_box", "Add obstacle", self.add_box))
        layout.addWidget(self.button("update_box", "Update selected obstacle", self.update_box))
        layout.addWidget(self.button("remove_box", "Remove selected obstacle", self.remove_box))
        layout.addWidget(
            self.button("blocker", "Add demo blocker", lambda: self.command("blocker"))
        )
        layout.addWidget(
            self.button("clear_boxes", "Clear obstacles", lambda: self.command("clear_boxes"))
        )
        self.obstacle_count = label("0 obstacles", "muted")
        layout.addWidget(self.obstacle_count)
        layout.addSpacing(12)
        layout.addWidget(label("DISPLAY", "section"))
        for title, attr in (
            ("TCP path and motion trail", "show_path"),
            ("World / TCP coordinate axes", "show_axes"),
        ):
            c = QCheckBox(title)
            c.setChecked(True)
            c.toggled.connect(lambda value, a=attr: setattr(self.viewport, a, value))
            layout.addWidget(c)
        layout.addStretch()
        return widget

    def selected_teach(self):
        item = self.teach_list.currentItem()
        return item.text() if item else ""

    def copy_joints(self):
        if self.snapshot:
            for box, v in zip(self.joint_targets, np.rad2deg(self.snapshot.q), strict=True):
                box.setValue(float(v))

    def copy_tcp(self):
        if self.snapshot:
            for i, (box, v) in enumerate(zip(self.tcp_targets, self.snapshot.tcp, strict=True)):
                box.setValue(v * 1000 if i < 3 else v)

    def preview_ik(self):
        values = [v.value() for v in self.tcp_targets]
        values[:3] = [v / 1000 for v in values[:3]]
        self.command("preview_pose", values)

    def target_changed(self, *_):
        if self.snapshot and self.snapshot.preview is not None and not self.preview_dirty:
            self.preview_dirty = True
            self.buttons["execute"].setEnabled(False)
            self.worker.submit("invalidate")

    def preview_current(self):
        self.preview_dirty = False
        if self.tabs.currentIndex() == 0:
            self.command(
                "preview_joint", np.deg2rad([s.value() for s in self.joint_targets]).tolist()
            )
        elif self.tabs.currentIndex() == 1:
            self.preview_ik()
        else:
            self.command("teach_preview", self.selected_teach())

    def add_box(self):
        v = [s.value() / 1000 for s in self.box_fields]
        self.command("add_box", v[:3], [x / 2 for x in v[3:]])

    def select_box(self, _=None):
        body = self.obstacle_selection.currentData()
        if self.snapshot:
            for key, center, half in self.snapshot.obstacles:
                if key == body:
                    for field, value in zip(
                        self.box_fields, (*center, *np.multiply(half, 2)), strict=True
                    ):
                        field.setValue(float(value) * 1000)

    def update_box(self):
        values = [field.value() / 1000 for field in self.box_fields]
        self.command(
            "update_box",
            self.obstacle_selection.currentData(),
            values[:3],
            [value / 2 for value in values[3:]],
        )

    def remove_box(self):
        self.command("remove_box", self.obstacle_selection.currentData())

    def command(self, name, *args):
        if self.closing:
            return
        if self.snapshot is None or not self.worker.isRunning():
            self.show_error("Control worker is not connected")
            return
        if self.viewport.error and name not in ("freeze", "reset"):
            self.show_error(self.viewport.error + "; restart with a working graphics backend")
            return
        if name in (
            "home",
            "demo",
            "preview_joint",
            "preview_pose",
            "teach_preview",
            "execute",
            "jog",
            "program",
            "resume",
        ):
            if self.pending_motion:
                self.show_error("A motion request is already being validated")
                return
            self.pending_motion = True
            self.buttons["demo"].setEnabled(False)
            self.buttons["execute"].setEnabled(False)
        self.notice.setText(f"{name.replace('_', ' ').capitalize()} requested…")
        self.worker.submit(name, *args)

    def command_finished(self, name: str, elapsed: float, error: str) -> None:
        if name in (
            "home",
            "demo",
            "preview_joint",
            "preview_pose",
            "teach_preview",
            "execute",
            "jog",
            "program",
            "resume",
        ):
            self.pending_motion = False
        if name == "reset" and not error:
            self.viewport.trail.clear()
        if self.snapshot:
            self.receive(self.snapshot)

    def toolbar_action(self, name):
        if name == "pause" and self.snapshot and self.snapshot.state == "PAUSED":
            name = "resume"
        self.command(name)

    def show_error(self, message):
        self.notice.setText(message)
        self.notice.setStyleSheet("background:#44232c; color:#ffb5b8; border-color:#814552;")

    def receive(self, s):
        first = self.snapshot is None
        self.snapshot = s
        if s.state == "STOPPED":
            self.pending_motion = False
        self.viewport.set_snapshot(s)
        self.state.setText(s.state)
        fault = s.state in ("FAULT", "BLOCKED")
        self.state.setStyleSheet("background:#502a32; color:#ffaaaa;" if fault else "")
        idle = s.state in ("IDLE", "STOPPED") and not self.pending_motion
        self.mode.blockSignals(True)
        self.mode.setCurrentText(s.mode)
        self.mode.blockSignals(False)
        self.mode.setEnabled(idle)
        self.speed.blockSignals(True)
        self.speed.setCurrentText(f"{round(s.speed * 100)}%")
        self.speed.blockSignals(False)
        self.buttons["pause"].setText("Resume" if s.state == "PAUSED" else "Pause")
        self.buttons["pause"].setEnabled(s.state in ("RUNNING", "PAUSED"))
        for name in (
            "home",
            "demo",
            "preview",
            "teach_save",
            "teach_delete",
            "program",
        ):
            self.buttons[name].setEnabled(idle and (name != "program" or s.mode == "AUTO"))
        if s.preview is None:
            self.preview_dirty = False
        self.buttons["execute"].setEnabled(
            idle
            and s.preview is not None
            and not self.preview_dirty
            and np.array_equal(s.q, s.preview.start)
        )
        for field in (*self.joint_targets, *self.tcp_targets):
            field.setEnabled(idle)
        for i in range(6):
            for direction in ("minus", "plus"):
                self.buttons[f"jog_{direction}_{i}"].setEnabled(idle and s.mode == "MANUAL")
            self.joint_live[i].setText(f"{np.rad2deg(s.q[i]):+7.2f}°")
            self.joint_bars[i].setValue(round(1000 * (s.q[i] - LOWER[i]) / (UPPER[i] - LOWER[i])))
        self.tcp_live.setText(
            "\n".join(f"{a}  {v * 1000:+8.1f} mm" for a, v in zip("XYZ", s.tcp[:3], strict=True))
        )
        self.safety.setText(
            f"{s.clearance_contacts} CLEARANCE CONTACT(S)\nMotion checks active"
            if s.clearance_contacts
            else "CLEARANCE MONITOR · CLEAR\nSampled motion checks active"
        )
        self.safety.setStyleSheet(
            "background:#44232c; color:#ffb5b8; border-color:#814552;"
            if s.clearance_contacts
            else ""
        )
        self.orientation_live.setText("RPY  " + " / ".join(f"{v:+.1f}°" for v in s.tcp[3:]))
        self.velocity_live.setText(
            f"Peak joint speed  {max(abs(v) for v in np.rad2deg(s.velocity)):.1f}°/s\n"
            f"Sequence  {s.sequence}"
        )
        self.progress.setValue(round(1000 * s.elapsed / s.duration) if s.duration else 0)
        self.obstacle_count.setText(f"{len(s.obstacles)} obstacle(s) in collision world")
        if s.obstacles != self.last_obstacles:
            selected = self.obstacle_selection.currentData()
            self.obstacle_selection.blockSignals(True)
            self.obstacle_selection.clear()
            for index, (body, _, _) in enumerate(s.obstacles):
                self.obstacle_selection.addItem(f"Box {index + 1} · ID {body}", body)
            match = self.obstacle_selection.findData(selected)
            self.obstacle_selection.setCurrentIndex(max(0, match))
            self.obstacle_selection.blockSignals(False)
            self.last_obstacles = s.obstacles
        self.buttons["update_box"].setEnabled(bool(s.obstacles))
        self.buttons["remove_box"].setEnabled(bool(s.obstacles))
        self.timeline.setEnabled(s.preview is not None and s.state != "RUNNING")
        self.timeline_value.setText(
            f"{s.elapsed:.2f} / {s.duration:.2f} s"
            if s.state == "RUNNING"
            else (f"Preview · {s.preview.duration:.2f} s" if s.preview else "No preview")
        )
        if s.error:
            self.show_error(s.error)
        else:
            self.notice.setStyleSheet("")
            self.notice.setText(
                {
                    "PLANNING": "Checking target, joint limits and collision clearance…",
                    "RUNNING": "Executing validated motion · incremental collision checks active",
                    "PAUSED": "Paused at current pose · Resume replans safely from rest",
                }.get(
                    s.state,
                    "Ready · set a target, preview the path, then execute. Simulation only.",
                )
            )
        if s.teach != self.last_teach:
            selected = self.selected_teach()
            self.teach_list.clear()
            self.teach_list.addItems([n for n, _ in s.teach])
            self.last_teach = s.teach
            matches = self.teach_list.findItems(selected, Qt.MatchFlag.MatchExactly)
            if matches:
                self.teach_list.setCurrentItem(matches[0])
        for serial, stamp, kind, detail in s.events:
            if serial <= self.last_event:
                continue
            if self.events.rowCount() >= 500:
                self.events.removeRow(0)
            row = self.events.rowCount()
            self.events.insertRow(row)
            for col, value in enumerate((stamp, kind, detail)):
                self.events.setItem(row, col, QTableWidgetItem(value))
            self.events.setRowHeight(row, 25)
            self.last_event = serial
            self.events.scrollToBottom()
        if first:
            self.copy_joints()
            self.copy_tcp()

    def refresh(self):
        now = perf_counter()
        self.heartbeat.append((now - self.last_beat) * 1000)
        self.last_beat = now
        self.viewport.update()
        self.render_health.setText(f"{self.viewport.fps:.0f} FPS  ·  OPENGL")
        if self.viewport.error:
            if not self.render_fault_held:
                self.render_fault_held = True
                self.worker.submit("freeze")
            self.show_error(self.viewport.error)
        if self.snapshot:
            self.status.setText(
                f"State age {(now - self.snapshot.stamp) * 1000:.0f} ms  |  "
                f"speed {self.snapshot.speed * 100:.0f}%"
            )

    def scrub(self, value):
        self.viewport.preview_fraction = value / 1000
        self.viewport.update()

    def toggle_proxies(self, value):
        self.viewport.show_proxies = value
        self.viewport.update()

    def capture(self):
        path = self.output / f"workstation-{strftime('%Y%m%d-%H%M%S')}.png"
        if not self.grab().save(str(path)):
            self.show_error("Screenshot could not be saved")
        else:
            self.notice.setText(f"Actual workstation capture saved: {path.name}")

    def closeEvent(self, event):
        if self.worker.isRunning():
            self.closing = True
            self.worker.stop_worker()
            self.notice.setText("Closing control worker safely…")
            event.ignore()
        else:
            self.timer.stop()
            event.accept()

    def worker_finished(self):
        if self.closing:
            self.close()
        else:
            self.show_error("Control worker has stopped. Close and restart to reconnect.")


def launch(config: Config, output: Path):
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSamples(4)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    window = Workstation(config, output)
    window.show()
    return app.exec()
