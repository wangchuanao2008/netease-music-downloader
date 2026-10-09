import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QHBoxLayout, QLabel,
                               QMainWindow, QPlainTextEdit, QProgressBar,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .links import extract_urls
from .worker import DownloadManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("网易云音乐下载器")
        self.resize(1050, 680)
        self.settings = QSettings("MusicDown", "MusicDown")
        self.manager = DownloadManager()
        self.next_id = 1
        self.tasks = {}
        self.rows = {}
        self._setup()
        self.manager.events.info.connect(self._on_info)
        self.manager.events.progress.connect(self._on_progress)
        self.manager.events.state.connect(self._on_state)
        self.manager.events.complete.connect(self._on_complete)
        QTimer.singleShot(0, self._choose_first_directory)

    def _setup(self):
        root = QWidget(); self.setCentralWidget(root)
        layout = QVBoxLayout(root); layout.setContentsMargins(22, 20, 22, 18); layout.setSpacing(12)
        title = QLabel("网易云音乐下载器"); title.setObjectName("title"); layout.addWidget(title)
        subtitle = QLabel("粘贴网易云音乐单曲链接。支持分享文字与一次粘贴多条链接。")
        subtitle.setObjectName("subtitle"); layout.addWidget(subtitle)
        folder_row = QHBoxLayout(); layout.addLayout(folder_row)
        folder_row.addWidget(QLabel("保存到"))
        self.folder_label = QLabel(self.settings.value("folder", "首次使用请选择目录")); self.folder_label.setObjectName("folder")
        folder_row.addWidget(self.folder_label, 1)
        choose = QPushButton("选择目录"); choose.clicked.connect(self._choose_directory); folder_row.addWidget(choose)
        self.input = QPlainTextEdit(); self.input.setPlaceholderText("把分享链接或整段分享文字粘贴到这里，自动加入队列…")
        self.input.setFixedHeight(95); layout.addWidget(self.input)
        self.paste_timer = QTimer(self); self.paste_timer.setSingleShot(True)
        self.paste_timer.timeout.connect(self._enqueue_input)
        self.input.textChanged.connect(lambda: self.paste_timer.start(650))
        options = QHBoxLayout(); layout.addLayout(options)
        self.mp3 = QCheckBox("转换为 MP3（需要 ffmpeg）")
        self.mp3.setChecked(self.settings.value("mp3", False, bool)); self.mp3.toggled.connect(lambda v: self.settings.setValue("mp3", v))
        options.addWidget(self.mp3)
        self.alternate = QCheckBox("原音源不可用时尝试备用来源")
        self.alternate.setChecked(self.settings.value("alternate", True, bool))
        self.alternate.toggled.connect(lambda v: self.settings.setValue("alternate", v))
        self.alternate.setToolTip("原音源不可用时，通过 GD Studio 第三方接口按网易云歌曲 ID 查询。")
        options.addWidget(self.alternate)
        options.addStretch(1)
        self.notice = QLabel("默认保留公开音源的原格式与实际音质")
        options.addWidget(self.notice)
        self.table = QTableWidget(0, 7); self.table.setHorizontalHeaderLabels(["封面", "歌曲", "歌手", "平台", "实际音质", "进度", "状态"])
        self.table.verticalHeader().setVisible(False); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(0, 58); self.table.setColumnWidth(1, 235); self.table.setColumnWidth(2, 155)
        self.table.setColumnWidth(3, 95); self.table.setColumnWidth(4, 150); self.table.setColumnWidth(5, 110)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(lambda *_: self._reveal())
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout(); layout.addLayout(actions)
        for caption, handler in (("取消所选", self._cancel), ("重试所选", self._retry), ("在资源管理器中显示", self._reveal)):
            button = QPushButton(caption); button.clicked.connect(handler); actions.addWidget(button)
        actions.addStretch(1)
        hint = QLabel("只保存时长完整、可解析的音频；备用来源会在下载列表中标注。")
        hint.setObjectName("hint"); layout.addWidget(hint)
        self.setStyleSheet("""
            QWidget { font-size: 13px; } #title { font-size: 26px; font-weight: 700; }
            #subtitle, #hint { color: #6c7180; } #folder { color: #366da6; }
            QPlainTextEdit { border: 1px solid #cfd5de; border-radius: 8px; padding: 10px; }
            QPushButton { padding: 7px 12px; border-radius: 6px; background: #e9edf3; }
            QPushButton:hover { background: #dce6f2; }
            QTableWidget { border: 1px solid #d7dce4; border-radius: 6px; }
        """)

    def _choose_first_directory(self):
        folder = self.settings.value("folder", "")
        if not folder or not Path(folder).is_dir():
            self._choose_directory()

    def _choose_directory(self):
        default_folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
        folder = QFileDialog.getExistingDirectory(self, "选择音乐保存目录", self.settings.value("folder", default_folder))
        if folder:
            self.settings.setValue("folder", folder); self.folder_label.setText(folder)
            self._enqueue_input()

    def _enqueue_input(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        folder = self.settings.value("folder", "")
        if not folder or not Path(folder).is_dir():
            self.notice.setText("请先选择有效的保存目录")
            return
        urls = extract_urls(text)
        if not urls:
            self.notice.setText("没有找到 http(s) 歌曲链接")
            return
        self.input.blockSignals(True); self.input.clear(); self.input.blockSignals(False)
        for url in urls:
            self._add_task(url, folder, self.mp3.isChecked(), self.alternate.isChecked())
        self.notice.setText(f"已加入 {len(urls)} 条链接")

    def _add_task(self, url: str, folder: str, mp3: bool, alternate: bool = True):
        task_id = self.next_id; self.next_id += 1
        row = self.table.rowCount(); self.table.insertRow(row); self.table.setRowHeight(row, 58)
        self.rows[task_id] = row
        self.tasks[task_id] = {"url": url, "folder": folder, "mp3": mp3,
                               "alternate": alternate, "status": "排队中", "path": ""}
        for col, value in ((1, url), (2, "—"), (3, "—"), (4, "—"), (6, "排队中")):
            self.table.setItem(row, col, QTableWidgetItem(value))
        cover = QLabel("♪"); cover.setAlignment(Qt.AlignmentFlag.AlignCenter); self.table.setCellWidget(row, 0, cover)
        progress = QProgressBar(); progress.setRange(0, 100); progress.setValue(0)
        self.table.setCellWidget(row, 5, progress)
        self.manager.add(task_id, url, folder, mp3, alternate)

    def _on_info(self, task_id, song, cover):
        row = self.rows[task_id]
        self.table.item(row, 1).setText(song.title)
        self.table.item(row, 1).setToolTip(f"{song.album}\n{self.tasks[task_id]['url']}")
        self.table.item(row, 2).setText(song.artist)
        self.table.item(row, 3).setText("网易云")
        if cover:
            pixmap = QPixmap(); pixmap.loadFromData(cover)
            label = self.table.cellWidget(row, 0)
            label.setPixmap(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _on_progress(self, task_id, percent):
        bar = self.table.cellWidget(self.rows[task_id], 5)
        if percent < 0:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100); bar.setValue(min(100, percent))

    def _on_state(self, task_id, state):
        self.tasks[task_id]["status"] = state
        self.table.item(self.rows[task_id], 6).setText(state)

    def _on_complete(self, task_id, state, detail, audio):
        self.tasks[task_id]["status"] = state
        row = self.rows[task_id]
        item = self.table.item(row, 6)
        source = audio.get("source", "") if audio else ""
        if state in ("已完成", "已存在"):
            item.setText(state + ("（备用来源）" if "GD Studio" in source else ""))
        else:
            item.setText(f"{state}：{detail}")
        item.setToolTip(detail)
        if audio:
            self.tasks[task_id]["path"] = detail
            bitrate = f"{audio['bitrate_kbps']} kbps" if audio["bitrate_kbps"] else "未知码率"
            quality = f"{audio['codec']} · {bitrate}" + (" · 无损" if audio["lossless"] else "")
            self.table.item(row, 4).setText(quality)
            self.table.item(row, 4).setToolTip(f"实际音频：{quality}\n来源：{source or '原平台公开音源'}")
            item.setToolTip(f"{detail}\n来源：{source or '原平台公开音源'}")
            self.table.cellWidget(row, 5).setRange(0, 100); self.table.cellWidget(row, 5).setValue(100)
        else:
            self.table.cellWidget(row, 5).setRange(0, 100)
            self.table.cellWidget(row, 5).setValue(0)

    def _selected_id(self):
        row = self.table.currentRow()
        return next((task_id for task_id, value in self.rows.items() if value == row), None)

    def _cancel(self):
        task_id = self._selected_id()
        if task_id and self.tasks[task_id]["status"] not in ("已完成", "已存在", "失败", "已取消"):
            self.manager.cancel(task_id); self._on_state(task_id, "取消中")

    def _retry(self):
        task_id = self._selected_id()
        if task_id and self.tasks[task_id]["status"] in ("失败", "已取消"):
            task = self.tasks[task_id]
            self._add_task(task["url"], task["folder"], task["mp3"], task["alternate"])

    def _reveal(self):
        task_id = self._selected_id()
        if task_id and self.tasks[task_id]["path"]:
            import os
            import subprocess
            path = Path(self.tasks[task_id]["path"]).resolve()
            try:
                subprocess.Popen(["explorer.exe", "/select,", str(path)])
            except OSError:
                os.startfile(str(path.parent))


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("MusicDown"); app.setApplicationName("MusicDown")
    window = MainWindow(); window.show()
    sys.exit(app.exec())
