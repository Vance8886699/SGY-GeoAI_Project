# YuGeoTech_Project/core/config_loader.py

class ConfigLoader:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.ziduan_definitions = {}
        self.table_configs = {}
        self.dropdown_options = {}
        self.rock_soil_types = []
        self.project_tree_raw_nodes = []
        # GCBZ 来自 x_GongCheng 表 [cite: 18]
        # x_tree_project 也包含 GCBZ 列 [cite: 50]
        self.project_tree_config_name = "x_tree_project"

        self._load_all_configs()


    def get_current_standard_gcbz_numeric(self):
        data = self.db_manager.get_table_data("CFGCurZXBZ", db_type="config", columns="ZXBZ")
        if data and data[0] and data[0][0] is not None:
            try:
                return int(str(data[0][0]))
            except ValueError:
                print(f"警告: CFGCurZXBZ.ZXBZ 的值 '{data[0][0]}' 无法转换为整数，将使用默认值 0。")
                return 0
        return 0

    def _load_all_configs(self):
        print("开始加载系统配置...")
        self._load_ziduan_definitions()
        self._load_table_configs()
        self._load_dropdown_options()
        self._load_project_tree_structure() # 确保在需要 GCBZ 之前加载了能提供 GCBZ 的配置（如果需要）
        self._load_rock_soil_types()
        print("系统配置加载完毕。")

    def _load_ziduan_definitions(self):
        # ... (代码无变化) ...
        data = self.db_manager.get_table_data("g_ZiDuan", db_type="config",
                                              columns="ZDMC, ZDMS, ZDTYPE, ZDMR, ZDSHOW")
        if data:
            for row in data:
                if len(row) >= 3:
                    zdmc, zdms, zdtype = row[0], row[1], row[2]
                    default_val = row[3] if len(row) > 3 else None
                    show_flag = row[4] if len(row) > 4 else '1'
                    if zdmc:
                        self.ziduan_definitions[zdmc] = {
                            "ZDMS": zdms,
                            "ZDTYPE": zdtype,
                            "ZDMR": default_val,
                            "ZDSHOW": show_flag
                        }

        print(f"加载字段定义: {len(self.ziduan_definitions)} 条")

    def _load_table_configs(self):
        # ... (代码无变化) ...
        # g_PeiZhi 表用于配置模块行为，PZGN 对应表名或模块名 [cite: 32]
        data = self.db_manager.get_table_data("g_PeiZhi", db_type="config",
                                              columns="PZGN, PZYM, PZCD, GJZ, PZBX, PZYMALL")
        if data:
            for row in data:
                if len(row) >= 2 and row[0]:
                    pzgn, pzym = row[0], row[1]
                    pzcd = row[2] if len(row) > 2 else ""
                    gjz = row[3] if len(row) > 3 else ""
                    pzbx = row[4] if len(row) > 4 else ""
                    pzymall = row[5] if len(row) > 5 else "" # PZYMALL 包含所有关联字段 [cite: 32]
                    self.table_configs[pzgn] = {
                        "PZYM": pzym.split(',') if pzym else [],
                        "PZCD": pzcd.split(',') if pzcd else [],
                        "GJZ": gjz.split(',') if gjz else [],
                        "PZBX": pzbx.split(',') if pzbx else [],
                        "PZYMALL": pzymall.split(',') if pzymall else []
                    }
        print(f"加载表单配置: {len(self.table_configs)} 条")

    def _load_dropdown_options(self):
        # ... (代码无变化) ...
        # g_DuiZhao 提供下拉选项 [cite: 31]
        data = self.db_manager.get_table_data("g_DuiZhao", db_type="config", columns="XMDH, DZBH, DZMC")
        if data:
            for row in data:
                if len(row) >= 3 and row[0]:
                    xmdh, dzbh, dzmc = row[0], row[1], row[2]
                    if xmdh not in self.dropdown_options:
                        self.dropdown_options[xmdh] = []
                    self.dropdown_options[xmdh].append({"code": dzbh, "name": dzmc})
        print(f"加载下拉选项: {len(self.dropdown_options)} 类")

    def _load_project_tree_structure(self):
        current_gcbz_num = self.get_current_standard_gcbz_numeric()
        columns_to_fetch = "GCBZ, ID, t_parentID, t_parenttable, t_parentField, t_ID, t_table, t_field, t_expand, t_state, t_type, t_nodepath"
        column_names = [col.strip() for col in columns_to_fetch.split(',')]

        final_nodes_map = {}  # 使用字典以ID为主键，确保唯一性并实现优先级

        # 1. 首先加载特定规范的节点 (current_gcbz_num)
        if current_gcbz_num != 0 and current_gcbz_num != -1:  # 避免重复查询通用配置
            condition_specific = f"([GCBZ] = {current_gcbz_num})"
            print(
                f"尝试加载特定导航树 (GCBZ={current_gcbz_num}): SELECT {columns_to_fetch} FROM [{self.project_tree_config_name}] WHERE {condition_specific}")
            data_specific = self.db_manager.get_table_data(
                self.project_tree_config_name,
                db_type="config",
                columns=columns_to_fetch,
                condition=condition_specific
            )
            if data_specific:
                for row_tuple in data_specific:
                    if len(row_tuple) == len(column_names):
                        node_dict = dict(zip(column_names, row_tuple))
                        final_nodes_map[node_dict['ID']] = node_dict  # 特定规范的节点优先
                    else:
                        print(
                            f"警告 (特定导航树加载): 列数不匹配。期望 {len(column_names)}, 得到 {len(row_tuple)}。数据: {row_tuple}")

        # 2. 接着加载通用规范的节点 (GCBZ = 0 或 GCBZ = -1)
        #    仅当节点ID未被特定规范加载时才添加
        condition_generic = "([GCBZ] = 0 OR [GCBZ] = -1)"
        print(
            f"尝试加载通用导航树 (GCBZ=0 or -1): SELECT {columns_to_fetch} FROM [{self.project_tree_config_name}] WHERE {condition_generic}")
        data_generic = self.db_manager.get_table_data(
            self.project_tree_config_name,
            db_type="config",
            columns=columns_to_fetch,
            condition=condition_generic
        )
        if data_generic:
            for row_tuple in data_generic:
                if len(row_tuple) == len(column_names):
                    node_dict = dict(zip(column_names, row_tuple))
                    if node_dict['ID'] not in final_nodes_map:  # 如果ID不存在于已加载的特定节点中
                        final_nodes_map[node_dict['ID']] = node_dict
                else:
                    print(
                        f"警告 (通用导航树加载): 列数不匹配。期望 {len(column_names)}, 得到 {len(row_tuple)}。数据: {row_tuple}")

        self.project_tree_raw_nodes = list(final_nodes_map.values())

        if self.project_tree_raw_nodes:
            print(f"加载导航树结构完成，共 {len(self.project_tree_raw_nodes)} 个去重后节点。")
            # print("导航树原始节点示例 (前1条):", [self.project_tree_raw_nodes[0]] if self.project_tree_raw_nodes else "无")
        else:
            print(f"警告: 未能从表 '{self.project_tree_config_name}' 加载到任何导航树节点数据。")

        print(f"ConfigLoader: Final project_tree_raw_nodes (count: {len(self.project_tree_raw_nodes)}):")
        for node in self.project_tree_raw_nodes:
            print(
                f"  ID: {node.get('ID')}, t_parentID: {node.get('t_parentID')}, t_field: {node.get('t_field')}, GCBZ: {node.get('GCBZ')}")
    def get_project_tree_raw_nodes(self):
        return self.project_tree_raw_nodes

    def _load_rock_soil_types(self):
        # ... (代码无变化) ...
        # g_YanXing_all 定义岩土类型 [cite: 31]
        rock_data = self.db_manager.get_table_data("g_YanXing_all", db_type="config",
                                                   columns="YTMC, YTLB, YTTL, YTQYS, YTBYS")
        if rock_data:
            for row in rock_data:
                if len(row) >= 3 and row[0]:
                    self.rock_soil_types.append({
                        "name": row[0],
                        "category": row[1],
                        "symbol": row[2],
                        "fg_color": row[3] if len(row) > 3 else None,
                        "bg_color": row[4] if len(row) > 4 else None
                    })
        print(f"加载岩土类型: {len(self.rock_soil_types)} 条")

    def get_current_standard_gcbz(self):
        data = self.db_manager.get_table_data("CFGCurZXBZ", db_type="config", columns="ZXBZ")
        if data and data[0] and data[0][0] is not None:
            return str(data[0][0])
        return "0"

    def get_ziduan_definition(self, zdmc):
        return self.ziduan_definitions.get(zdmc)

    def get_table_config(self, pzgn):
        return self.table_configs.get(pzgn)

    def get_dropdown_options(self, xmdh):
        return self.dropdown_options.get(xmdh, [])

    # get_project_tree_nodes 方法已移除，因为MainWindow直接使用get_project_tree_raw_nodes
    # def get_project_tree_nodes(self):
    #     return self.project_tree_structure

    def get_rock_soil_list(self):
        return self.rock_soil_types


if __name__ == '__main__':
    db_mngr = DBManager()
    if db_mngr.config_conn:
        cfg_loader = ConfigLoader(db_mngr)
        # 测试获取某个字段定义
        zkbh_def = cfg_loader.get_ziduan_definition("ZKBH")
        if zkbh_def:
            print(f"\n字段 ZKBH 定义: {zkbh_def['ZDMS']} (类型: {zkbh_def['ZDTYPE']})")

        # 测试获取某个表配置
        tuceng_cfg = cfg_loader.get_table_config("z_g_TuCeng")  # 假设这是PZGN
        if tuceng_cfg:
            print(f"\n表 z_g_TuCeng 显示字段: {tuceng_cfg['PZYM']}")

        # 测试获取下拉选项
        ktlx_options = cfg_loader.get_dropdown_options("KTLX")  # 勘探点类型
        if ktlx_options:
            print(f"\n勘探点类型选项 (前3条): {ktlx_options[:3]}")

        rock_list = cfg_loader.get_rock_soil_list()
        if rock_list:
            print(f"\n岩土类型 (前3条): {rock_list[:3]}")

        print(f"\n当前执行标准GCBZ: {cfg_loader.get_current_standard_gcbz()}")