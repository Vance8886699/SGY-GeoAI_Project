# YuGeoTech_Project/ui/views/borehole_main_view.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QMessageBox
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt
from datetime import datetime

class BoreholeMainView(QWidget):
    def __init__(self, pzgn, db_manager, config_loader, field_mapper, project_handler, parent=None):
        super().__init__(parent)
        self.pzgn = pzgn  # 表的配置名，例如 "z_ZuanKong"
        self.db_manager = db_manager
        self.config_loader = config_loader
        self.field_mapper = field_mapper
        self.project_handler = project_handler

        self.layout = QVBoxLayout(self)
        self.table_view = QTableView()
        self.layout.addWidget(self.table_view)

        self.model = QStandardItemModel(self)
        self.table_view.setModel(self.model)
        self.table_view.setSortingEnabled(True)  # 允许排序
        # self.table_view.setEditTriggers(QAbstractItemView.DoubleClicked) # 允许双击编辑

        self.load_data()

    def load_data(self):
        self.model.clear()

        current_gcsy = self.project_handler.get_current_project_gcsy()
        if current_gcsy is None: # GCSY 可能是0，所以要判断 is None
            # QMessageBox.information(self, "提示", "没有活动的工程GCSY，无法加载数据。")
            print(f"视图 {self.pzgn}: 当前工程 GCSY 为 None，不加载数据。")
            return

        table_config = self.config_loader.get_table_config(self.pzgn)
        if not table_config:
            QMessageBox.warning(self, "配置错误", f"未找到表 '{self.pzgn}' 的界面配置 (g_PeiZhi)。")
            return

        db_fields_to_display = table_config.get("PZYM", [])
        if not db_fields_to_display:
            QMessageBox.warning(self, "配置错误", f"表 '{self.pzgn}' 的显示字段列表 (PZYM) 为空。")
            return

        ui_headers = [self.field_mapper.get_ui_name(db_field) for db_field in db_fields_to_display]
        self.model.setHorizontalHeaderLabels(ui_headers)

        fields_for_select = ", ".join([f"[{field}]" for field in db_fields_to_display])
        table_actual_name = self.pzgn # PZGN 通常就是实际表名

        # 对于 z_ZuanKong (勘探点主表)，它需要根据 GCSY 筛选
        # 确保 GCSY 在数据库中是数字类型，而 self.project_handler.get_current_project_gcsy() 返回的也是数字
        query = f"SELECT {fields_for_select} FROM [{table_actual_name}] WHERE [GCSY] = ?"
        params = (current_gcsy,) # current_gcsy 应该是数字

        print(f"执行查询 ({self.pzgn}): {query} with params {params} (GCSY type: {type(current_gcsy)})")
        data_rows = self.db_manager.execute_query(query, params=params, db_type="project")

        if data_rows is None:
            QMessageBox.critical(self, "数据加载错误", f"无法从表 '{table_actual_name}' 加载数据。请检查控制台输出。")
            return

        if not data_rows:
            print(f"表 '{table_actual_name}' 中没有与GCSY '{current_gcsy}' 相关的数据，或表为空。")
            # self.table_view.setRowCount(0) # 如果用 QTableWidget
            pass

        for row_idx, row_data in enumerate(data_rows):
            items = []
            if len(row_data) != len(db_fields_to_display):
                print(
                    f"警告: 第 {row_idx + 1} 行数据列数 ({len(row_data)}) 与期望列数 ({len(db_fields_to_display)}) 不匹配。跳过此行。")
                continue  # 跳过不匹配的行
            for col_idx, value in enumerate(row_data):
                db_field_name = db_fields_to_display[col_idx]
                field_def = self.config_loader.get_ziduan_definition(db_field_name)
                zd_type = field_def.get("ZDTYPE", "0") if field_def else "0"  # 假设0是文本

                item_text = ""
                if value is None:
                    item_text = ""
                # 根据字段类型进行格式化 (g_ZiDuan.ZDTYPE 的含义需要明确)
                # 假设 '1', '2', '3' 等代表数字类型，'4' 代表日期，'5' 代表布尔
                # 这个 ZDTYPE -> Python类型的映射需要您根据 g_ZiDuan 的实际定义来完善
                elif zd_type in ['1', '2', '3', 'N', 'F']:  # 假设这些代表数字
                    try:
                        # TODO: 应用 g_XiaoShuDian 中的小数位数配置
                        item_text = str(float(value)) if '.' in str(value) else str(int(value))
                    except ValueError:
                        item_text = str(value)  # 转换失败则用原字符串
                elif zd_type == 'D':  # 假设 'D' 代表日期
                    # Pyodbc 返回的日期时间类型可能是 datetime.datetime 对象
                    if isinstance(value, datetime):
                        item_text = value.strftime('%Y-%m-%d')  # 或 '%Y-%m-%d %H:%M:%S'
                    else:
                        item_text = str(value)
                elif zd_type == 'L':  # 假设 'L' 代表布尔/逻辑型
                    item_text = "是" if value else "否"  # 或者 "True"/"False", "1"/"0"
                else:  # 默认按文本处理
                    item_text = str(value).strip() if value else ""

                item = QStandardItem(item_text)
                items.append(item)
            self.model.appendRow(items)

        self.table_view.resizeColumnsToContents()
        print(f"为 {self.pzgn} 加载了 {self.model.rowCount()} 行数据。")