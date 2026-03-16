import sys
import os
import copy
import math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox, QComboBox, QFileDialog,
    QMessageBox, QSplitter, QSizePolicy, QGraphicsScene, QGraphicsView,
    QDockWidget, QDialog, QDialogButtonBox, QSpinBox, QToolBar,
    QAction, QPlainTextEdit, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import (
    QFont, QColor, QPen, QBrush, QPainter, QPolygonF, QKeySequence
)

from src.parser import parse_file, parse_program
from src.state import Machine, Thread, Message, Promise
from src.execution_engine import ExecutionEngine, ReadChoice
from src.instructions import Read, Write, If, Loop, AccessMode



#FONTS 

MONO       = QFont('Consolas', 14)
MONO_SMALL = QFont('Consolas', 13)
MONO_BOLD  = QFont('Consolas', 14); MONO_BOLD.setBold(True)
TITLE_FONT = QFont('Consolas', 16); TITLE_FONT.setBold(True)
SCENE_FONT = QFont('Consolas', 12)
SCENE_BOLD = QFont('Consolas', 12); SCENE_BOLD.setBold(True)



#COLORS

C = {
    'bg':       QColor('#1e1e2e'),
    'panel':    QColor('#2a2a3d'),
    'border':   QColor('#3a3a5c'),
    'text':     QColor('#cdd6f4'),
    'dim':      QColor('#6c7086'),
    'accent':   QColor('#89b4fa'),
    'green':    QColor('#a6e3a1'),
    'red':      QColor('#f38ba8'),
    'yellow':   QColor('#f9e2af'),
    'orange':   QColor('#fab387'),
    'purple':   QColor('#cba6f7'),
    'btn':      QColor('#313244'),
    'header':   QColor('#181825'),
    'scene_bg': QColor('#11111b'),
    'msg_box':  QColor('#313244'),
    'msg_init': QColor('#45475a'),
}

THREAD_COLORS = [C['accent'], C['green'], C['orange'], C['purple']]


#STYLESHEET 

STYLESHEET = """
QMainWindow { background-color: #1e1e2e; }
QDockWidget {
    color: #89b4fa; font-family: Consolas; font-size: 14px; font-weight: bold;
    titlebar-close-icon: none; titlebar-normal-icon: none;
}
QDockWidget::title {
    background-color: #181825; padding: 6px; border: 1px solid #3a3a5c;
}
QLabel { color: #cdd6f4; font-family: Consolas; font-size: 13px; }
QTextEdit, QPlainTextEdit {
    background-color: #181825; color: #cdd6f4; border: 1px solid #3a3a5c;
    border-radius: 4px; font-family: Consolas; font-size: 15px; padding: 6px;
}
QPushButton {
    background-color: #313244; color: #cdd6f4; border: 1px solid #3a3a5c;
    border-radius: 4px; padding: 8px 18px; font-family: Consolas;
    font-size: 13px; font-weight: bold; min-height: 20px;
}
QPushButton:hover { background-color: #45475a; border-color: #89b4fa; }
QPushButton:disabled { color: #6c7086; border-color: #2a2a3d; }
QComboBox {
    background-color: #313244; color: #cdd6f4; border: 1px solid #3a3a5c;
    border-radius: 4px; padding: 6px 10px; font-family: Consolas;
    font-size: 13px; min-height: 20px;
}
QComboBox QAbstractItemView {
    background-color: #2a2a3d; color: #cdd6f4;
    selection-background-color: #45475a; font-size: 13px;
}
QComboBox::drop-down { border: none; }
QStatusBar {
    background-color: #181825; color: #6c7086;
    font-family: Consolas; font-size: 12px;
}
QToolBar {
    background-color: #181825; border: none; padding: 4px; spacing: 8px;
}
QGraphicsView {
    background-color: #11111b; border: 1px solid #3a3a5c; border-radius: 4px;
}
QSplitter::handle { background-color: #3a3a5c; }
QDialog { background-color: #2a2a3d; }
QSpinBox {
    background-color: #313244; color: #cdd6f4; border: 1px solid #3a3a5c;
    border-radius: 4px; padding: 6px; font-family: Consolas; font-size: 13px;
}
"""


#HELPERS

def hcol(text, hex_color):
     #HTML colored text
    return f'<span style="color:{hex_color}">{text}</span>'


def draw_arrow(scene, x1, y1, x2, y2, color, width=2):
    """Draw a line with arrowhead on a QGraphicsScene."""
    scene.addLine(x1, y1, x2, y2, QPen(color, width))
    angle = math.atan2(y2 - y1, x2 - x1)
    sz = 8
    p1 = QPointF(x2 - sz * math.cos(angle - math.pi/6),
                 y2 - sz * math.sin(angle - math.pi/6))
    p2 = QPointF(x2 - sz * math.cos(angle + math.pi/6),
                 y2 - sz * math.sin(angle + math.pi/6))
    scene.addPolygon(QPolygonF([QPointF(x2, y2), p1, p2]),
                     QPen(color, 1), QBrush(color))



#CUSTOM DARK DIALOGS

class DarkPromiseDialog(QDialog):
    """Dark-themed dialog for entering promise location and value."""

    def __init__(self, parent, thread_id, locations):
        super().__init__(parent)
        self.setWindowTitle(f"Thread {thread_id} — Make a Promise")
        self.setStyleSheet(STYLESHEET + """
            QDialog { min-width: 350px; }
            QLabel { font-size: 13px; font-weight: bold; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        #Title
        title = QLabel(f"Thread {thread_id}: Promise a future write")
        title.setStyleSheet("color: #f9e2af; font-size: 14px;")
        layout.addWidget(title)

        #Location
        layout.addWidget(QLabel("Location:"))
        self.loc_combo = QComboBox()
        self.loc_combo.addItems(locations)
        self.loc_combo.setMinimumHeight(32)
        layout.addWidget(self.loc_combo)

        #Value
        layout.addWidget(QLabel("Value:"))
        self.val_spin = QSpinBox()
        self.val_spin.setRange(0, 9999)
        self.val_spin.setValue(1)
        self.val_spin.setMinimumHeight(32)
        layout.addWidget(self.val_spin)

        #Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet("""
            QPushButton { min-width: 80px; min-height: 28px; font-size: 12px; }
        """)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @property
    def location(self):
        return self.loc_combo.currentText()

    @property
    def value(self):
        return self.val_spin.value()



#TIMELINE 

class TimelineScene(QGraphicsScene):
    #Thread lanes with colored action blocks

    def __init__(self):
        super().__init__()
        self.setBackgroundBrush(C['scene_bg'])
        self.events = []
        self.thread_ids = []
        self.lane_h = 55
        self.block_w = 120
        self.pad = 15
        self.hdr_w = 70

    def reset(self, thread_ids):
        self.clear()
        self.events = []
        self.thread_ids = thread_ids
        self._draw()

    def add_event(self, step, tid, desc, etype='normal'):
        self.events.append((step, tid, desc, etype))
        self._draw()

    def _draw(self):
        self.clear()
        #Lane labels and lines
        for i, tid in enumerate(self.thread_ids):
            y = i * self.lane_h + self.pad
            col = THREAD_COLORS[i % len(THREAD_COLORS)]
            t = self.addText(f"T{tid}", SCENE_BOLD)
            t.setDefaultTextColor(col)
            t.setPos(10, y + 14)
            pen = QPen(QColor(col.red(), col.green(), col.blue(), 50), 1, Qt.DashLine)
            self.addLine(self.hdr_w, y + self.lane_h//2, 3000, y + self.lane_h//2, pen)

        #Event blocks
        type_colors = {
            'write': C['accent'], 'read': C['green'], 'if': C['purple'],
            'loop': C['purple'], 'promise': C['yellow'], 'fulfill': C['orange'],
            'cert_fail': C['red'], 'normal': C['dim'],
        }
        for idx, (step, tid, desc, etype) in enumerate(self.events):
            lane = self.thread_ids.index(tid) if tid in self.thread_ids else 0
            y = lane * self.lane_h + self.pad + 4
            x = self.hdr_w + idx * (self.block_w + 8)
            col = type_colors.get(etype, C['dim'])

            self.addRect(x, y, self.block_w, self.lane_h - 12,
                         QPen(col, 1.5),
                         QBrush(QColor(col.red(), col.green(), col.blue(), 35)))
            st = self.addText(f"#{step}", SCENE_FONT)
            st.setDefaultTextColor(C['dim'])
            st.setPos(x + 3, y)
            dt = self.addText(desc[:15], SCENE_FONT)
            dt.setDefaultTextColor(col)
            dt.setPos(x + 5, y + 17)

        w = self.hdr_w + len(self.events) * (self.block_w + 8) + 80
        h = len(self.thread_ids) * self.lane_h + self.pad * 2
        self.setSceneRect(0, 0, max(w, 500), max(h, 80))



#MEMORY CHAIN

class MemoryScene(QGraphicsScene):
    #Linked boxes per location with view front markers

    def __init__(self):
        super().__init__()
        self.setBackgroundBrush(C['scene_bg'])
        self.bw = 100
        self.bh = 60
        self.gap = 35
        self.row_h = 90
        self.lbl_w = 55

    def update(self, machine):
        self.clear()
        if not machine:
            return
        locs = sorted(machine.memory.locations)

        for row, loc in enumerate(locs):
            y = row * self.row_h + 10
            msgs = machine.memory.get_messages(loc)

            lbl = self.addText(f"{loc}:", SCENE_BOLD)
            lbl.setDefaultTextColor(C['accent'])
            lbl.setPos(5, y + 18)

            for col, msg in enumerate(msgs):
                x = self.lbl_w + col * (self.bw + self.gap)
                bc = C['msg_init'] if (msg.timestamp == 0 and msg.value == 0) else (
                     C['orange'] if msg.view_from else C['msg_box'])

                self.addRect(x, y, self.bw, self.bh,
                             QPen(QColor(bc.red(), bc.green(), bc.blue(), 180), 1.5),
                             QBrush(QColor(bc.red(), bc.green(), bc.blue(), 40)))

                vt = self.addText(f"val={msg.value}", SCENE_FONT)
                vt.setDefaultTextColor(C['text'])
                vt.setPos(x + 6, y + 4)

                tt = self.addText(f"ts={msg.timestamp}", SCENE_FONT)
                tt.setDefaultTextColor(C['dim'])
                tt.setPos(x + 6, y + 20)

                if msg.view_from:
                    rt = self.addText("REL", SCENE_FONT)
                    rt.setDefaultTextColor(C['yellow'])
                    rt.setPos(x + 6, y + 38)

                if col < len(msgs) - 1:
                    ax = x + self.bw
                    ay = y + self.bh // 2
                    draw_arrow(self, ax, ay, ax + self.gap, ay, C['dim'], 1.5)

            #View front markers
            for thread in machine.threads:
                tc = THREAD_COLORS[(thread.thread_id - 1) % len(THREAD_COLORS)]
                vf = thread.get_view_front(loc)
                if vf > 0:
                    for col, msg in enumerate(msgs):
                        if msg.timestamp == vf:
                            mx = self.lbl_w + col * (self.bw + self.gap) + self.bw // 2
                            my = y + self.bh + 2
                            tri = QPolygonF([
                                QPointF(mx - 5, my + 10),
                                QPointF(mx + 5, my + 10),
                                QPointF(mx, my)])
                            self.addPolygon(tri, QPen(tc, 1), QBrush(tc))
                            mt = self.addText(f"T{thread.thread_id}", SCENE_FONT)
                            mt.setDefaultTextColor(tc)
                            mt.setPos(mx - 8, my + 10)
                            break

        mc = max((len(machine.memory.get_messages(l)) for l in locs), default=1)
        self.setSceneRect(0, 0, max(self.lbl_w + mc * (self.bw+self.gap) + 60, 350),
                          max(len(locs) * self.row_h + 40, 80))



#PROMISE LIFECYCLE 

class PromiseScene(QGraphicsScene):
    #CREATED -> CERTIFIED or FAILED -> FULFILLED

    def __init__(self):
        super().__init__()
        self.setBackgroundBrush(C['scene_bg'])
        self.bw = 90
        self.bh = 32
        self.row_h = 52

    def update_data(self, promises, failed):
        self.clear()
        items = [('ok', p) for p in promises] + [('fail', f) for f in failed]
        if not items:
            t = self.addText("No promises yet", SCENE_FONT)
            t.setDefaultTextColor(C['dim'])
            t.setPos(10, 10)
            self.setSceneRect(0, 0, 200, 40)
            return

        for row, (kind, data) in enumerate(items):
            y = row * self.row_h + 8

            if kind == 'ok':
                p = data
                tc = THREAD_COLORS[(p.thread_id - 1) % len(THREAD_COLORS)]
                lbl = self.addText(f"T{p.thread_id}: {p.location}={p.value}", SCENE_BOLD)
                lbl.setDefaultTextColor(tc)
                lbl.setPos(5, y + 6)

                stages = [("CREATED", C['yellow'], True),
                          ("CERTIFIED", C['yellow'], True),
                          ("FULFILLED", C['green'], p.fulfilled)]
                for ci, (name, col, active) in enumerate(stages):
                    x = 150 + ci * (self.bw + 30)
                    pc = col if active else C['dim']
                    self.addRect(x, y, self.bw, self.bh,
                                 QPen(pc, 1.5),
                                 QBrush(QColor(pc.red(), pc.green(), pc.blue(), 40)
                                        if active else Qt.NoBrush))
                    st = self.addText(name, SCENE_FONT)
                    st.setDefaultTextColor(pc)
                    st.setPos(x + 3, y + 7)
                    if active:
                        mk = self.addText("✓", SCENE_BOLD)
                        mk.setDefaultTextColor(pc)
                        mk.setPos(x + self.bw - 16, y + 5)
                    if ci < 2:
                        draw_arrow(self, x + self.bw, y + self.bh//2,
                                   x + self.bw + 30, y + self.bh//2,
                                   pc if active else C['dim'], 1)
            else:
                tid, loc, val = data
                tc = THREAD_COLORS[(tid - 1) % len(THREAD_COLORS)]
                lbl = self.addText(f"T{tid}: {loc}={val}", SCENE_BOLD)
                lbl.setDefaultTextColor(tc)
                lbl.setPos(5, y + 6)

                x = 150
                self.addRect(x, y, self.bw, self.bh,
                             QPen(C['yellow'], 1.5),
                             QBrush(QColor(C['yellow'].red(), C['yellow'].green(),
                                          C['yellow'].blue(), 40)))

                st = self.addText("CREATED", SCENE_FONT)
                st.setDefaultTextColor(C['yellow'])
                st.setPos(x + 3, y + 7)

                draw_arrow(self, x + self.bw, y + self.bh//2,
                           x + self.bw + 30, y + self.bh//2, C['red'], 1)
                x2 = x + self.bw + 30
                self.addRect(x2, y, self.bw, self.bh,
                             QPen(C['red'], 2),
                             QBrush(QColor(C['red'].red(), C['red'].green(),
                                          C['red'].blue(), 40)))
                ft = self.addText("FAILED ✖", SCENE_FONT)
                ft.setDefaultTextColor(C['red'])
                ft.setPos(x2 + 5, y + 7)

        self.setSceneRect(0, 0, 550, max(len(items) * self.row_h + 20, 50))



#MAIN WINDOW

class MainWindow(QMainWindow):
    def __init__(self, filepath=None):
        super().__init__()
        self.setWindowTitle("Promises Visualised — Execution Explorer")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet(STYLESHEET)
        self.setDockOptions(
            QMainWindow.AnimatedDocks |
            QMainWindow.AllowNestedDocks |
            QMainWindow.AllowTabbedDocks)

        # State
        self.machine = None
        self.engine = None
        self.pending_read = None
        self.failed_promises = []
        self.filepath = None
        self._undo_stack = []

        self._build_toolbar()
        self._build_docks()
        self._build_controls_dock()
        self.statusBar().showMessage("Load a program or type one in the editor.")

        if filepath:
            self._load_file(filepath)

    #Toolbar 

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_load = QPushButton("Load Program")
        self.btn_load.clicked.connect(self._on_load)
        tb.addWidget(self.btn_load)

        self.btn_run_editor = QPushButton("Run Editor")
        self.btn_run_editor.clicked.connect(self._on_run_editor)
        tb.addWidget(self.btn_run_editor)

        self.btn_reset = QPushButton("  Reset  ")
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_reset.setEnabled(False)
        tb.addWidget(self.btn_reset)

        self.btn_undo = QPushButton("  Undo  ")
        self.btn_undo.clicked.connect(self._on_undo)
        self.btn_undo.setEnabled(False)
        self.btn_undo.setShortcut(QKeySequence("Ctrl+Z"))
        tb.addWidget(self.btn_undo)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.lbl_step = QLabel("  Step: 0  ")
        self.lbl_step.setStyleSheet("color: #89b4fa; font-size: 17px; font-weight: bold;")
        tb.addWidget(self.lbl_step)

    #Dock Panels 
    def _build_docks(self):
        # Threads 
        self.threads_display = QTextEdit()
        self.threads_display.setReadOnly(True)
        self._dock_threads = self._make_dock("Threads", self.threads_display, Qt.LeftDockWidgetArea)

        #Code Editor
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Type a program here, then click 'Run Editor'\n"
            "Example:\n"
            "Thread 1:\n"
            "    x = 1\n"
            "    r1 = y\n\n"
            "Thread 2:\n"
            "    y = 1\n"
            "    r2 = x\n")
        self._dock_editor = self._make_dock("Code Editor", self.editor, Qt.LeftDockWidgetArea)
        self.tabifyDockWidget(self._dock_threads, self._dock_editor)
        self._dock_threads.raise_()

        #Memory
        self.mem_scene = MemoryScene()
        self.mem_view = QGraphicsView(self.mem_scene)
        self.mem_view.setRenderHint(QPainter.Antialiasing)
        self._dock_memory = self._make_dock("Memory — Message Chains", self.mem_view, Qt.RightDockWidgetArea)

        #Promise Lifecycle 
        self.prom_scene = PromiseScene()
        self.prom_view = QGraphicsView(self.prom_scene)
        self.prom_view.setRenderHint(QPainter.Antialiasing)
        self._dock_promises = self._make_dock("Promise Lifecycle", self.prom_view, Qt.RightDockWidgetArea)

        #Timeline 
        self.timeline_scene = TimelineScene()
        self.timeline_view = QGraphicsView(self.timeline_scene)
        self.timeline_view.setRenderHint(QPainter.Antialiasing)
        self._dock_timeline = self._make_dock("Execution Timeline", self.timeline_view, Qt.BottomDockWidgetArea)

        #Log 
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self._dock_log = self._make_dock("Execution Log", self.log_display, Qt.BottomDockWidgetArea)
        self.tabifyDockWidget(self._dock_timeline, self._dock_log)
        self._dock_timeline.raise_()

    def _make_dock(self, title, widget, area):
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable)
        self.addDockWidget(area, dock)
        return dock

    #Controls Dock 

    def _build_controls_dock(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        #Row 1- thread + execute + promise
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Thread:"))
        self.thread_combo = QComboBox()
        self.thread_combo.setMinimumWidth(180)
        r1.addWidget(self.thread_combo)

        self.btn_exec = QPushButton("  Execute  ")
        self.btn_exec.setStyleSheet("QPushButton { border-color: #a6e3a1; }")
        self.btn_exec.clicked.connect(self._on_execute)
        self.btn_exec.setEnabled(False)
        r1.addWidget(self.btn_exec)

        self.btn_prom = QPushButton("  Promise  ")
        self.btn_prom.setStyleSheet("QPushButton { border-color: #f9e2af; }")
        self.btn_prom.clicked.connect(self._on_promise)
        self.btn_prom.setEnabled(False)
        r1.addWidget(self.btn_prom)

        r1.addStretch()
        layout.addLayout(r1)

        #Row 2- read message picker
        r2 = QHBoxLayout()
        self.lbl_read = QLabel("")
        r2.addWidget(self.lbl_read)
        self.msg_combo = QComboBox()
        self.msg_combo.setMinimumWidth(320)
        self.msg_combo.setVisible(False)
        r2.addWidget(self.msg_combo)
        self.btn_confirm = QPushButton("  Confirm Read  ")
        self.btn_confirm.clicked.connect(self._on_confirm_read)
        self.btn_confirm.setVisible(False)
        r2.addWidget(self.btn_confirm)
        r2.addStretch()
        layout.addLayout(r2)

        dock = QDockWidget("Controls", self)
        dock.setWidget(w)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

    #File / Editor Loading

    def _on_load(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Open Program", "examples/", "Text Files (*.txt);;All (*)")
        if fp:
            self._load_file(fp)

    def _on_run_editor(self):
        text = self.editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty", "Type a program in the editor first.")
            return
        try:
            threads = parse_program(text)
        except SyntaxError as e:
            QMessageBox.critical(self, "Parse Error", str(e))
            return
        self._init_machine(threads, "(editor)")

    def _load_file(self, fp):
        try:
            threads = parse_file(fp)
        except (SyntaxError, FileNotFoundError) as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.filepath = fp
        #Load text into editor too
        with open(fp) as f:
            self.editor.setPlainText(f.read())
        self._init_machine(threads, os.path.basename(fp))

    def _init_machine(self, threads, name):
        self.machine = Machine(threads)
        self.machine.initialize_memory_for_threads()
        self.engine = ExecutionEngine(self.machine)
        self.pending_read = None
        self.failed_promises = []
        self._undo_stack = []

        self.btn_reset.setEnabled(True)
        self.btn_exec.setEnabled(True)
        self.btn_prom.setEnabled(True)
        self.btn_undo.setEnabled(False)

        self.timeline_scene.reset([t.thread_id for t in self.machine.threads])
        self.log_display.clear()
        self._log(f"Loaded: {name} ({len(threads)} threads)")
        self.statusBar().showMessage(f"Loaded {name}")

        self._hide_read_ui()
        self._refresh()
        self._refresh_combo()

    def _on_reset(self):
        if self.filepath:
            self._load_file(self.filepath)
        else:
            self._on_run_editor()

    #Undo-Backtracking 

    def _save_undo(self):
        #snapshot current state before making a change.
        if not self.machine:
            return
        snapshot = {
            'machine': copy.deepcopy(self.machine),
            'step_count': self.engine.step_count,
            'events': list(self.timeline_scene.events),
            'failed': list(self.failed_promises),
        }
        self._undo_stack.append(snapshot)
        self.btn_undo.setEnabled(True)

    def _on_undo(self):
        if not self._undo_stack:
            return
        snap = self._undo_stack.pop()

        self.machine = snap['machine']
        self.engine = ExecutionEngine(self.machine)
        self.engine.step_count = snap['step_count']
        self.timeline_scene.events = snap['events']
        self.timeline_scene._draw()
        self.failed_promises = snap['failed']
        self.pending_read = None

        self.btn_exec.setEnabled(True)
        self.btn_prom.setEnabled(True)
        self.btn_undo.setEnabled(len(self._undo_stack) > 0)

        self._log(f"↩ Undo — back to step {self.engine.step_count}")
        self.statusBar().showMessage(f"Undone to step {self.engine.step_count}")
        self._hide_read_ui()
        self._refresh()
        self._refresh_combo()

    #Execute 

    def _on_execute(self):
        if not self.machine or self.machine.is_finished:
            return
        tid = self.thread_combo.currentData()
        if tid is None:
            return

        self._save_undo()
        thread = self.machine.get_thread(tid)
        instr = thread.next_instruction

        result = self.engine.step_thread(thread)

        if isinstance(result, ReadChoice):
            self.pending_read = result
            self._show_read_ui(result)
            return

        step = self.engine.step_count
        if isinstance(instr, Write):
            # Check fulfillment
            fulfilled = any(p.fulfilled and p.location == instr.location
                           and p.thread_id == tid for p in self.machine.promises)
            if fulfilled:
                self._log(f"Step {step}: T{tid} fulfilled {instr}")
                self.timeline_scene.add_event(step, tid, f"F({instr})", 'fulfill')
            else:
                self._log(f"Step {step}: T{tid} wrote {instr}")
                self.timeline_scene.add_event(step, tid, f"W({instr})", 'write')
        elif isinstance(instr, If):
            self._log(f"Step {step}: T{tid} eval {instr}")
            self.timeline_scene.add_event(step, tid, str(instr), 'if')
        elif isinstance(instr, Loop):
            self._log(f"Step {step}: T{tid} eval {instr}")
            self.timeline_scene.add_event(step, tid, str(instr), 'loop')

        # Auto-step IF/LOOP
        while not thread.is_finished and isinstance(thread.next_instruction, (If, Loop)):
            ai = thread.next_instruction
            result = self.engine.step_thread(thread)
            s = self.engine.step_count
            self.timeline_scene.add_event(s, tid, str(ai), 'if' if isinstance(ai, If) else 'loop')
            if isinstance(result, ReadChoice):
                self.pending_read = result
                self._show_read_ui(result)
                self._refresh()
                return

        self._refresh()
        self._refresh_combo()

    #Read UI 

    def _show_read_ui(self, rc):
        tid = rc.thread.thread_id
        loc = rc.instruction.location
        m = rc.instruction.mode
        ms = f" [{m.value}]" if m != AccessMode.RLX else ""
        self.lbl_read.setText(f"T{tid} reads {loc}{ms} — pick message:")
        self.lbl_read.setStyleSheet("color: #a6e3a1; font-size: 13px; font-weight: bold;")

        self.msg_combo.clear()
        self.msg_combo.setVisible(True)
        self.btn_confirm.setVisible(True)

        for i, msg in enumerate(rc.available_messages):
            vf = " [REL]" if msg.view_from else ""
            self.msg_combo.addItem(
                f"[{i}] val={msg.value}  ts={msg.timestamp}{vf}", i)

        self.btn_exec.setEnabled(False)
        self.btn_prom.setEnabled(False)

    def _hide_read_ui(self):
        self.lbl_read.setText("")
        self.msg_combo.setVisible(False)
        self.btn_confirm.setVisible(False)
        self.pending_read = None
        if self.machine and not self.machine.is_finished:
            self.btn_exec.setEnabled(True)
            self.btn_prom.setEnabled(True)

    def _on_confirm_read(self):
        if not self.pending_read:
            return
        idx = self.msg_combo.currentData()
        if idx is None:
            return

        rc = self.pending_read
        msg = rc.available_messages[idx]
        tid = rc.thread.thread_id
        loc = rc.instruction.location
        mode = rc.instruction.mode

        self.engine.step_thread(rc.thread, read_choice=msg)
        step = self.engine.step_count
        acq = " [ACQ]" if mode == AccessMode.ACQ else ""
        self._log(f"Step {step}: T{tid} read {loc}={msg.value} ts={msg.timestamp}{acq}")
        self.timeline_scene.add_event(step, tid, f"R({loc})={msg.value}", 'read')

        #Auto-step IF/LOOP
        thread = rc.thread
        while not thread.is_finished and isinstance(thread.next_instruction, (If, Loop)):
            ai = thread.next_instruction
            result = self.engine.step_thread(thread)
            s = self.engine.step_count
            self.timeline_scene.add_event(s, tid, str(ai), 'if' if isinstance(ai, If) else 'loop')
            if isinstance(result, ReadChoice):
                self.pending_read = result
                self._show_read_ui(result)
                self._refresh()
                return

        self._hide_read_ui()
        self._refresh()
        self._refresh_combo()

    #Promise

    def _on_promise(self):
        if not self.machine or self.machine.is_finished:
            return
        tid = self.thread_combo.currentData()
        if tid is None:
            return

        thread = self.machine.get_thread(tid)
        locs = sorted(self.machine.memory.locations)

        dlg = DarkPromiseDialog(self, tid, locs)
        if dlg.exec_() != QDialog.Accepted:
            return

        location = dlg.location
        value = dlg.value

        self._save_undo()
        self._log(f"T{tid} attempts promise {location}={value}...")

        result = self.engine.create_promise(thread, location, value)
        step = self.engine.step_count

        if result:
            self._log(f"  ✓ Certification PASSED — promise accepted!")
            self.timeline_scene.add_event(step, tid, f"P({location}={value})", 'promise')
            self.statusBar().showMessage(f"T{tid} promised {location}={value}")
        else:
            self._log(f"  ✖ Certification FAILED — promise rejected!")
            self.failed_promises.append((tid, location, value))
            self.timeline_scene.add_event(step, tid, f"P({location}={value})✖", 'cert_fail')
            self.statusBar().showMessage(f"T{tid}: {location}={value} REJECTED")

        self._refresh()
        self._refresh_combo()

    #Refresh 

    def _refresh(self):
        if not self.machine:
            return
        self._refresh_threads()
        self.mem_scene.update(self.machine)
        self.prom_scene.update_data(self.machine.promises, self.failed_promises)
        self.lbl_step.setText(f"  Step: {self.engine.step_count}  ")

        if self.machine.is_finished:
            self._on_complete()

    def _refresh_threads(self):
        html = ""
        for t in self.machine.threads:
            tid = t.thread_id
            tc = THREAD_COLORS[(tid-1) % len(THREAD_COLORS)].name()
            if t.is_finished:
                st = hcol("DONE", C['green'].name())
            else:
                st = hcol(f"next: {t.next_instruction}", C['orange'].name())

            html += f"<b>{hcol(f'Thread {tid}', tc)}</b> [{st}]<br>"

            if t.registers:
                rs = ", ".join(f"{hcol(k, C['yellow'].name())}={v}" for k, v in t.registers.items())
            else:
                rs = hcol("none", C['dim'].name())
            html += f"&nbsp;&nbsp;registers: {rs}<br>"

            if t.view_fronts:
                vs = ", ".join(f"{hcol(k, C['yellow'].name())}&gt;={v}" for k, v in t.view_fronts.items())
            else:
                vs = hcol("all&gt;=0", C['dim'].name())
            html += f"&nbsp;&nbsp;view fronts: {vs}<br>"

            pend = self.machine.get_promises_for_thread(tid)
            if pend:
                ps = ", ".join(hcol(f"{p.location}={p.value}", C['yellow'].name()) for p in pend)
                html += f"&nbsp;&nbsp;promises: {ps}<br>"

            if not t.is_finished:
                prog = " ; ".join(hcol(str(i), C['text'].name()) for i in t.program)
                html += f"&nbsp;&nbsp;program: {prog}<br>"

            html += "<br>"
        self.threads_display.setHtml(html)

    def _refresh_combo(self):
        self.thread_combo.clear()
        if not self.machine:
            return
        for t in self.machine.get_active_threads():
            self.thread_combo.addItem(f"Thread {t.thread_id} — {t.next_instruction}", t.thread_id)

    def _on_complete(self):
        self.btn_exec.setEnabled(False)
        self.btn_prom.setEnabled(False)
        unf = [p for p in self.machine.promises if not p.fulfilled]

        self._log("")
        self._log("----- EXECUTION COMPLETE -----")
        if unf:
            self._log("⚠ Unfulfilled promises — INVALID execution")
            for p in unf:
                self._log(f"  {p}")
        self._log("")
        self._log("Final register values:")
        for t in self.machine.threads:
            for r, v in sorted(t.registers.items()):
                self._log(f"  Thread {t.thread_id}: {r} = {v}")
        self.statusBar().showMessage("Execution complete!")

    def _log(self, text):
        self.log_display.append(text)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum())



#MAIN

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    fp = sys.argv[1] if len(sys.argv) > 1 else None
    win = MainWindow(fp)
    win.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
