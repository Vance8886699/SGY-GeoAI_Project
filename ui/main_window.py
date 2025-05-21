# YuGeoTech_Project/ui/main_window.py
import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QLabel, QMenuBar, QToolBar, QStatusBar, QTreeView,
                               QSplitter, QTabWidget, QFileDialog, QMessageBox,
                               QDialog, QLineEdit, QPushButton, QFormLayout, QInputDialog, QAbstractItemView,
                               QHBoxLayout)  # 添加 QHBoxLayout
from PySide6.QtGui import QAction, QIcon, QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QModelIndex, QDateTime  # 添加 QDateTime

# 导入自定义模块 - 确保这些路径和文件名与您的项目结构一致
from .widgets.generic_table_view import GenericTableView
from .views.project_info_view import ProjectInfoView
# from .views.borehole_main_view import BoreholeMainView # 如果您有单独的BoreholeMainView，取消注释

# 假设这些模块已经有了基本定义
from core.db_manager import DBManager
from core.config_loader import ConfigLoader
from core.field_mapper import FieldMapper
from core.project_handler import ProjectHandler


# 占位：空工程模板路径，这个应该由 project_handler 内部处理或从配置读取
# EMPTY_PROJECT_TEMPLATE_PATH_UI = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'templates',
#                                               'empty_project_template.mdb')


class NewProjectDialog(QDialog):
    def __init__(self, config_loader, parent=None):  # 传入 config_loader 以获取默认 GCBZ
        super().__init__(parent)
        self.config_loader = config_loader
        self.setWindowTitle("新建工程")
        self.layout = QFormLayout(self)
        self.setMinimumWidth(350)

        default_gcbh = f"Proj_{QDateTime.currentDateTime().toString('yyyyMMddHHmmss')}"
        default_gcmc = "未命名工程"
        default_gckcjd = "详细勘察"
        # 尝试从配置获取当前执行标准的 GCBZ
        default_gcbz = self.config_loader.get_current_standard_gcbz() if self.config_loader else "0"

        self.gcbh_edit = QLineEdit(default_gcbh)
        self.gcmc_edit = QLineEdit(default_gcmc)
        self.gckcjd_edit = QLineEdit(default_gckcjd)
        self.gcbz_edit = QLineEdit(default_gcbz)
        self.gcbz_edit.setToolTip("工程规范代码 (例如: 0 代表工民建标准)")

        self.layout.addRow("工程编号 (GCBH):", self.gcbh_edit)
        self.layout.addRow("工程名称 (GCMC):", self.gcmc_edit)
        self.layout.addRow("勘察阶段 (GCKCJD):", self.gckcjd_edit)
        self.layout.addRow("规范代码 (GCBZ):", self.gcbz_edit)

        # TODO: 根据您的GUI需求文档2.12，添加其他新建工程所需的字段
        # 例如：“水平是否为Y轴”，“指北针与Y轴的夹角”，“工程坐标系”，“工程高程系”，固结压力级别等
        # 这些字段的选项可能需要从 g_DuiZhao 或其他配置表加载到 QComboBox

        self.buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.buttons_layout.addStretch()
        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        self.layout.addRow(self.buttons_layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_project_info(self):
        return {
            "GCBH": self.gcbh_edit.text().strip(),
            "GCMC": self.gcmc_edit.text().strip(),
            "GCKCJD": self.gckcjd_edit.text().strip(),
            "GCBZ": self.gcbz_edit.text().strip(),
            # TODO: 添加从其他控件获取值的代码
        }


class MainWindow(QMainWindow):
    def __init__(self, db_manager, config_loader, field_mapper, project_handler):
        super().__init__()
        self.db_manager = db_manager
        self.config_loader = config_loader
        self.field_mapper = field_mapper
        self.project_handler = project_handler

        self.current_selected_zkbh = None
        self.current_selected_qybh = None
        self.current_project_label = QLabel("当前未打开工程")
        self.setWindowTitle("星瀚禹极智岩土工程勘察")
        self.setGeometry(100, 100, 1200, 800)

        # 方案一：定义导航节点到 PZGN 的映射关系
        # 键可以是 t_field (节点显示文本), ID (节点ID), 或 t_type (节点类型)
        # 优先使用 t_field，因为它直观。如果 t_field 可能重复或改变，ID 更稳定。
        self.nav_node_to_pzgn_map = {
            # 根据您 x_tree_project 表中的 t_field 和目标 PZGN 配置,基本上都是在g_SubTree表里找
            # 示例 (您需要根据您的实际 x_tree_project.t_field 和期望的PZGN来填写):
            "工程信息": "x_GongCheng",
            "标准地层": "g_STuCengGC",  # 假设 "标准地层" 节点的 t_field 是 "标准地层"
            "设计勘探点表": "t_ZuanKong_SJZK",  # 假设设计勘探点表对应的 PZGN
            "勘探点表": "z_ZuanKong",  # 这是关键！
            "地层表": "z_g_TuCeng",
            "取样表": "z_c_QuYang",
            "标贯": "z_y_BiaoGuan",  # 假设 "标贯" 节点的 t_field 是 "标贯"
            "动探": "z_y_DongTan",
            "单桥静探": "z_y_JingTan", #  z_y_JingTan 在 g_PeiZhi 中可能配置为单桥 [cite: 7]
            "双桥静探": "z_y_JingTanSQ",#  z_y_JingTanSQ 专门用于双桥静探 [cite: 15]
            "抽水试验表": "z_y_ChouShui",
            "压水试验表": "z_y_YaShui_SJ",
            "注水试验表": "z_y_ZhuShui",
            # 新增的映射
            "平板载荷试验": "z_ZuanKongZH",# g_SpecialPeiZhi PAGENAME, g_Stat_WLLXTJModel TJTableName [cite: 53, 54]
            "螺旋板载荷试验": "z_y_LuoXuanBan",  # g_PeiZhiZhiYu ZDMC (作为表名) [cite: 51]
            "扁铲侧胀": "t_BianBanCZSYSJ",
            "旁压": "z_y_PangYa",
            "十字板": "z_y_ShiZiBan",
            "平硐表": "PD_BaseInfo",  # g_TableName 中 TNMC="t_PingDong", TNMS="平硐" [cite: 50]
            "探坑(竖井)表": "SJ_BaseInfo",  # g_TableName 中 TNMC="t_TanKeng", TNMS="探坑(竖井)" [cite: 50]
            "探槽表": "TC_BaseInfo",  # g_TableName 中 TNMC="t_TanCao", TNMS="探槽" [cite: 50]
            "剖面图": "p_PouXian",  # x_tree_project_Single t_table, p_PouXian.json 是剖面线定义表 [cite: 49, 15]
            "地基承载力和桩参数表": "x_diceng",  # g_SubTree ZSBH, g_TableName TNMC="x_ChengZaiLi" [cite: 47, 50]
            "工程地质单元": "p_GCDZDY",  # g_SubTree ZSBH, g_TableName TNMC="g_GongChengDZDY" [cite: 47, 50]
            "等高线测量点": "d_DengGaoXian",# d_DengGaoXianLine.json 是等高线数据表[cite: 4], x_tree_project_Single t_field "等高线" 关联 t_table "d_DengGaoXianLine" [cite: 49]
            "设计文件": "t_WenJianML", # x_tree_project_Single t_field "设计文件" 关联 t_table "t_WenJianML" (工程文件目录管理表) [cite: 49, 50]
            "成果文件": "t_WenJianML",  # x_tree_project_Single t_field "成果文件" 关联 t_table "t_WenJianML" [cite: 49, 50]
            "室内试验": "z_c_ShiYan",  # 对应 “综合试验（总表）”
            "原位测试": "z_y_ShiYan",  # 对应 “原位测试综合表”
            "土工试验": "t_TuGong",  # 对应 “土工试验原始数据及成果表”
            "岩石试验": "t_YanShi",  # 对应 “岩石试验数据表”
            # 注意：以下节点在g_SubTree中其ZSBH为列表，表示它们是多个具体试验的集合。
            # 如果您的UI设计中，点击这些节点会加载一个特定的、单一的汇总表或默认表，
            # 则以下PZGN是基于此假设的代表性选择。
            # 否则，这些节点更多是作为“文件夹”来组织下一级具体试验。
            "常规试验": "t_TuGong",  # 代表性的土工试验数据，因其是“土工试验”的子集
            # 或者 z_c_QuYang (取样表，汇总了多项常规物理性质)
            "化学试验": "t_ShuiZhiFenXi",  # 代表性的化学分析试验 (水质全分析)
            # 或者 t_YiRongYan (易溶盐分析)
            # ... 其他从 x_tree_project 的 t_field 到 PZGN 的映射 ...
            # 对于二级或三级导航（例如“室内试验”下的“土工试验”再下的“常规试验”）
            # 如果这些子级也通过点击主导航树节点后，在某个地方（如 Tab 页内的新 TreeView 或 ToolBar）触发，
            # 那么那些子导航的点击事件也需要类似的映射逻辑或直接使用正确的 PZGN。
            # 目前我们只处理主导航树的点击。
        }
        # 您也可以准备一个基于ID的映射（如果ID更可靠）
        self.nav_node_id_to_pzgn_map = {

            1: "z_ZuanKong",# 勘探点表
            -2: "g_STuCengGC",  # 标准地层
            -1: "t_ZuanKong_SJZK",  # 设计勘探点表
            0: "x_GongCheng",  # 工程信息 (GCMC节点对应的表)
            5: "SJ_BaseInfo",  # 探坑(竖井) (t_field="探坑(竖井)", ID=3, t_table="t_TanKeng")
            6: "TC_BaseInfo",  # 探槽表 (t_field="探槽", ID=4, t_table="t_TanCao")
            4: "PD_BaseInfo",  # 平硐表 (t_field="平硐", ID=5, t_table="t_PingDong")
            7: "p_PouXian",  # 剖面图 (t_field="剖面图", ID=-5, t_table="t_PouXian")
            10: "d_DengGaoXian",  # 等高线 (t_field="等高线", ID=-6, t_table="d_DengGaoXianLine")
            11: "t_WenJianML",  # 设计文件 (t_field="设计文件", ID=-10, t_table="t_WenJianML")
            12: "t_WenJianML",  # 成果文件 (t_field="成果文件", ID=-11, t_table="t_WenJianML")
            # 来自 g_SubTree.json (ZSBS 作为 ID) [cite: 47]
            2: "z_ZuanKongZH",  # 平板载荷试验 (ZSMC="平板载荷", ZSBH="t_BianBanCZSYSJ", ZSBS=10806)
            3: "z_y_LuoXuanBan",  # 螺旋板载荷试验 (ZSMC="螺旋板载荷", ZSBH="z_y_LuoXuanBan", ZSBS=10807)
            8: "x_diceng",  # 地基承载力和桩参数表 (ZSMC="地基承载力和桩参数表", ZSBH="x_ChengZaiLi", ZSBS=20200)
            9: "p_GCDZDY",  # 工程地质单元 (ZSMC="工程地质单元划分", ZSBH="g_GongChengDZDY", ZSBS=30000)
            # 新增的映射 (ID 主要参考 x_tree_project_Single.ID 和 g_SubTree.ZSBS)
            # 来自 x_tree_project_Single.json
            1222: "z_c_ShiYan",  # 室内试验
            1116: "z_y_ShiYan",  # 原位测试
            # 来自 g_SubTree.json (ZSBS 作为 ID)
            # 注意: 某些ID可能对应的是文件夹或分组，PZGN是代表性的选择
            11001: "t_TuGong",  # 土工试验 (ZSBS for the folder, PZGN for the representative table)
            1100101: "t_TuGong",  # 常规试验 (ZSBS for the group, PZGN is representative)
            11002: "t_YanShi",  # 岩石试验
            11003: "t_ShuiZhiFenXi",  # 化学试验 (ZSBS for the group, PZGN is representative)
            # ... 其他 ID 到 PZGN 的映射
        }

        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()
        self._setup_central_widget()
        self._load_navigation_tree()

    def _create_actions(self):  # 调整“导入”按钮的初始状态
        self.new_project_action = QAction(QIcon(), "新建工程(N)...", self)
        self.new_project_action.triggered.connect(self.handle_new_project)
        self.open_project_action = QAction(QIcon(), "打开工程(O)...", self)
        self.open_project_action.triggered.connect(self.handle_open_project)
        self.close_project_action = QAction(QIcon(), "关闭工程", self)
        self.close_project_action.triggered.connect(self.handle_close_project)
        self.close_project_action.setEnabled(False)

        # 根据您的最新澄清，如果“导入其他工程数据”应该在未打开工程时可用
        # 那么这里就应该设置为 True。后续 handle_import_other_project 需要相应调整。
        # 如果还是维持原状（打开工程后可用），则这里保持 False。
        # 暂时维持原逻辑，打开工程后启用。
        self.import_other_project_action = QAction(QIcon(), "导入其他工程数据...", self)
        self.import_other_project_action.triggered.connect(self.handle_import_other_project)
        self.import_other_project_action.setEnabled(False)

        self.exit_action = QAction(QIcon(), "退出(X)", self)
        self.exit_action.triggered.connect(self.close)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        project_menu = menu_bar.addMenu("工程管理(&M)")
        project_menu.addAction(self.new_project_action)
        project_menu.addAction(self.open_project_action)
        project_menu.addAction(self.close_project_action)
        project_menu.addSeparator()
        project_menu.addAction(self.import_other_project_action)  # 添加到菜单
        project_menu.addSeparator()
        project_menu.addAction(self.exit_action)

        data_entry_menu = menu_bar.addMenu("数据录入(&J)")
        # TODO: Add more menus and actions based on GUI requirements

    def _create_tool_bar(self):
        tool_bar = QToolBar("主工具栏")
        self.addToolBar(tool_bar)
        tool_bar.addAction(self.new_project_action)
        tool_bar.addAction(self.open_project_action)

    def _create_status_bar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.addWidget(self.current_project_label)

    def _setup_central_widget(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QHBoxLayout(self.central_widget)
        splitter = QSplitter(Qt.Horizontal)
        self.nav_tree = QTreeView()
        self.nav_tree.clicked.connect(self.on_nav_tree_clicked)
        splitter.addWidget(self.nav_tree)
        self.main_tab_widget = QTabWidget()
        self.main_tab_widget.setTabsClosable(True)
        self.main_tab_widget.tabCloseRequested.connect(self.main_tab_widget.removeTab)
        welcome_label = QLabel("欢迎使用岩土工程勘察软件！请新建或打开一个工程。")
        welcome_label.setAlignment(Qt.AlignCenter)
        self.main_tab_widget.addTab(welcome_label, "欢迎")
        splitter.addWidget(self.main_tab_widget)
        splitter.setSizes([250, 950])
        layout.addWidget(splitter)

    def _load_navigation_tree(self):
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['工程与模块导航'])
        root_node_std_item = model.invisibleRootItem()
        self.nav_tree.setModel(model)

        if not self.project_handler.current_project_path:
            return

        project_name_from_path, _ = os.path.splitext(os.path.basename(self.project_handler.current_project_path))
        project_display_name = project_name_from_path  # 默认值

        # 修正获取工程名称的SQL查询
        if self.project_handler.current_project_gcsy is not None:
            gcmc_data = self.db_manager.execute_query(  # 使用 execute_query
                "SELECT [GCMC] FROM [x_GongCheng] WHERE [GCSY] = ?",
                params=(self.project_handler.current_project_gcsy,),
                db_type="project"
            )
            if gcmc_data and len(gcmc_data) > 0 and gcmc_data[0] and gcmc_data[0][0]:
                project_display_name = gcmc_data[0][0]
            else:
                print(
                    f"警告: 未能从 x_GongCheng 获取到 GCSY={self.project_handler.current_project_gcsy} 的工程名称。将使用文件名。")

        project_std_item = QStandardItem(project_display_name)
        project_std_item.setEditable(False)
        project_std_item.setData(
            {"t_field": project_display_name, "t_table": "x_GongCheng", "t_type": "project_root",
             "ID": "PROJECT_ROOT_UI_ID_ACTUAL"},  # 使用一个唯一的字符串ID避免与数字ID冲突
            Qt.UserRole + 1
        )
        root_node_std_item.appendRow(project_std_item)

        raw_nodes = self.config_loader.get_project_tree_raw_nodes()
        if not raw_nodes:
            print("导航树：ConfigLoader 未返回任何导航节点数据。")
            return

        # ----------- 数据补丁：修正 GCMC (ID=0) 的父节点问题 -----------
        # 这个补丁的目的是如果发现 ID=0 的 t_parentID 是 -1，并且 ID=-1 的 t_parentID 是 0，
        # 则强制将 ID=0 的 t_parentID 改为 0，以打破循环并使其成为顶级节点。
        node_0_info = None
        node_minus_1_info = None
        for node_dict in raw_nodes:
            if node_dict.get('ID') == 0:
                node_0_info = node_dict
            elif node_dict.get('ID') == -1:
                node_minus_1_info = node_dict

        if node_0_info and node_minus_1_info:
            if node_0_info.get('t_parentID') == -1 and node_minus_1_info.get('t_parentID') == 0:
                print("补丁应用：检测到 GCMC(ID=0, parent=-1) 与 设计勘探点表(ID=-1, parent=0) 的潜在循环。")
                print(
                    f"  原GCMC节点信息: ID={node_0_info.get('ID')}, t_parentID={node_0_info.get('t_parentID')}, t_field={node_0_info.get('t_field')}")
                node_0_info['t_parentID'] = 0  # 强制 GCMC 的父节点为 0
                print(
                    f"  修改后GCMC节点信息: ID={node_0_info.get('ID')}, t_parentID={node_0_info.get('t_parentID')}, t_field={node_0_info.get('t_field')}")
        # ----------- 数据补丁结束 -----------

        all_nodes_map = {}
        nodes_by_parent_id = {}  # 键是 t_parentID，值是拥有此 t_parentID 的节点列表

        # 重新构建 all_nodes_map 和 nodes_by_parent_id，因为 raw_nodes 可能已被补丁修改
        # valid_raw_nodes 逻辑用于排除直接自循环，是好的，保留。
        valid_raw_nodes_after_patch = []
        for node_data_dict in raw_nodes:  # 使用可能被补丁修改过的 raw_nodes
            node_id = node_data_dict.get('ID')
            parent_id = node_data_dict.get('t_parentID')  # 这个 parent_id 可能已被补丁修改
            if node_id is None: continue

            all_nodes_map[node_id] = node_data_dict  # 更新 all_nodes_map

            if parent_id is not None and node_id == parent_id:  # 直接自循环检查
                print(
                    f"警告: 导航树节点数据中发现直接自循环! ID={node_id}, t_field='{node_data_dict.get('t_field')}'. 此节点将不会被添加到树中。")
                if node_id in all_nodes_map: del all_nodes_map[node_id]  # 从map中也移除
                continue
            valid_raw_nodes_after_patch.append(node_data_dict)

        # 使用处理过直接自循环且可能被补丁修改过的节点列表来构建 nodes_by_parent_id
        for node_data_dict in valid_raw_nodes_after_patch:
            parent_id_val = node_data_dict.get('t_parentID')
            if parent_id_val is not None:
                if parent_id_val not in nodes_by_parent_id: nodes_by_parent_id[parent_id_val] = []
                nodes_by_parent_id[parent_id_val].append(node_data_dict)

        # --- 顶级节点收集逻辑保持不变 ---
        top_level_children_data = []
        # 根据您之前截图112.jpg和console输出，t_parentID=0 是主要的顶级父ID标记
        # t_parentID=-1 在您的数据中被用作了 GCMC(ID=0)的父，如果补丁生效，GCMC(ID=0)的父会变成0
        # 所以这里 root_parent_ids_to_process 应该主要关注 0
        # 如果您的原始配置中，确实有其他顶级模块的 t_parentID 设置为 -1（且-1不是某个模块的ID）
        # 那么也需要包含 -1。但鉴于 GCMC 的情况，-1 现在更像是一个普通节点的ID。
        # 为了安全，我们先假设只有 t_parentID=0 的是顶级（补丁会把GCMC也归到这里）
        root_parent_ids_to_process = [0]
        # 如果你的x_tree_project设计中，-1也可能作为顶级父ID（而非某个模块的ID），可以再加入-1
        # 例如，如果存在 ID=100, t_parentID=-1 这样的顶级模块。
        # 但从你的数据看，ID=-1 本身就是一个模块（设计勘探点表）。

        processed_top_level_node_ids = set()

        for root_parent_id in root_parent_ids_to_process:
            if root_parent_id in nodes_by_parent_id:
                for node_data in nodes_by_parent_id[root_parent_id]:
                    node_id = node_data.get('ID')
                    if node_id not in processed_top_level_node_ids:
                        top_level_children_data.append(node_data)
                        processed_top_level_node_ids.add(node_id)

        sorted_top_level_children = sorted(top_level_children_data,
                                           key=lambda x: (x.get('ID', 0), x.get('t_field', '')))

        for node_data in sorted_top_level_children:
            item_text = node_data.get('t_field', '未命名节点')
            std_item = QStandardItem(item_text)
            std_item.setEditable(False)
            std_item.setData(node_data, Qt.UserRole + 1)
            project_std_item.appendRow(std_item)

            node_id_val = node_data.get('ID')
            # 检查此顶级节点是否应有子节点 (即，它的 ID 是否作为其他节点的 t_parentID)
            if node_id_val is not None and node_id_val in nodes_by_parent_id:
                # nodes_by_parent_id[node_id_val] 才是这个节点的直接子节点列表
                self._build_tree_recursively(std_item, node_id_val, all_nodes_map, nodes_by_parent_id, {node_id_val})

            if node_data.get('t_expand') == 1:
                self.nav_tree.expand(std_item.index())

        self.nav_tree.expand(project_std_item.index())
        print(f"导航树已动态加载，工程 '{project_display_name}' 下有 {project_std_item.rowCount()} 个主模块/文件夹。")

    def _build_tree_recursively(self, parent_std_item, parent_id_value, all_nodes_map, nodes_by_parent_id,
                                visited_ids_in_current_path):
        # ... (此方法内部逻辑与您上一版本类似，主要是确保 visited_ids_in_current_path 正确用于防止分支内的循环)
        if parent_id_value not in nodes_by_parent_id:
            return

        child_nodes_data = sorted(nodes_by_parent_id[parent_id_value],
                                  key=lambda x: (x.get('ID', 0), x.get('t_field', '')))

        for node_data in child_nodes_data:
            node_id_val = node_data.get('ID')
            item_text = node_data.get('t_field', '未命名节点')

            if node_id_val is None: continue

            if node_id_val in visited_ids_in_current_path:
                print(
                    f"警告(_build_tree_recursively): 检测到递归路径! 节点ID {node_id_val} ('{item_text}') 已在此路径中，跳过构建其子树。路径: {visited_ids_in_current_path}")
                continue

            std_item = QStandardItem(item_text)
            std_item.setEditable(False)
            std_item.setData(node_data, Qt.UserRole + 1)
            parent_std_item.appendRow(std_item)

            if node_id_val in nodes_by_parent_id:
                new_visited_path = visited_ids_in_current_path.copy()
                new_visited_path.add(node_id_val)
                self._build_tree_recursively(std_item, node_id_val, all_nodes_map, nodes_by_parent_id, new_visited_path)

            if node_data.get('t_expand') == 1:
                self.nav_tree.expand(std_item.index())

    def on_nav_tree_clicked(self, index: QModelIndex):
        print("--- on_nav_tree_clicked ---")
        item = self.nav_tree.model().itemFromIndex(index)
        if not item:
            print("  点击的item无效")
            return

        node_data = item.data(Qt.UserRole + 1)
        # print(f"  获取到的原始UserRole+1数据: {node_data}") # 详细调试

        if not node_data or not isinstance(node_data, dict):
            print(f"  节点 '{item.text()}' 没有关联的 UserRole+1 数据或数据格式不正确。")
            return

        item_text = node_data.get("t_field", "未知模块")
        pzgn_from_t_table = node_data.get("t_table")  # 来自 x_tree_project.t_table
        node_type = node_data.get("t_type")
        node_id = node_data.get("ID")

        actual_pzgn_to_use = None

        print(
            f"  导航树点击: 文本='{item_text}', 原始t_table='{pzgn_from_t_table}', 类型='{node_type}', ID='{node_id}'")

        # 方案一：实现映射逻辑
        if pzgn_from_t_table and pzgn_from_t_table.lower() not in ["文件夹", "名称", "", None]:
            # 如果 t_table 本身就是一个有效的 PZGN (不是特殊值，例如直接就是 "z_ZuanKong")
            if self.config_loader.get_table_config(pzgn_from_t_table):
                actual_pzgn_to_use = pzgn_from_t_table
                print(f"  直接使用 t_table 作为 PZGN: '{actual_pzgn_to_use}'")
            else:
                print(f"  t_table ('{pzgn_from_t_table}')看起来像PZGN，但在g_PeiZhi中未找到配置。")

        if not actual_pzgn_to_use:
            # 如果 t_table 是 "名称"、"文件夹" 或空，或者虽然不是这些但配置不存在，则尝试映射
            # 1. 优先通过节点ID映射
            if node_id in self.nav_node_id_to_pzgn_map:
                actual_pzgn_to_use = self.nav_node_id_to_pzgn_map[node_id]
                print(f"  通过节点ID '{node_id}' 映射到 PZGN: '{actual_pzgn_to_use}'")
            # 2. 其次通过节点文本 (t_field) 映射
            elif item_text in self.nav_node_to_pzgn_map:
                actual_pzgn_to_use = self.nav_node_to_pzgn_map[item_text]
                print(f"  通过节点文本 '{item_text}' 映射到 PZGN: '{actual_pzgn_to_use}'")
            # 3. （可选）可以通过 t_type 映射，如果类型与功能一一对应
            # elif node_type and node_type in self.nav_node_type_to_pzgn_map: # 假设有这样一个映射
            #     actual_pzgn_to_use = self.nav_node_type_to_pzgn_map[node_type]
            #     print(f"  通过节点类型 '{node_type}' 映射到 PZGN: '{actual_pzgn_to_use}'")

        if actual_pzgn_to_use:
            if actual_pzgn_to_use.lower() == "z_zuankong":
                self.set_current_borehole_context(None)
            elif actual_pzgn_to_use.lower() == "z_c_quyang" and self.current_selected_zkbh:
                self.set_current_sample_context(None)

            # 再次确认映射后的PZGN是否有配置
            if not self.config_loader.get_table_config(actual_pzgn_to_use):
                QMessageBox.warning(self, "配置缺失",
                                    f"导航节点 '{item_text}' (ID: {node_id}) 映射到的PZGN '{actual_pzgn_to_use}' "
                                    f"在 g_PeiZhi 中未找到其配置。无法打开视图。")
                print(f"  错误: 映射得到的PZGN '{actual_pzgn_to_use}' 没有有效的g_PeiZhi配置。")
                return

            self.open_data_view_tab(item_text, actual_pzgn_to_use)

        elif pzgn_from_t_table and pzgn_from_t_table.lower() == "文件夹":  # 或者判断 node_type
            print(f"  点击了文件夹节点: '{item_text}' (原始t_table: '{pzgn_from_t_table}'), 不打开数据视图。")
            if self.nav_tree.isExpanded(index):
                self.nav_tree.collapse(index)
            else:
                self.nav_tree.expand(index)
        else:
            print(f"  节点 '{item_text}' (原始t_table: '{pzgn_from_t_table}', 类型: '{node_type}') "
                  f"无法确定有效的PZGN来打开数据视图。")

    def open_data_view_tab(self, tab_title, pzgn):  # pzgn应该是最终确定的、有效的PZGN
        if not self.project_handler.current_project_path:
            QMessageBox.warning(self, "提示", "请先打开一个工程项目。")
            return

        if not pzgn or not self.config_loader.get_table_config(pzgn):  # 再次校验pzgn有效性
            QMessageBox.warning(self, "配置错误", f"尝试打开视图失败：PZGN '{pzgn}' 无效或其配置未在g_PeiZhi中找到。")
            print(f"  open_data_view_tab: PZGN '{pzgn}' 无效或配置缺失。")
            return

        # 检查是否已存在与当前PZGN和上下文完全匹配的标签页
        for i in range(self.main_tab_widget.count()):
            existing_view = self.main_tab_widget.widget(i)
            if hasattr(existing_view, 'pzgn') and existing_view.pzgn == pzgn:
                context_match = True
                # 对于需要钻孔上下文的表
                db_type, filter_gcsy, zk_col, qy_col = existing_view.determine_db_type_and_filters() if hasattr(
                    existing_view, 'determine_db_type_and_filters') else (None, False, None, None)

                if zk_col and hasattr(existing_view,
                                      'parent_zkbh') and existing_view.parent_zkbh != self.current_selected_zkbh:
                    context_match = False
                if qy_col and hasattr(existing_view,
                                      'parent_qybh') and existing_view.parent_qybh != self.current_selected_qybh:
                    context_match = False

                if context_match:
                    self.main_tab_widget.setCurrentIndex(i)
                    # 可选：如果视图已存在且上下文匹配，是否需要强制刷新数据？
                    # if hasattr(existing_view, 'load_data'): existing_view.load_data()
                    return
                else:
                    print(
                        f"  PZGN '{pzgn}' 的标签页上下文不匹配，将关闭并重建。旧ZKBH: {getattr(existing_view, 'parent_zkbh', 'N/A')}, 新ZKBH: {self.current_selected_zkbh}")
                    self.main_tab_widget.removeTab(i)
                    break  # 移除后需要重新创建

        view_widget = None
        current_gcsy = self.project_handler.get_current_project_gcsy()

        if pzgn.lower() == "x_gongcheng":
            view_widget = ProjectInfoView(
                pzgn, self.db_manager, self.config_loader, self.field_mapper, self.project_handler,
                parent=self
            )
        else:  # 其他 PZGN 统一使用 GenericTableView
            active_parent_zkbh = self.current_selected_zkbh
            active_parent_qybh = self.current_selected_qybh

            # 如果是勘探点主表，不应该传递钻孔上下文作为过滤器
            if pzgn.lower() == "z_zuankong":
                active_parent_zkbh = None
                active_parent_qybh = None
            # 如果是取样主表，且当前没有选钻孔，它也不应该被钻孔过滤（尽管通常它应该在选定钻孔后才出现）
            elif pzgn.lower() == "z_c_quyang" and not self.current_selected_zkbh:
                active_parent_zkbh = None  # 理论上不应发生，除非导航允许直接打开所有取样
                active_parent_qybh = None

            print(
                f"  实例化 GenericTableView: PZGN='{pzgn}', GCSY='{current_gcsy}', parent_ZKBH='{active_parent_zkbh}', parent_QYBH='{active_parent_qybh}'")
            view_widget = GenericTableView(
                pzgn, self.db_manager, self.config_loader, self.field_mapper, self.project_handler,
                parent_gcsy=current_gcsy,
                parent_zkbh=active_parent_zkbh,
                parent_qybh=active_parent_qybh,
                parent=self
            )
            view_widget.setObjectName(f"generic_view_{pzgn}")

        if view_widget:
            if isinstance(view_widget, GenericTableView):
                if hasattr(view_widget, 'boreholeSelectedSignal'):
                    view_widget.boreholeSelectedSignal.connect(self.set_current_borehole_context)
                if hasattr(view_widget, 'sampleSelectedSignal'):
                    view_widget.sampleSelectedSignal.connect(self.set_current_sample_context)

            index = self.main_tab_widget.addTab(view_widget, tab_title)
            self.main_tab_widget.setCurrentIndex(index)
            print(f"  成功创建视图并添加到标签页: '{tab_title}' (PZGN: {pzgn})")
        else:
            QMessageBox.warning(self, "视图创建错误", f"未能为模块 '{tab_title}' (PZGN: {pzgn}) 创建视图。")
            print(f"  创建视图失败: PZGN='{pzgn}', 标题='{tab_title}'")

    def set_current_borehole_context(self, zkbh_str: str):
        selected_zkbh = str(zkbh_str).strip() if zkbh_str and zkbh_str.strip() else None
        if self.current_selected_zkbh != selected_zkbh:
            self.current_selected_zkbh = selected_zkbh
            self.current_selected_qybh = None
            print(f"MainWindow: 钻孔上下文更新为 ZKBH = {self.current_selected_zkbh}")
            status_msg = f"工程: {os.path.basename(self.project_handler.current_project_path or 'N/A')}"
            if self.current_selected_zkbh: status_msg += f" | 钻孔: {self.current_selected_zkbh}"
            self.statusBar.showMessage(status_msg, 0)
            self.update_context_sensitive_views_and_nav()

    def set_current_sample_context(self, qybh_str: str):
        selected_qybh = str(qybh_str).strip() if qybh_str and qybh_str.strip() else None
        if self.current_selected_qybh != selected_qybh:
            self.current_selected_qybh = selected_qybh
            print(f"MainWindow: 取样上下文更新为 QYBH = {self.current_selected_qybh} (ZKBH: {self.current_selected_zkbh})")
            status_msg = f"工程: {os.path.basename(self.project_handler.current_project_path or 'N/A')}"
            if self.current_selected_zkbh: status_msg += f" | 钻孔: {self.current_selected_zkbh}"
            if self.current_selected_qybh: status_msg += f" | 取样: {self.current_selected_qybh}"
            self.statusBar.showMessage(status_msg, 0)
            self.update_context_sensitive_views_and_nav()

    def update_context_sensitive_views_and_nav(self):
        print(f"更新上下文敏感视图: 当前ZKBH={self.current_selected_zkbh}, 当前QYBH={self.current_selected_qybh}")
        for i in range(self.main_tab_widget.count()):
            view = self.main_tab_widget.widget(i)
            if isinstance(view, GenericTableView):
                needs_refresh = False
                db_type, filter_gcsy, zk_col, qy_col = view.determine_db_type_and_filters()
                if zk_col:
                    if view.parent_zkbh != self.current_selected_zkbh:
                        print(f"  视图 {view.pzgn} 的钻孔上下文从 {view.parent_zkbh} 更新为 {self.current_selected_zkbh}")
                        view.parent_zkbh = self.current_selected_zkbh
                        view.parent_qybh = None
                        needs_refresh = True
                if qy_col:
                    if zk_col and view.parent_zkbh == self.current_selected_zkbh:
                        if view.parent_qybh != self.current_selected_qybh:
                            print(f"  视图 {view.pzgn} 的取样上下文从 {view.parent_qybh} 更新为 {self.current_selected_qybh}")
                            view.parent_qybh = self.current_selected_qybh
                            needs_refresh = True
                    elif not zk_col:
                         if view.parent_qybh != self.current_selected_qybh:
                            print(f"  视图 {view.pzgn} 的取样上下文从 {view.parent_qybh} 更新为 {self.current_selected_qybh}")
                            view.parent_qybh = self.current_selected_qybh
                            needs_refresh = True
                if needs_refresh:
                    print(f"  因上下文变化，将刷新数据: 标签 '{self.main_tab_widget.tabText(i)}', 视图PZGN: {view.pzgn}")
                    view.load_data()
        # TODO: 动态更新导航树（例如，在选中钻孔后，在导航树中该钻孔下显示其子模块）

    def handle_import_other_project(self):
        if not self.project_handler.current_project_path:
            QMessageBox.warning(self, "操作无效", "请先打开或创建一个目标工程。")
            return

        source_mdb_path, _ = QFileDialog.getOpenFileName(
            self, "选择源工程数据库文件",
            self.project_handler.workspace_dir,
            "Access 数据库 (*.mdb)"
        )
        if not source_mdb_path: return
        if source_mdb_path == self.project_handler.current_project_path:
            QMessageBox.warning(self, "操作无效", "不能选择当前打开的工程作为源工程。")
            return

        reply = QMessageBox.question(
            self, "确认导入",
            f"确定要从工程:\n{os.path.basename(source_mdb_path)}\n导入数据到当前工程:\n{os.path.basename(self.project_handler.current_project_path)}吗?\n\n此操作可能修改当前工程数据，请谨慎！\n建议先备份当前工程。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No: return

        # 这里需要您在 ProjectHandler 中实现 import_data_from_project 方法
        success, message = self.project_handler.import_data_from_project(source_mdb_path)
        if success:
            QMessageBox.information(self, "导入成功", message or "数据导入成功完成。请刷新相关视图查看数据。")
            # 刷新所有已打开的 GenericTableView
            for i in range(self.main_tab_widget.count()):
                view = self.main_tab_widget.widget(i)
                if isinstance(view, GenericTableView) and hasattr(view, 'load_data'):
                    print(f"刷新视图: {self.main_tab_widget.tabText(i)}")
                    view.load_data()
        else:
            QMessageBox.critical(self, "导入失败", message or "数据导入过程中发生错误。")
    def handle_new_project(self):
        dialog = NewProjectDialog(self.config_loader, self)
        if dialog.exec():
            project_info = dialog.get_project_info()
            if not project_info["GCBH"] or not project_info["GCMC"]:
                QMessageBox.warning(self, "输入错误", "工程编号和工程名称不能为空。")
                return

            result = self.project_handler.create_new_project(project_info)
            if result:
                proj_path, proj_gcsy = result
                self.current_project_label.setText(f"当前工程: {os.path.basename(proj_path)} (GCSY: {proj_gcsy})")
                self.close_project_action.setEnabled(True)
                self.import_other_project_action.setEnabled(True) # 启用导入
                self._clear_tabs_and_reload_nav()
                QMessageBox.information(self, "成功", f"新工程 '{project_info['GCMC']}' 已创建并打开。")
                self.open_data_view_tab("工程信息", "x_GongCheng")
            else:
                QMessageBox.critical(self, "错误", "创建新工程失败。请查看控制台输出。")


    def handle_open_project(self):
        workspace_path = self.project_handler.workspace_dir
        file_path, _ = QFileDialog.getOpenFileName(self, "打开工程数据库", workspace_path, "Access数据库 (*.mdb)")
        if file_path:
            if self.project_handler.open_project(file_path):
                gcsy = self.project_handler.get_current_project_gcsy()
                self.current_project_label.setText(f"当前工程: {os.path.basename(file_path)} (GCSY: {gcsy})")
                self.close_project_action.setEnabled(True)
                self.import_other_project_action.setEnabled(True) # 启用导入
                self._clear_tabs_and_reload_nav()
                self.open_data_view_tab("工程信息", "x_GongCheng")
            else:
                QMessageBox.critical(self, "错误", "打开工程失败。")

    def _clear_tabs_and_reload_nav(self):
        current_tab_count = self.main_tab_widget.count()
        for i in range(current_tab_count - 1, -1, -1):
            if self.main_tab_widget.tabText(i) != "欢迎":
                self.main_tab_widget.removeTab(i)

        if self.main_tab_widget.count() == 0 or self.main_tab_widget.tabText(0) != "欢迎":
            if self.main_tab_widget.count() > 0 and self.main_tab_widget.tabText(0) == "欢迎":
                self.main_tab_widget.removeTab(0)
            welcome_label = QLabel("欢迎使用软件！请新建或打开工程，或从导航树选择模块。")
            welcome_label.setAlignment(Qt.AlignCenter)
            self.main_tab_widget.insertTab(0, welcome_label, "欢迎")
        self.main_tab_widget.setCurrentIndex(0)

        self.current_selected_zkbh = None
        self.current_selected_qybh = None
        self._load_navigation_tree()

    def handle_close_project(self):
        self.project_handler.close_current_project()
        self.current_project_label.setText("当前未打开工程")
        self.close_project_action.setEnabled(False)
        self.import_other_project_action.setEnabled(False) # 禁用导入
        self.current_selected_zkbh = None
        self.current_selected_qybh = None
        self._clear_tabs_and_reload_nav()
        QMessageBox.information(self, "提示", "当前工程已关闭。")

    def closeEvent(self, event):
        reply = QMessageBox.question(self, '确认退出', "确定要退出软件吗?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.project_handler and hasattr(self.project_handler, 'close_current_project'):
                self.project_handler.close_current_project()
            if self.db_manager:  # 确保db_manager存在
                self.db_manager.close_project_db()  # 关闭工程库
                # Config库的连接应该在DBManager的__del__中处理，或在main.py退出前显式关闭
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    project_root_for_test = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root_for_test not in sys.path:
        sys.path.insert(0, project_root_for_test)
        print(f"测试时，已将项目根目录 {project_root_for_test} 添加到 sys.path")

    mock_db_manager = DBManager()
    if not mock_db_manager.config_conn:
        print("错误：无法连接到 system_config.mdb，MainWindow 测试无法继续。")
        sys.exit(-1)

    mock_config_loader = ConfigLoader(mock_db_manager)
    mock_field_mapper = FieldMapper(mock_config_loader)

    test_workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "workspace_test_main_window")
    os.makedirs(test_workspace, exist_ok=True)
    mock_project_handler = ProjectHandler(mock_db_manager, test_workspace)

    main_win = MainWindow(mock_db_manager, mock_config_loader, mock_field_mapper, mock_project_handler)
    main_win.show()
    sys.exit(app.exec())