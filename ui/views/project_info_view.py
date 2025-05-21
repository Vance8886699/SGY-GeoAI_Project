# YuGeoTech_Project/ui/views/project_info_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                               QPushButton, QMessageBox, QLabel, QComboBox, QCheckBox,
                               QScrollArea)  # 添加 QScrollArea
from PySide6.QtCore import Qt


class ProjectInfoView(QWidget):
    def __init__(self, pzgn, db_manager, config_loader, field_mapper, project_handler, parent=None):
        super().__init__(parent)
        self.pzgn = pzgn  # 应该是 "x_GongCheng"
        self.db_manager = db_manager
        self.config_loader = config_loader
        self.field_mapper = field_mapper
        self.project_handler = project_handler

        self.current_gcsy = self.project_handler.get_current_project_gcsy()
        if self.current_gcsy is None:
            main_layout_error = QVBoxLayout(self)
            main_layout_error.addWidget(QLabel("错误：没有活动的工程 (GCSY 为空)，无法加载工程信息。"))
            return

        self.fields_config = self.config_loader.get_table_config(self.pzgn)
        if not self.fields_config or not self.fields_config.get("PZYM"):
            main_layout_error = QVBoxLayout(self)
            main_layout_error.addWidget(QLabel(f"错误：PZGN '{self.pzgn}' 的表单字段配置 (PZYM) 未找到。"))
            return

        self.db_field_names_ordered = self.fields_config.get("PZYM", [])
        self.input_widgets = {}  # 存储 ZDMC -> QLineEdit/QComboBox等
        self.primary_keys_zdmc = self.fields_config.get("GJZ", [])  # 主键

        # 使用 QScrollArea 以便内容过多时可以滚动
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)

        container_widget = QWidget()  # 容器控件，放置表单布局
        self.form_layout = QFormLayout(container_widget)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)  # 让字段扩展
        self.form_layout.setLabelAlignment(Qt.AlignRight)  # 标签右对齐

        # 根据 PZYM 动态创建表单项
        for zdmc in self.db_field_names_ordered:
            field_def = self.config_loader.get_ziduan_definition(zdmc)
            if not field_def or field_def.get("ZDSHOW", '1') == '0':
                continue

            ui_name = self.field_mapper.get_ui_name(zdmc)

            # TODO: 根据字段的 XMDH (如果存在于 g_DuiZhao) 创建 QComboBox，
            # 或者根据 ZDTYPE 创建不同类型的编辑器 (如 QDateEdit, QCheckBox)
            # 目前简化为 QLineEdit
            widget = QLineEdit()
            # GCSY 字段通常是只读的
            if zdmc.upper() == 'GCSY':
                widget.setReadOnly(True)

            self.form_layout.addRow(f"{ui_name}:", widget)
            self.input_widgets[zdmc] = widget

        self.save_button = QPushButton("保存工程信息")
        self.save_button.clicked.connect(self.save_project_info)
        self.form_layout.addRow(self.save_button)

        scroll_area.setWidget(container_widget)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll_area)

        self.load_project_info()

    def load_project_info(self):
        if self.current_gcsy is None: return

        # x_GongCheng 表按 GCSY 应该只有一条记录
        # 我们只获取PZYM中定义的字段
        fields_to_select = ", ".join([f"[{zdmc}]" for zdmc in self.db_field_names_ordered])
        query = f"SELECT {fields_to_select} FROM [{self.pzgn}] WHERE [GCSY] = ?"
        params = (self.current_gcsy,)

        print(f"ProjectInfoView: 加载数据查询: {query} 参数: {params}")
        data = self.db_manager.execute_query(query, params=params, db_type="project")

        if data and len(data) == 1:
            row_data = data[0]
            for i, zdmc in enumerate(self.db_field_names_ordered):
                if zdmc in self.input_widgets:
                    value = row_data[i]
                    # 格式化显示 (简单版本)
                    display_text = ""
                    if value is not None:
                        if isinstance(value, bool):
                            display_text = "是" if value else "否"  # 或根据配置
                        else:
                            display_text = str(value)
                    self.input_widgets[zdmc].setText(display_text)
            print(f"ProjectInfoView: 工程信息已加载 (GCSY: {self.current_gcsy})。")
        elif data and len(data) > 1:
            print(f"警告 (ProjectInfoView): x_GongCheng 表中 GCSY={self.current_gcsy} 找到多于一条记录！")
        else:
            print(f"ProjectInfoView: 未找到 GCSY={self.current_gcsy} 的工程信息。")
            # 清空表单或显示提示
            for widget in self.input_widgets.values():
                widget.clear()
            if 'GCSY' in self.input_widgets and self.current_gcsy is not None:  # 如果GCSY字段存在，则填充它
                self.input_widgets['GCSY'].setText(str(self.current_gcsy))

    def save_project_info(self):
        if self.current_gcsy is None:
            QMessageBox.warning(self, "错误", "没有活动的工程，无法保存。")
            return

        if not self.primary_keys_zdmc or 'GCSY' not in self.primary_keys_zdmc:
            QMessageBox.critical(self, "配置错误", "x_GongCheng表的主键未正确配置为GCSY，无法保存。")
            return

        set_clauses = []
        param_values = []

        for zdmc, widget in self.input_widgets.items():
            if zdmc.upper() == 'GCSY':  # GCSY 通常不应通过表单修改
                continue

            field_def = self.config_loader.get_ziduan_definition(zdmc)
            if not field_def: continue

            zd_type = field_def.get("ZDTYPE", "0")
            display_text = widget.text()

            # 从显示文本解析为数据库存储类型
            actual_value = None
            try:
                if display_text.strip() == "":
                    actual_value = None  # 空字符串视为 NULL
                elif zd_type in ['1', '2', '3', 'N', 'F', 'I', 'S', 'L', 'INT', 'INTEGER', 'NUMBER', 'FLOAT', 'DOUBLE',
                                 'REAL', 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:  # 数字类型
                    actual_value = float(display_text)  # 或 int()
                elif zd_type == 'D':  # 日期
                    actual_value = datetime.strptime(display_text, '%Y-%m-%d').date()
                elif zd_type == 'L':  # 布尔
                    actual_value = True if display_text.lower() in ['是', 'true', '1'] else False
                else:  # 文本
                    actual_value = display_text
            except ValueError as e:
                QMessageBox.warning(self, "输入错误",
                                    f"字段 '{self.field_mapper.get_ui_name(zdmc)}' 的值 '{display_text}' 格式不正确: {e}")
                return

            set_clauses.append(f"[{zdmc}] = ?")
            param_values.append(actual_value)

        if not set_clauses:
            QMessageBox.information(self, "提示", "没有需要更新的字段。")
            return

        # WHERE 条件是 GCSY
        where_clause = "[GCSY] = ?"
        param_values.append(self.current_gcsy)

        update_query = f"UPDATE [{self.pzgn}] SET {', '.join(set_clauses)} WHERE {where_clause}"

        print(f"ProjectInfoView: 尝试更新: {update_query} 参数: {tuple(param_values)}")
        if self.db_manager.execute_query(update_query, params=tuple(param_values), db_type="project"):
            QMessageBox.information(self, "成功", "工程信息已保存。")
            self.load_project_info()  # 重新加载以确认
        else:
            QMessageBox.critical(self, "保存失败", "保存工程信息失败，请检查控制台输出。")