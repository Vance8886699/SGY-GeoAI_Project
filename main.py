# YuGeoTech_Project/main.py
import sys
import os
from PySide6.QtWidgets import QApplication
import datetime
# 将项目根目录添加到 sys.path，以便正确导入模块
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.dirname(current_dir) # 如果 main.py 在项目根目录，这行不需要
# sys.path.insert(0, project_root)


from core.db_manager import DBManager
from core.config_loader import ConfigLoader
from core.field_mapper import FieldMapper
from core.project_handler import ProjectHandler
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # 检查 system_config.mdb 是否存在
    sys_config_path = os.path.join(os.path.dirname(__file__), 'system_config_ref', 'system_config.mdb')
    if not os.path.exists(sys_config_path):
        from PySide6.QtWidgets import QMessageBox  # 局部导入
        QMessageBox.critical(None, "严重错误",
                             f"系统配置文件 'system_config.mdb' 未找到！\n路径: {sys_config_path}\n程序无法启动。")
        return -1  # 或者 sys.exit(-1)

    # 1. 初始化核心组件
    db_manager = DBManager()
    if not db_manager.config_conn:  # 检查 system_config.mdb 是否成功连接
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "数据库连接错误",
                             "无法连接到 system_config.mdb。\n请检查配置文件路径和Access驱动。\n程序无法启动。")
        return -1

    # 调试打印：确认 ConfigLoader 实例化位置
    print(">>> 即将实例化 ConfigLoader (main.py)")
    config_loader = ConfigLoader(db_manager)
    print("<<< ConfigLoader 实例化完成 (main.py)")

    field_mapper = FieldMapper(config_loader)

    # 定义工程工作区路径
    workspace_directory = os.path.join(os.path.dirname(__file__), 'workspace')
    project_handler = ProjectHandler(db_manager, workspace_directory)

    # 2. 创建主窗口
    main_win = MainWindow(db_manager, config_loader, field_mapper, project_handler)
    main_win.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()