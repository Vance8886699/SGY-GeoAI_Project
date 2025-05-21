# YuGeoTech_Project/ui/widgets/generic_table_view.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QMessageBox, QAbstractItemView, QMenu
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QKeySequence
from PySide6.QtCore import Qt
from datetime import datetime
from PySide6.QtCore import Qt, QModelIndex,Signal # 添加 Signal

# import pandas as pd # 用于Excel导入导出
# import openpyxl # 用于Excel导入导出 (如果需要处理 .xlsx)



class GenericTableView(QWidget):
    boreholeSelectedSignal = Signal(str)
    sampleSelectedSignal = Signal(str)

    def __init__(self, pzgn, db_manager, config_loader, field_mapper, project_handler,
                 parent_gcsy=None,
                 parent_zkbh=None,
                 parent_qybh=None,
                 parent=None):
        super().__init__(parent)
        self.pzgn = pzgn
        self.db_manager = db_manager
        self.config_loader = config_loader
        self.field_mapper = field_mapper
        self.project_handler = project_handler

        self.parent_gcsy = parent_gcsy if parent_gcsy is not None else self.project_handler.get_current_project_gcsy()
        self.parent_zkbh = parent_zkbh
        self.parent_qybh = parent_qybh

        self.table_config = self.config_loader.get_table_config(self.pzgn)
        if not self.table_config:
            self.layout = QVBoxLayout(self)
            error_label = QLabel(f"错误：PZGN '{self.pzgn}' 的表配置未在g_PeiZhi中找到。视图无法初始化。")
            self.layout.addWidget(error_label)
            print(f"错误：PZGN '{self.pzgn}' 的表配置未在g_PeiZhi中找到。")
            return

        self.primary_keys_zdmc = self.table_config.get("GJZ", [])  # 主键字段名列表 (ZDMC)
        self.db_fields_displayed_zdmc = self.table_config.get("PZYM", [])  # PZYM 定义了要显示的列及其顺序

        # 确保所有主键字段都在PZYM中，或者有一种方式获取它们的值
        # 为了简化，我们假设如果GJZ存在，PZYM中至少应包含它们才能进行编辑和删除
        for pk in self.primary_keys_zdmc:
            if pk not in self.db_fields_displayed_zdmc:
                print(f"警告 ({self.pzgn}): 主键 '{pk}' 未在显示字段PZYM中配置，编辑和删除功能可能受限。")
                # 考虑是否要将主键强制添加到查询和模型中，但不在表格中显示
                # self.db_fields_displayed_zdmc.append(pk) # 风险：改变了显示列

        self.layout = QVBoxLayout(self)
        self.table_view = QTableView()
        self.layout.addWidget(self.table_view)

        self.model = QStandardItemModel(self)
        self.table_view.setModel(self.model)

        self.table_view.setSortingEnabled(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)

        # 在load_data之前连接信号，但在clear之后、添加新数据之前阻塞它
        self.model.itemChanged.connect(self.handle_item_changed)
        self.table_view.selectionModel().currentRowChanged.connect(self.on_row_changed)

        self.load_data()

    def determine_db_type_and_filters(self):
        # (此方法与上一轮代码基本一致，此处省略以减少重复，请确保其逻辑正确)
        # 返回: db_type, filter_by_gcsy_flag, zkbh_filter_field_name, qybh_filter_field_name
        db_type = "project"
        filter_by_gcsy = True
        zkbh_filter_field = None
        qybh_filter_field = None

        if self.pzgn.lower() == "x_gongcheng":
            filter_by_gcsy = True
        elif self.pzgn.lower().startswith("g_"):
            db_type = "config"
            filter_by_gcsy = False
            if self.pzgn.lower() == "g_stucenggc":
                db_type = "project"
                filter_by_gcsy = True

        drillhole_related_tables = ["z_g_tuceng", "z_zuankong_zkj", "z_y_biaoguan", "z_y_dongtan", "z_y_jingtan",
                                    "z_y_jingtansq", "z_g_shuiwei", "t_yashuisyjl", "t_yashuisyswjl", "t_yashuisy",
                                    "z_y_choushui", "z_y_choushuisj", "z_y_choushuiswhf", "z_y_zhushui"]
        sample_related_tables = ["z_c_quyang", "z_c_gujie", "z_c_kefen", "z_c_zhijian", "z_c_sanzhou",
                                 "z_c_pengzhangtu", "t_yanshisy", "t_yirongyan", "t_shuizhijianfx"]

        if self.pzgn.lower() in drillhole_related_tables:
            zkbh_filter_field = "ZKBH"

        if self.pzgn.lower() in sample_related_tables:
            if zkbh_filter_field is None: zkbh_filter_field = "ZKBH"
            if self.pzgn.lower() != "z_c_quyang":  # 取样表本身不按QYBH过滤列表
                qybh_filter_field = "QYBH"

        if self.pzgn.lower() == "z_zuankong":
            zkbh_filter_field = None  # 勘探点主表不按ZKBH过滤自身
            qybh_filter_field = None
            # filter_by_gcsy 应该为 True，因为它与工程相关
            filter_by_gcsy = True
            db_type = "project"

        # 确保对 z_g_TuCeng 的处理
        elif self.pzgn.lower() == "z_g_tuceng":
            zkbh_filter_field = "ZKBH"  # 地层表需要按ZKBH过滤
            qybh_filter_field = None
            filter_by_gcsy = True
            db_type = "project"

        # 确保对 z_c_QuYang (取样表) 的处理
        elif self.pzgn.lower() == "z_c_quyang":
            zkbh_filter_field = "ZKBH"  # 取样表需要按ZKBH过滤
            qybh_filter_field = None  # 取样表本身不按QYBH过滤其列表
            filter_by_gcsy = True
            db_type = "project"

        # ... 其他已有的 drillhole_related_tables 和 sample_related_tables 逻辑
        # 例如，如果一个表在 drillhole_related_tables 中，但它不是 z_ZuanKong，则它需要 ZKBH 过滤
        # 如果一个表在 sample_related_tables 中，但它不是 z_c_QuYang，它可能需要 ZKBH 和 QYBH 过滤

        return db_type, filter_by_gcsy, zkbh_filter_field, qybh_filter_field

    def load_data(self):
        self.model.blockSignals(True)
        self.model.clear()

        db_type_to_use, use_gcsy_filter, zk_col_name, qy_col_name = self.determine_db_type_and_filters()

        # ... (检查 parent_gcsy, parent_zkbh, parent_qybh 是否缺失的逻辑，同上) ...
        # ... (获取 PZYM, 设置表头等逻辑不变) ...
        if use_gcsy_filter and self.parent_gcsy is None:  # 确保parent_gcsy已获取
            print(f"视图 {self.pzgn}: GCSY是必需的但未提供。")
            self.model.setHorizontalHeaderLabels(["错误：工程未正确加载 (无GCSY)"])
            self.model.blockSignals(False);
            return
        if zk_col_name and self.parent_zkbh is None:
            self.model.setHorizontalHeaderLabels([f"请先选择钻孔以查看 {self.field_mapper.get_ui_name(self.pzgn)}"])
            self.model.blockSignals(False);
            return
        if qy_col_name and self.parent_qybh is None:
            self.model.setHorizontalHeaderLabels([f"请先选择取样以查看 {self.field_mapper.get_ui_name(self.pzgn)}"])
            self.model.blockSignals(False);
            return

        if not self.db_fields_displayed_zdmc:  # PZYM 为空
            QMessageBox.warning(self, "配置错误", f"表 '{self.pzgn}' 的显示字段列表 (PZYM) 为空。")
            self.model.blockSignals(False);
            return
        ui_headers = [self.field_mapper.get_ui_name(zdmc) for zdmc in self.db_fields_displayed_zdmc]
        self.model.setHorizontalHeaderLabels(ui_headers)

        fields_for_select = ", ".join([f"[{f}]" for f in self.db_fields_displayed_zdmc])
        table_actual_name = self.pzgn

        conditions = []
        params = []

        if use_gcsy_filter and self.parent_gcsy is not None:
            conditions.append(f"[{'GCSY'}] = ?")
            params.append(self.parent_gcsy)
        if zk_col_name and self.parent_zkbh is not None:
            conditions.append(f"[{zk_col_name}] = ?")
            params.append(self.parent_zkbh)
        if qy_col_name and self.parent_qybh is not None:
            conditions.append(f"[{qy_col_name}] = ?")
            params.append(self.parent_qybh)

        query = f"SELECT {fields_for_select} FROM [{table_actual_name}]"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        # 新增：添加排序逻辑 (如果该表在g_PeiZhi中有PZPX配置)
        default_sort_columns_str = self.table_config.get("PZPX", "")  # 如 "TCXH ASC, ZKBH"
        if default_sort_columns_str:
            # 简单处理，假设 PZPX 就是直接可用的 SQL ORDER BY 子句
            # 您可能需要解析它，确保字段名用方括号括起来
            # 例如，如果PZPX是 "TCXH, ZKBH"，转换为 "[TCXH], [ZKBH]"
            # 如果有 ASC/DESC，也需要处理
            sort_parts = []
            for part in default_sort_columns_str.split(','):
                part = part.strip()
                if not part: continue
                col_name_order = part.split()
                col_name = f"[{col_name_order[0]}]"
                if len(col_name_order) > 1:
                    col_name += f" {col_name_order[1].upper()}"  # ASC 或 DESC
                sort_parts.append(col_name)
            if sort_parts:
                query += " ORDER BY " + ", ".join(sort_parts)
        final_params = tuple(params) if params else None
        print(f"执行查询 ({self.pzgn}, db_type={db_type_to_use}): {query} with params {final_params}")
        data_rows = self.db_manager.execute_query(query, params=final_params, db_type=db_type_to_use)

        if data_rows is None:
            QMessageBox.critical(self, "数据加载错误", f"无法从表 '{table_actual_name}' 加载数据。")
            self.model.blockSignals(False);
            return

        for row_data in data_rows:
            items = []
            if len(row_data) != len(self.db_fields_displayed_zdmc):
                print(f"警告({self.pzgn}): 数据行与PZYM列数不符。行数据: {row_data}")
                continue
            for col_idx, db_field_name in enumerate(self.db_fields_displayed_zdmc):
                value = row_data[col_idx]
                field_def = self.config_loader.get_ziduan_definition(db_field_name)
                zd_type = field_def.get("ZDTYPE", "0") if field_def else "0"
                item_text = self.format_value_for_display(value, zd_type)

                q_item = QStandardItem(item_text)
                q_item.setData(value, Qt.UserRole)  # 存储原始值
                q_item.setData(db_field_name, Qt.UserRole + 1)  # 存储ZDMC
                items.append(q_item)
            self.model.appendRow(items)

        self.table_view.resizeColumnsToContents()
        print(f"为 {self.pzgn} (db_type={db_type_to_use}) 加载了 {self.model.rowCount()} 行数据。")
        self.model.blockSignals(False)

    def format_value_for_display(self, value, zd_type):
        """根据字段类型格式化值以供显示"""
        if value is None: return ""
        # ZDTYPE 的含义需要您根据 system_config.mdb -> g_ZiDuan 表来确定
        # 以下是基于常见情况的猜测和示例
        if zd_type in ['1', '2', '3', 'N', 'F', 'I', 'S', 'L', 'INT', 'INTEGER', 'NUMBER', 'FLOAT', 'DOUBLE', 'REAL', 0,
                       1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:  # 假设数字类型
            try:
                num_val = float(value)
                # TODO: 应用 g_XiaoShuDian 配置小数位数
                # xiaoshu_config = self.config_loader.get_xiaoshu_config_for_field(self.pzgn, db_field_name)
                # if xiaoshu_config and 'POINT' in xiaoshu_config:
                #     return f"{num_val:.{xiaoshu_config['POINT']}f}"
                if num_val == int(num_val): return str(int(num_val))
                return str(num_val)  # 或者格式化为特定小数位
            except (ValueError, TypeError):
                return str(value)
        elif zd_type == 'D' or isinstance(value, datetime):  # 日期
            return value.strftime('%Y-%m-%d') if isinstance(value, datetime) else str(value)
        elif zd_type == 'L' or isinstance(value, bool):  # 逻辑/布尔
            return "是" if value else "否"
        return str(value).strip()

    def _build_where_clause_for_row(self, row_index):
        """为指定行构建基于主键的WHERE子句和参数"""
        if not self.primary_keys_zdmc:
            print(f"警告({self.pzgn}): 未配置主键 (GJZ)，无法定位行。")
            return None, None

        where_parts = []
        param_values = []

        for pk_zdmc in self.primary_keys_zdmc:
            try:
                # 从 PZYM 中找到主键列的索引
                col_idx = self.db_fields_displayed_zdmc.index(pk_zdmc)
                item = self.model.item(row_index, col_idx)
                if item is None or item.data(Qt.UserRole) is None:  # 使用存储的原始值
                    print(f"错误({self.pzgn}): 构建WHERE时无法获取主键'{pk_zdmc}'的值 (行: {row_index + 1})。")
                    return None, None

                # 如果主键本身是上下文ID，则使用当前的上下文ID值
                # 这部分逻辑比较复杂，因为主键可能是GCSY, ZKBH, QYBH等
                pk_value_to_use = item.data(Qt.UserRole)
                if pk_zdmc == 'GCSY' and self.parent_gcsy is not None:
                    pk_value_to_use = self.parent_gcsy
                elif pk_zdmc == 'ZKBH' and self.parent_zkbh is not None:  # (或 self.determine_db_type_and_filters 返回的 zkbh_filter_field)
                    # 检查此表的主键是否真的就是ZKBH，并且其值应来自parent_zkbh
                    # 这是一个简化，实际主键可能更复杂
                    pass  # 暂时假设ZKBH主键值来自item.data(Qt.UserRole)
                # 类似地处理 QYBH

                where_parts.append(f"[{pk_zdmc}] = ?")
                param_values.append(pk_value_to_use)

            except ValueError:  # pk_zdmc 不在显示的列中
                print(f"错误({self.pzgn}): 主键字段'{pk_zdmc}'未在显示字段PZYM中，无法定位行。")
                return None, None

        if not where_parts:
            return None, None

        return " AND ".join(where_parts), tuple(param_values)

    def _get_current_row_pk_values(self, row_index):
        """获取指定模型行的所有主键字段的原始值"""
        if not self.primary_keys_zdmc:
            return None

        pk_values = {}
        valid_pks = True
        for pk_zdmc in self.primary_keys_zdmc:
            # 检查主键是否是上下文ID
            if pk_zdmc == 'GCSY' and self.parent_gcsy is not None:
                pk_values[pk_zdmc] = self.parent_gcsy
                continue

            # determine_db_type_and_filters 返回的字段名
            _, _, zk_col_name_in_db, qy_col_name_in_db = self.determine_db_type_and_filters()

            if zk_col_name_in_db and pk_zdmc == zk_col_name_in_db and self.parent_zkbh is not None:
                # 如果主键是当前视图的钻孔上下文的关联字段 (例如地层表的 ZKBH)
                # 并且这个主键与我们传入的 parent_zkbh 的字段名相同
                pk_values[pk_zdmc] = self.parent_zkbh
                continue

            if qy_col_name_in_db and pk_zdmc == qy_col_name_in_db and self.parent_qybh is not None:
                pk_values[pk_zdmc] = self.parent_qybh
                continue

            # 如果不是上下文ID，则从表格行中获取
            try:
                col_idx = self.db_fields_displayed_zdmc.index(pk_zdmc)
                item = self.model.item(row_index, col_idx)
                if item is None or item.data(Qt.UserRole) is None:
                    print(f"错误({self.pzgn}): 获取主键'{pk_zdmc}'时值为None (行: {row_index + 1})。")
                    valid_pks = False;
                    break
                pk_values[pk_zdmc] = item.data(Qt.UserRole)
            except ValueError:
                print(f"错误({self.pzgn}): 主键字段'{pk_zdmc}'未在PZYM中配置，无法获取值。")
                valid_pks = False;
                break

        return pk_values if valid_pks else None

    def _build_where_clause_from_pks(self, pk_values_dict):
        """根据提供的主键值字典构建WHERE子句和参数"""
        if not pk_values_dict:
            return "", []

        where_parts = []
        param_values = []
        for pk_zdmc, pk_val in pk_values_dict.items():
            if pk_val is None:  # 主键值不应为None来定位
                print(f"错误({self.pzgn}): 主键字段'{pk_zdmc}'的值为None，无法用于WHERE子句。")
                return "", []  # 返回无效子句
            where_parts.append(f"[{pk_zdmc}] = ?")
            param_values.append(pk_val)

        if not where_parts:
            return "", []
        return " AND ".join(where_parts), tuple(param_values)

    def handle_item_changed(self, item: QStandardItem):
        db_type_to_use, _, _, _ = self.determine_db_type_and_filters()
        if db_type_to_use != "project":
            # ... (恢复原始值并返回的逻辑) ...
            original_value = item.data(Qt.UserRole)
            field_zdmc = item.data(Qt.UserRole + 1)
            field_def = self.config_loader.get_ziduan_definition(field_zdmc) if field_zdmc else None
            zd_type = field_def.get("ZDTYPE", "0") if field_def else "0"
            item_text = self.format_value_for_display(original_value, zd_type)
            self.model.blockSignals(True)
            item.setText(item_text)
            self.model.blockSignals(False)
            return

        row = item.row()
        column = item.column()
        new_display_value = item.text()

        field_to_update_zdmc = self.db_fields_displayed_zdmc[column]  # 直接从PZYM获取
        field_def = self.config_loader.get_ziduan_definition(field_to_update_zdmc)
        if not field_def: return

        zd_type = field_def.get("ZDTYPE", "0")
        actual_value_to_save = self.parse_value_from_display(new_display_value, zd_type, field_to_update_zdmc)

        original_value = item.data(Qt.UserRole)
        if actual_value_to_save is None and new_display_value.strip() != "":
            # 解析失败，恢复
            original_display_text = self.format_value_for_display(original_value, zd_type)
            self.model.blockSignals(True);
            item.setText(original_display_text);
            self.model.blockSignals(False)
            return

        # 如果解析后的值与原始值相同（对于某些类型，需要考虑浮点数精度等）
        # 为简单起见，如果字符串表示相同，或者解析值和原始值都为None，则认为未改变
        if str(actual_value_to_save) == str(original_value) or (
                actual_value_to_save is None and original_value is None):
            # 如果值未改变，但显示文本可能因格式化而不同，则恢复标准格式的显示文本
            # 但如果用户输入了无效内容导致解析为None，则上面已经恢复了，这里是针对有效输入但值不变
            if item.text() != self.format_value_for_display(actual_value_to_save, zd_type):
                self.model.blockSignals(True)
                item.setText(self.format_value_for_display(actual_value_to_save, zd_type))
                self.model.blockSignals(False)
            return  # 值未实际改变，不更新数据库

        pk_values_for_row = self._get_current_row_pk_values(row)
        if not pk_values_for_row:
            QMessageBox.critical(self, "更新错误", "无法获取行的主键信息，无法更新。")
            self.load_data();
            return

        where_clause, where_params = self._build_where_clause_from_pks(pk_values_for_row)
        if not where_clause:
            QMessageBox.critical(self, "更新错误", "无法构建定位行的WHERE子句。")
            self.load_data();
            return

        # 不能更新主键列本身 (通常数据库不允许，或逻辑上不应该通过这种方式)
        if field_to_update_zdmc in self.primary_keys_zdmc:
            QMessageBox.warning(self, "操作无效",
                                f"字段 '{self.field_mapper.get_ui_name(field_to_update_zdmc)}' 是主键的一部分，通常不应直接编辑。")
            original_display_text = self.format_value_for_display(original_value, zd_type)
            self.model.blockSignals(True);
            item.setText(original_display_text);
            self.model.blockSignals(False)
            return

        update_query = f"UPDATE [{self.pzgn}] SET [{field_to_update_zdmc}] = ? WHERE {where_clause}"
        update_params = (actual_value_to_save, *where_params)

        print(f"尝试更新 ({self.pzgn}): {update_query} 参数: {update_params}")
        if self.db_manager.execute_query(update_query, params=update_params, db_type="project"):
            print(f"行 {row + 1}, 列 '{self.field_mapper.get_ui_name(field_to_update_zdmc)}' 更新成功。")
            item.setData(actual_value_to_save, Qt.UserRole)  # 更新存储的原始值
        else:
            QMessageBox.critical(self, "更新失败", f"更新数据失败。")
            original_display_text = self.format_value_for_display(original_value, zd_type)
            self.model.blockSignals(True);
            item.setText(original_display_text);
            self.model.blockSignals(False)

    def parse_value_from_display(self, display_value_str, zd_type, field_zdmc_for_error_msg=""):
        """将显示的字符串值转换回适合数据库的类型"""
        try:
            if display_value_str.strip() == "": return None  # 空字符串视为NULL

            if zd_type in ['1', '2', '3', 'N', 'F', 'I', 'S', 'L', 'INT', 'INTEGER', 'NUMBER', 'FLOAT', 'DOUBLE',
                           'REAL', 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
                return float(display_value_str)  # Access ODBC通常能处理好float到各种数字类型的转换
            elif zd_type == 'D':
                return datetime.strptime(display_value_str, '%Y-%m-%d').date()
            elif zd_type == 'L':
                return True if display_value_str == "是" else False
            return display_value_str  # 文本
        except ValueError as e:
            QMessageBox.warning(self, "输入值错误",
                                f"字段 '{self.field_mapper.get_ui_name(field_zdmc_for_error_msg)}' 的值 '{display_value_str}' 格式不正确: {e}")
            return None  # 解析失败返回None

    def add_new_row_gui(self):  # GUI调用的方法
        self.add_new_row()  # 实际逻辑

    def delete_selected_rows_gui(self):  # GUI调用的方法
        self.delete_selected_rows()

    # add_new_row 和 delete_selected_rows 方法与上一轮回复中的基本一致，
    # 关键在于它们构建SQL语句时，WHERE子句需要正确使用主键和可能的父级上下文ID
    # 我们在 _build_where_clause_for_row 中处理了主键，
    # add_new_row 中在 new_row_values_dict 中填充了父级ID

    def show_context_menu(self, position):
        menu = QMenu(self)  # 指定父对象
        # (为了简单，暂时只加这两个，您可以从您的GUI需求文档中添加更多)
        add_action = menu.addAction("添加新行")
        delete_action = menu.addAction("删除选中行")
        menu.addSeparator()
        refresh_action = menu.addAction("刷新数据")

        selected_action = menu.exec(self.table_view.viewport().mapToGlobal(position))

        if selected_action == add_action:
            self.add_new_row_gui()
        elif selected_action == delete_action:
            self.delete_selected_rows_gui()
        elif selected_action == refresh_action:
            self.load_data()

    def on_row_changed(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid():
            return

        row = current.row()
        # 如果当前视图是 "z_ZuanKong" (勘探点主表)
        if self.pzgn.lower() == "z_zuanKong".lower():
            zkbh_zdmc = "ZKBH"  # 假设ZKBH的数据库字段名(ZDMC)是 "ZKBH"

            # 从 PZYM (显示列) 中找到 ZKBH 这一列的索引
            if zkbh_zdmc in self.db_fields_displayed_zdmc:
                try:
                    zkbh_col_index = self.db_fields_displayed_zdmc.index(zkbh_zdmc)
                    zkbh_item = self.model.item(row, zkbh_col_index)
                    if zkbh_item:
                        # 获取的是显示文本，如果ZKBH有特殊格式，可能需要获取原始值
                        # 我们在load_data时用item.data(Qt.UserRole)存了原始值
                        selected_zkbh_raw = zkbh_item.data(Qt.UserRole)  # 获取原始值
                        selected_zkbh_str = str(selected_zkbh_raw) if selected_zkbh_raw is not None else ""

                        print(
                            f"GenericTableView ({self.pzgn}): 钻孔选中 - ZKBH = {selected_zkbh_str} (原始值: {selected_zkbh_raw})")
                        self.boreholeSelectedSignal.emit(selected_zkbh_str)
                except ValueError:
                    print(f"警告 ({self.pzgn}): 字段'{zkbh_zdmc}'虽在PZYM中，但在模型中获取索引失败。")
                except Exception as e:
                    print(f"错误 ({self.pzgn}): 在获取选中ZKBH时发生错误: {e}")
            else:
                print(f"警告 ({self.pzgn}): 关键字段'{zkbh_zdmc}'未在PZYM配置中，无法发出钻孔选择信号。")

        # 类似地，如果 pzgn 是取样表 (如 "z_c_QuYang")，则发射 sampleSelectedSignal
        elif self.pzgn.lower() == "z_c_quyang".lower():
            qybh_zdmc = "QYBH"  # 假设QYBH的ZDMC是 "QYBH"
            if qybh_zdmc in self.db_fields_displayed_zdmc:
                try:
                    qybh_col_index = self.db_fields_displayed_zdmc.index(qybh_zdmc)
                    qybh_item = self.model.item(row, qybh_col_index)
                    if qybh_item:
                        selected_qybh_raw = qybh_item.data(Qt.UserRole)
                        selected_qybh_str = str(selected_qybh_raw) if selected_qybh_raw is not None else ""
                        print(f"GenericTableView ({self.pzgn}): 取样选中 - QYBH = {selected_qybh_str}")
                        self.sampleSelectedSignal.emit(selected_qybh_str)
                except ValueError:
                    print(f"警告 ({self.pzgn}): 字段'{qybh_zdmc}'未在PZYM配置中，无法获取选中的取样编号。")
                except Exception as e:
                    print(f"错误 ({self.pzgn}): 在获取选中QYBH时发生错误: {e}")
            else:
                print(f"警告 ({self.pzgn}): 关键字段'{qybh_zdmc}'未在PZYM配置中，无法发出取样选择信号。")

    # --- add_new_row 和 delete_selected_rows 的 WHERE 子句构建的详细实现 ---
    def add_new_row(self):
        db_type_to_use, _, zk_col_name, qy_col_name = self.determine_db_type_and_filters()
        if db_type_to_use != "project":
            QMessageBox.information(self, "操作无效", "不能向配置表添加新行。")
            return

        # 使用PZYMALL获取所有可能的字段，如果PZYMALL为空，则使用PZYM
        all_db_fields = self.table_config.get("PZYMALL", [])
        if not all_db_fields: all_db_fields = self.db_fields_displayed_zdmc
        if not all_db_fields:
            QMessageBox.warning(self, "配置错误", f"表 '{self.pzgn}' 的字段列表(PZYMALL/PZYM)为空，无法添加新行。")
            return

        new_row_data_dict = {}
        # 1. 填充上下文外键
        if self.parent_gcsy is not None and 'GCSY' in all_db_fields:
            new_row_data_dict['GCSY'] = self.parent_gcsy
        if zk_col_name and self.parent_zkbh is not None and zk_col_name in all_db_fields:
            new_row_data_dict[zk_col_name] = self.parent_zkbh
        if qy_col_name and self.parent_qybh is not None and qy_col_name in all_db_fields:
            new_row_data_dict[qy_col_name] = self.parent_qybh

        # 2. 为其他字段（尤其是主键和必填字段）获取默认值或提示用户输入
        # 简单起见，这里只插入包含上下文外键和来自g_ZiDuan默认值的记录
        for zdmc in all_db_fields:
            if zdmc not in new_row_data_dict:  # 如果不是已设置的外键
                field_def = self.config_loader.get_ziduan_definition(zdmc)
                default_val_str = field_def.get("ZDMR", "") if field_def else ""
                # 需要将 default_val_str 转换为适合数据库的类型
                zd_type_for_default = field_def.get("ZDTYPE", "0") if field_def else "0"
                parsed_default_val = self.parse_value_from_display(default_val_str, zd_type_for_default, zdmc)
                new_row_data_dict[zdmc] = parsed_default_val

        # 确保所有主键都有值 (如果主键不是自增的)
        # 对于Access的MDB，自增主键比较特殊，通常是“自动编号”类型，INSERT时可以不指定该列
        # 我们的主键配置来自 g_PeiZhi.GJZ (self.primary_keys_zdmc)
        # 如果主键不是上下文ID，且没有默认值，且不是自动编号，则需要用户输入
        # 这是一个复杂的问题，简单起见，我们假设必要的键已通过上下文或默认值提供

        columns_for_insert = list(new_row_data_dict.keys())
        values_for_insert = [new_row_data_dict[col] for col in columns_for_insert]

        if not columns_for_insert:
            QMessageBox.warning(self, "错误", "没有要插入的列数据。")
            return

        placeholders = ",".join(["?"] * len(columns_for_insert))
        sql_insert = f"INSERT INTO [{self.pzgn}] ([{'], ['.join(columns_for_insert)}]) VALUES ({placeholders})"

        print(f"尝试插入 ({self.pzgn}): {sql_insert} 参数: {tuple(values_for_insert)}")
        if self.db_manager.execute_query(sql_insert, tuple(values_for_insert), db_type="project"):
            QMessageBox.information(self, "成功", "新行已成功添加到数据库。")
            self.load_data()  # 重新加载以显示新行
        else:
            QMessageBox.critical(self, "插入失败", "无法添加新行到数据库，请检查控制台输出。")

    def delete_selected_rows(self):
        db_type_to_use, _, _, _ = self.determine_db_type_and_filters()
        if db_type_to_use != "project":
            QMessageBox.information(self, "操作无效", "不能从配置表删除行。")
            return

        selected_model_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_model_indexes:
            QMessageBox.information(self, "提示", "请先选择要删除的行。")
            return

        reply = QMessageBox.question(self, "确认删除", f"确定要删除选中的 {len(selected_model_indexes)} 行数据吗？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No: return

        rows_to_delete_indices = sorted([index.row() for index in selected_model_indexes], reverse=True)

        deleted_count_db = 0
        for row_index in rows_to_delete_indices:
            pk_values_for_row = self._get_current_row_pk_values(row_index)
            if not pk_values_for_row:
                print(f"警告({self.pzgn}): 无法获取第 {row_index + 1} 行的主键信息，跳过删除。")
                continue

            where_clause, where_params = self._build_where_clause_from_pks(pk_values_for_row)
            if not where_clause:
                print(f"警告({self.pzgn}): 无法为第 {row_index + 1} 行构建删除条件，跳过。")
                continue

            sql_delete = f"DELETE FROM [{self.pzgn}] WHERE {where_clause}"
            print(f"尝试删除 ({self.pzgn}): {sql_delete} 参数: {where_params}")
            if self.db_manager.execute_query(sql_delete, where_params, db_type="project"):
                deleted_count_db += 1
            else:
                QMessageBox.warning(self, "删除失败", f"从数据库删除第 {row_index + 1} 行时发生错误。")

        if deleted_count_db > 0:
            QMessageBox.information(self, "删除成功", f"已从数据库成功删除 {deleted_count_db} 行数据。")
            self.load_data()
        elif selected_model_indexes:
            QMessageBox.information(self, "提示", "没有行被删除。")