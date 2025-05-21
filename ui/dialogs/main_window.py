# gui/main_window.py
import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
                               QFileDialog, QInputDialog, QMessageBox)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QKeySequence
from datetime import datetime  # <--- 确保导入

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# DBManager 和 ConfigLoader 现在由 ProjectHandler 内部管理其生命周期
from core.project_handler import ProjectHandler
from core.config_loader import ConfigLoader  # MainWindow仍需ConfigLoader类型提示
from core.db_manager import DBManager  # MainWindow仍需DBManager类型提示


class MainWindow(QMainWindow):
    def __init__(self, project_handler: ProjectHandler, global_config_loader: ConfigLoader):
        super().__init__()
        self.project_handler = project_handler
        self.global_config_loader = global_config_loader  # 全局配置加载器实例

        # 工程打开后，这些会指向 project_handler 内部的实例
        self.db_manager_project: Optional[DBManager] = None
        # 注意：config_loader 现在应该是基于当前工程MDB的，或者我们继续用全局的然后按工程GCBZ筛选
        # 为简单起见，我们先假设 project_handler 打开工程后，会有一个 config_loader 实例是针对该工程MDB的
        # 但更合理的做法是，全局 ConfigLoader 加载系统配置，工程特定配置按需读取或合并
        self.config_loader_project: Optional[ConfigLoader] = None

        self.setWindowTitle("岩土工程勘察软件 (PySide6-MDB版)")
        self.setGeometry(100, 100, 1200, 800)

        self._create_menus()
        self._create_status_bar()
        self._setup_central_widget()
        self.update_ui_on_project_change()

    # _create_menus, _create_status_bar, _setup_central_widget 方法与之前MDB版本相同
    # ... (粘贴上一版MDB的MainWindow中的这些方法代码) ...
    def _create_menus(self):
        menu_bar = self.menuBar()
        project_menu = menu_bar.addMenu("工程管理(&M)")

        new_action = QAction("新建工程(&N)...", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.on_new_project)
        project_menu.addAction(new_action)

        open_action = QAction("打开工程(&O)...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.on_open_project)
        project_menu.addAction(open_action)

        self.close_project_action = QAction("关闭工程(&C)", self)
        self.close_project_action.setEnabled(False)
        self.close_project_action.triggered.connect(self.on_close_project)
        project_menu.addAction(self.close_project_action)

        project_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        project_menu.addAction(exit_action)

    def _create_status_bar(self):
        self.statusBar().showMessage("准备就绪。请新建或打开工程。")

    def _setup_central_widget(self):
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        self.project_status_label = QLabel("当前未打开工程。")
        self.project_status_label.setAlignment(Qt.AlignCenter)
        font = self.project_status_label.font()
        font.setPointSize(16)
        self.project_status_label.setFont(font)
        layout.addWidget(self.project_status_label)
        self.setCentralWidget(central_widget)

    def update_ui_on_project_change(self):
        base_title = "岩土工程勘察软件 (PySide6-MDB版)"
        current_project_info = self.project_handler.get_current_project_info()

        if current_project_info and self.project_handler.current_project_mdb_path:
            project_name = current_project_info.get("GCMC", "未知工程")
            mdb_filename = os.path.basename(self.project_handler.current_project_mdb_path)
            self.setWindowTitle(f"{project_name} ({mdb_filename}) - {base_title}")
            self.project_status_label.setText(
                f"当前工程: {project_name} (GCSY: {self.project_handler.get_current_gcsy()})\n"
                f"数据库: {mdb_filename}"
            )
            self.statusBar().showMessage(f"已打开工程: {project_name}")
            self.close_project_action.setEnabled(True)

            # 工程打开后，project_handler 内部会有一个连接到该工程MDB的db_manager
            # 并且会有一个针对该工程MDB的config_loader (如果每个MDB自包含配置)
            self.db_manager_project = self.project_handler.db_manager_project  # 从handler获取当前工程的DBManager
            self.config_loader_project = self.project_handler.config_loader  # 从handler获取当前工程的ConfigLoader

            if self.config_loader_project:
                print("主窗口：当前工程的ConfigLoader 已成功关联。")
                # 使用这个针对工程MDB的ConfigLoader来获取工程特定的GCBZ
                current_proj_gcbz_from_opened_mdb = self.config_loader_project.get_current_project_gcbz()
                print(
                    f"主窗口中获取的当前打开工程的规范代码 (来自工程MDB的x_GongCheng): {current_proj_gcbz_from_opened_mdb if current_proj_gcbz_from_opened_mdb else '未定义'}")
                # 现在可以用 project_specific_gcbz 和 self.global_config_loader 来获取和显示配置了
                # 例如: self.global_config_loader.get_zi_duan_info_for_project("ZKBH", project_specific_gcbz)
            else:
                print("主窗口：ConfigLoader 未能从ProjectHandler获取 (可能工程MDB配置不全或打开失败)。")
        else:
            self.setWindowTitle(base_title)
            self.project_status_label.setText("当前未打开工程。\n请通过“工程管理”菜单新建或打开一个工程MDB文件。")
            self.statusBar().showMessage("准备就绪。请新建或打开工程。")
            self.close_project_action.setEnabled(False)
            self.db_manager_project = None
            self.config_loader_project = None

    @Slot()
    def on_new_project(self):
        default_mdb_filename = f"新勘察工程_{datetime.now().strftime('%Y%m%d%H%M%S')}.mdb"
        default_save_path = os.path.join(self.project_handler.base_project_dir, default_mdb_filename)

        new_mdb_full_path, _ = QFileDialog.getSaveFileName(
            self, "保存新工程数据库文件", default_save_path, "Access数据库文件 (*.mdb)"
        )
        if not new_mdb_full_path:
            self.statusBar().showMessage("新建工程操作已取消。")
            return

        if not new_mdb_full_path.lower().endswith(".mdb"): new_mdb_full_path += ".mdb"

        project_name, ok1 = QInputDialog.getText(self, "新建工程", "工程名称:",
                                                 text=os.path.splitext(os.path.basename(new_mdb_full_path))[0])
        if not ok1 or not project_name.strip(): self.statusBar().showMessage("工程名称不能为空，新建取消。"); return

        project_code, ok2 = QInputDialog.getText(self, "新建工程", "工程编号:",
                                                 text=f"NEW-{datetime.now().strftime('%H%M')}")
        if not ok2 or not project_code.strip(): self.statusBar().showMessage("工程编号不能为空，新建取消。"); return

        project_location, _ = QInputDialog.getText(self, "新建工程", "工程地点:")

        # 从全局配置加载器获取系统默认规范 (CFGCurZXBZ)
        standard_gcbz = self.global_config_loader.get_current_system_standard_gcbz()

        # 可以进一步让用户从 x_BiaoZhun 选择规范
        available_standards_data = self.global_config_loader.get_config_table("x_BiaoZhun")
        if available_standards_data:
            items = [f"{s.get('BZMC')} (代码: {s.get('GCBZ')})" for s in available_standards_data]
            item, ok_std = QInputDialog.getItem(self, "选择工程规范", "请选择工程遵循的规范:", items, 0, False)
            if ok_std and item:
                # 解析选择的规范代码，例如从 "工民建标准 (代码: 0)" 中提取 "0"
                try:
                    standard_gcbz = item.split("代码:")[1].split(")")[0].strip()
                except IndexError:
                    print(f"解析规范代码失败: {item}, 使用默认 {standard_gcbz}")

        gcsy, created_mdb_path = self.project_handler.create_new_project_from_schema_template(
            project_mdb_full_path=new_mdb_full_path,
            project_name=project_name, project_code=project_code,
            project_location=project_location, standard_gcbz=standard_gcbz
        )

        if gcsy and created_mdb_path:
            QMessageBox.information(self, "成功", f"工程 '{project_name}' 已创建并打开！")
            self.update_ui_on_project_change()
        else:
            QMessageBox.warning(self, "失败", f"创建工程 '{project_name}' 失败。")

    # on_open_project, on_close_project, closeEvent 方法与上一版MDB相同
    # ...
    @Slot()
    def on_open_project(self):
        mdb_path, _ = QFileDialog.getOpenFileName(
            self, "打开工程数据库文件", self.project_handler.base_project_dir,
            "Access数据库文件 (*.mdb);;所有文件 (*)"
        )
        if not mdb_path:
            self.statusBar().showMessage("打开工程操作已取消。")
            return

        if self.project_handler.open_project_mdb(mdb_path):
            self.update_ui_on_project_change()
        else:
            QMessageBox.warning(self, "失败", f"打开工程文件失败: {os.path.basename(mdb_path)}")

    @Slot()
    def on_close_project(self):
        if not self.project_handler.current_project_mdb_path:
            self.statusBar().showMessage("当前没有打开的工程。")
            return
        self.project_handler.close_current_project()
        self.update_ui_on_project_change()
        QMessageBox.information(self, "操作完成", "当前工程已关闭。")

    def closeEvent(self, event):
        if self.project_handler.current_project_mdb_path:
            self.project_handler.close_current_project()
        # 全局ConfigLoader的DBManager应该在main.py退出时关闭
        print("应用程序主窗口关闭。")
        event.accept()

# --- main.py (MDB版本 - 调整ConfigLoader的初始化) ---