# YuGeoTech_Project/core/field_mapper.py

class FieldMapper:
    def __init__(self, config_loader):
        self.config_loader = config_loader
        # ZDMC (db_name) -> ZDMS (ui_name)
        self.db_to_ui_map = {}
        # ZDMS (ui_name) -> ZDMC (db_name)
        # 注意：ZDMS可能不唯一，以此作为键需要谨慎，或确保ZDMS在特定上下文唯一
        self.ui_to_db_map = {}
        self._build_maps()

    def _build_maps(self):
        """从ConfigLoader加载的字段定义构建映射"""
        ziduan_defs = self.config_loader.ziduan_definitions # 这是个字典 ZDMC -> details
        if not ziduan_defs:
            print("警告 (FieldMapper): 字段定义为空，无法构建映射。")
            return

        for zdmc, details in ziduan_defs.items():
            zdms = details.get("ZDMS")
            if zdmc and zdms:
                self.db_to_ui_map[zdmc] = zdms
                if zdms not in self.ui_to_db_map: # 防止因ZDMS不唯一导致覆盖
                    self.ui_to_db_map[zdms] = zdmc
                # else:
                #     print(f"警告 (FieldMapper): UI名称 '{zdms}' 重复，已映射到 '{self.ui_to_db_map[zdms]}', 将忽略新的ZDMC '{zdmc}'")
        # print(f"字段映射构建完成: {len(self.db_to_ui_map)} 条DB->UI映射, {len(self.ui_to_db_map)} 条UI->DB映射。")


    def get_ui_name(self, db_name, default_to_db_name=True):
        """根据数据库字段名获取UI显示名称"""
        name = self.db_to_ui_map.get(db_name)
        if name is None and default_to_db_name:
            return db_name
        return name

    def get_db_name(self, ui_name, default_to_ui_name=True):
        """根据UI显示名称获取数据库字段名 (需谨慎使用，UI名可能不唯一)"""
        name = self.ui_to_db_map.get(ui_name)
        if name is None and default_to_ui_name:
            return ui_name
        return name

if __name__ == '__main__':
    # 需要先有 DBManager 和 ConfigLoader 的实例
    db_mngr = DBManagerDBManager()
    if db_mngr.config_conn:
        cfg_loader = ConfigLoader(db_mngr)
        fld_mapper = FieldMapper(cfg_loader)

        db_field = "ZKBH"
        ui_field = fld_mapper.get_ui_name(db_field)
        print(f"\n数据库字段 '{db_field}' -> UI名称: '{ui_field}'")

        ui_field_example = "钻孔编号" # 假设这个中文名存在于 g_ZiDuan.ZDMS
        db_field_mapped = fld_mapper.get_db_name(ui_field_example)
        print(f"UI名称 '{ui_field_example}' -> 数据库字段: '{db_field_mapped}'")

        db_field_not_exist = "NON_EXISTENT_DB_FIELD"
        ui_field_not_exist = fld_mapper.get_ui_name(db_field_not_exist)
        print(f"数据库字段 '{db_field_not_exist}' -> UI名称: '{ui_field_not_exist}' (应为原名)")