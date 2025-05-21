# YuGeoTech_Project/core/project_handler.py
import os
import shutil
# import uuid # 不再使用uuid生成GCSY
import time  # 用于生成基于时间的数字GCSY
from datetime import datetime
from PySide6.QtWidgets import QMessageBox  # 移到顶部或在需要时导入
# DBManager 需要从同一目录或可访问路径导入
from .db_manager import DBManager # 假设db_manager.py在同一目录下或core包内
# 假设空工程模板路径
EMPTY_PROJECT_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'templates',
                                           'empty_project_template.mdb')


class ProjectHandler:
    def __init__(self, db_manager, workspace_dir):
        self.db_manager = db_manager
        self.workspace_dir = workspace_dir
        self.current_project_path = None
        self.current_project_gcsy = None
        os.makedirs(self.workspace_dir, exist_ok=True)

        # 用于生成唯一的数字 GCSY (简单实现)
        # 您可能需要一个更健壮的机制，例如从配置文件或小型数据库读取和更新
        self.last_gcsy_counter_file = os.path.join(workspace_dir, "_internal_gcsy_counter.txt")
        self._initialize_gcsy_counter()

    def _initialize_gcsy_counter(self):
        if not os.path.exists(self.last_gcsy_counter_file):
            with open(self.last_gcsy_counter_file, "w") as f:
                f.write(str(int(time.time())))  # 使用当前时间戳作为初始值

    def _get_next_numeric_gcsy(self):
        """获取下一个唯一的数字GCSY (简单实现)"""
        try:
            with open(self.last_gcsy_counter_file, "r+") as f:
                current_val = int(f.read().strip())
                next_val = current_val + 1
                f.seek(0)
                f.write(str(next_val))
                f.truncate()
                return next_val
        except Exception as e:
            print(f"警告: 获取数字GCSY失败 ({e})，将使用基于时间戳的GCSY。")
            # 回退方案，如果文件操作失败
            return int(time.time() * 1000)  # 毫秒级，增加唯一性机会

    def create_new_project(self, project_base_info):
        gcbh = project_base_info.get("GCBH", f"Proj_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        gcmc = project_base_info.get("GCMC", "未命名工程")

        project_folder = os.path.join(self.workspace_dir, gcbh)
        os.makedirs(project_folder, exist_ok=True)

        project_mdb_name = f"{gcbh}_{gcmc}.mdb".replace(" ", "_").replace(":", "-")  # 进一步清理文件名
        new_project_db_path = os.path.join(project_folder, project_mdb_name)

        if os.path.exists(new_project_db_path):
            print(f"错误：工程文件 {new_project_db_path} 已存在。")
            QMessageBox.warning(None, "创建失败", f"工程文件 {project_mdb_name} 已存在于目录 {project_folder}。")
            return None

        if not os.path.exists(EMPTY_PROJECT_TEMPLATE_PATH):
            print(f"错误：空工程模板 '{EMPTY_PROJECT_TEMPLATE_PATH}' 未找到。无法创建新工程。")
            QMessageBox.critical(None, "严重错误", f"空工程模板文件未找到：\n{EMPTY_PROJECT_TEMPLATE_PATH}")
            return None

        try:
            shutil.copy(EMPTY_PROJECT_TEMPLATE_PATH, new_project_db_path)
            print(f"新工程文件已创建: {new_project_db_path}")
        except Exception as e:
            print(f"复制模板文件失败: {e}")
            QMessageBox.critical(None, "创建失败", f"复制工程模板时出错: {e}")
            return None

        if not self.db_manager.connect_project_db(new_project_db_path):
            print("错误：创建工程后无法连接到新的工程数据库。")
            QMessageBox.critical(None, "创建失败", "无法连接到新创建的工程数据库。")
            try:
                os.remove(new_project_db_path)
                print(f"已删除未成功连接的工程文件: {new_project_db_path}")
            except Exception as del_e:
                print(f"删除未成功连接的工程文件失败: {del_e}")
            return None

        try:
            # gcsy = str(uuid.uuid4()) # 改为获取数字GCSY
            gcsy_numeric = self._get_next_numeric_gcsy()  # 获取数字 GCSY

            columns = ["GCSY", "GCBH", "GCMC", "GCKCJD", "GCBZ", "GCPATH",
                       "GCZBX", "GCGCX", "SPGJYLJB", "SXGJYLJB"]

            # 确保为数字类型的字段提供数字，为文本类型的字段提供文本
            gcbz_str = project_base_info.get("GCBZ", "0")
            try:
                gcbz_numeric = int(gcbz_str)  # GCBZ 必须是数字
            except ValueError:
                print(f"警告: GCBZ 值 '{gcbz_str}' 无法转换为整数，将使用默认值 0。")
                gcbz_numeric = 0

            values_list = [
                gcsy_numeric,  # 数字 GCSY
                str(project_base_info.get("GCBH", gcbh)),
                str(project_base_info.get("GCMC", gcmc)),
                str(project_base_info.get("GCKCJD", "详细勘察")),
                gcbz_numeric,  # 数字 GCBZ
                str(project_folder),
                str(project_base_info.get("GCZBX", "2000国家大地坐标系")),
                str(project_base_info.get("GCGCX", "1985国家高程基准")),
                str(project_base_info.get("SPGJYLJB", "100,200,400,800")),  # 这些是文本
                str(project_base_info.get("SXGJYLJB", "100,200,400,800"))  # 这些是文本
            ]

            if len(values_list) != len(columns):
                QMessageBox.critical(None, "内部错误", "插入x_GongCheng表时列数与值的数量不匹配。")
                raise Exception("列数与值的数量不匹配。")

            placeholders = ','.join(['?'] * len(columns))
            insert_query = f"INSERT INTO [x_GongCheng] ([{'], ['.join(columns)}]) VALUES ({placeholders})"

            print(f"尝试插入 x_GongCheng: {insert_query} 参数: {tuple(values_list)}")  # 打印详细信息

            if self.db_manager.execute_query(insert_query, tuple(values_list), db_type="project"):
                print(f"工程信息已存入 x_GongCheng 表，GCSY: {gcsy_numeric}")
                self.current_project_path = new_project_db_path
                self.current_project_gcsy = gcsy_numeric  # 存储数字 GCSY
                return new_project_db_path, gcsy_numeric
            else:
                # execute_query 内部已经打印了详细的错误信息
                raise Exception("无法将工程信息存入 x_GongCheng 表 (execute_query 返回 False)。")

        except Exception as e:
            print(f"错误：在初始化新工程数据时发生错误: {e}")
            QMessageBox.critical(None, "创建失败", f"初始化工程数据时出错: {str(e)}")
            self.db_manager.close_project_db()
            try:
                # 延迟一小段时间再尝试删除，给连接释放留出更多时间
                time.sleep(0.5)
                os.remove(new_project_db_path)
                print(f"已删除未成功初始化的工程文件: {new_project_db_path}")
            except Exception as del_e:
                print(f"删除未成功初始化的工程文件 '{new_project_db_path}' 失败: {del_e}")
            return None

    def open_project(self, project_db_path):
        """打开现有工程"""
        if self.db_manager.connect_project_db(project_db_path):
            self.current_project_path = project_db_path
            gcsy_data = self.db_manager.get_table_data("x_GongCheng", db_type="project", columns="GCSY")
            if gcsy_data and len(gcsy_data) > 0 and gcsy_data[0] and gcsy_data[0][0] is not None:
                self.current_project_gcsy = gcsy_data[0][0]  # GCSY 直接是数字
                print(
                    f"工程已打开: {project_db_path}, GCSY: {self.current_project_gcsy} (类型: {type(self.current_project_gcsy)})")
                return True
            else:
                print(f"警告: 无法从 {project_db_path} 的 x_GongCheng 表获取 GCSY。")
                QMessageBox.warning(None, "打开警告",
                                    f"无法从工程文件 {os.path.basename(project_db_path)} 的 x_GongCheng 表中读取有效的GCSY。")
                self.current_project_gcsy = None
                # 即使没有GCSY，也可能允许打开，但功能会受限
                return True  # 或者 return False 如果GCSY是绝对必须的
        return False

    def close_current_project(self):
        """关闭当前活动的工程数据库连接并重置状态"""
        if self.db_manager:
            self.db_manager.close_project_db()  # 调用 DBManager 关闭实际连接

        # 重置 ProjectHandler 内部关于当前工程的状态
        self.current_project_path = None
        self.current_project_gcsy = None
        print("当前工程已由 ProjectHandler 关闭。")

    # --- 方法添加结束 ---

    def get_current_project_gcsy(self):
        return self.current_project_gcsy

    def get_current_project_path(self):
        return self.current_project_path

    def import_data_from_project(self, source_mdb_path):
        if not self.current_project_path or self.current_project_gcsy is None:
            return False, "目标工程未打开，无法导入数据。"

        source_db_manager = DBManager()
        if not source_db_manager.connect_project_db(source_mdb_path):
            return False, f"无法连接到源工程数据库: {source_mdb_path}"

        source_gcsy_rows = source_db_manager.get_table_data("x_GongCheng", db_type="project", columns="GCSY")
        if not source_gcsy_rows or not source_gcsy_rows[0] or source_gcsy_rows[0][0] is None:
            source_db_manager.close_project_db()
            return False, "无法从源工程的 x_GongCheng 表获取其 GCSY。"
        source_original_gcsy = source_gcsy_rows[0][0]
        target_gcsy_to_use = self.current_project_gcsy

        print(f"准备从源工程 (原GCSY: {source_original_gcsy}) 导入数据到目标工程 (GCSY: {target_gcsy_to_use})")

        # 核心业务数据表，根据您的文档分析进行扩展和确认
        # 主键 'pk_cols' 必须准确，特别是对于包含 GCSY 的表
        # 顺序建议：父表在前，子表在后
        tables_to_import_info = [  # 改为列表以控制顺序
            ("z_ZuanKong", {"pk_cols": ["GCSY", "ZKBH"]}),
            ("z_g_TuCeng", {"pk_cols": ["GCSY", "ZKBH", "TCXH"]}),  # 土层表 [cite: 2, 110]
            ("z_c_QuYang", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}),  # 取样表 [cite: 3, 112]
            # 原位测试
            ("z_y_BiaoGuan", {"pk_cols": ["GCSY", "ZKBH", "BGDSDTOP"]}),  # 标贯 [cite: 4, 114]
            ("z_y_DongTan", {"pk_cols": ["GCSY", "ZKBH", "DTDSDTOP"]}),  # 动探 [cite: 4, 114]
            ("z_y_JingTan", {"pk_cols": ["GCSY", "ZKBH", "JTDSD"]}),  # 静探，假设JTDSD是关键深度 [cite: 8, 114]
            ("z_y_JingTanSQ", {"pk_cols": ["GCSY", "ZKBH", "JTDSD"]}),  # 双桥静探 [cite: 16, 114]
            ("z_y_YeHuaJT", {"pk_cols": ["GCSY", "ZKBH", "TuCBH", "PBSD"]}),  # 液化判别-静探 [cite: 5, 114] (主键需确认)
            ("t_y_YingLiChan", {"pk_cols": ["GCSY", "ZKBH", "ID"]}), # 应力铲 [cite: 28, 114]
            # ... (其他 z_y_* 原位测试表，如旁压、波速)

            # 室内试验 (通常依赖 z_c_QuYang)
            ("z_c_KeFen", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}),  # 颗粒分析，假设QYBH是主键一部分 [cite: 13, 113]
            ("z_c_GuJie", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}),  # 固结试验 [cite: 6, 113]
            ("z_c_SanZhou", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}),  # 三轴试验 [cite: 13, 113]
            ("z_c_ZhiJian", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}),  # 直剪试验 [cite: 8, 113]
            ("t_YanShi", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}),  # 岩石试验 [cite: 7, 113]
            ("t_YiRongYan", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}),  # 易溶盐 [cite: 19, 113]
            ("t_ShuiZhiJianFX", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}),  # 水质简分析 [cite: 19, 113]
            ("z_c_PengZhangTu", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}),  # 膨胀土 [cite: 9, 113]
            # ("t_BengJie", {"pk_cols": ["GCSY", "ZKBH", "QYBH"]}), # 崩解试验，需确认主键 [cite: 27, 113]

            # 水文地质
            ("z_g_ShuiWei", {"pk_cols": ["GCSY", "ZKBH", "XH"]}),  # 地下水位 [cite: 10, 115]
            ("t_YaShuiSY", {"pk_cols": ["GCSY", "ZKBH", "SYBH"]}), # 压水试验成果 [cite: 20, 115]
            ("t_YaShuiSYJL", {"pk_cols": ["GCSY", "ZKBH", "SYBH", "YLJD", "TIME_H", "TIME_M"]}), # 压水记录 (主键复杂) [cite: 9, 115]
            ("t_YaShuiSYSWJL", {"pk_cols": ["GCSY", "ZKBH", "SYBH", "TIME_H", "TIME_M"]}), # 压水水位记录 [cite: 17, 115]
            ("z_y_ChouShui", {"pk_cols": ["GCSY", "ZKBH", "SYBH"]}), # 抽水基本信息 [cite: 20, 115]
            ("z_y_ChouShuiSJ", {"pk_cols": ["GCSY", "ZKBH", "LCCS"]}),# 抽水数据记录 [cite: 23, 115]
            ("z_y_ChouShuiSWHF", {"pk_cols": ["GCSY", "ZKBH", "HFSJ"]}),# 抽水水位恢复 [cite: 23, 115]
            ("z_y_ZhuShui", {"pk_cols": ["GCSY", "ZKBH", "ZSXH"]}),   # 注水试验 [cite: 23, 115]

            # 工程绘图与成果 (部分可能不需要直接导入，或导入逻辑特殊)
            ("g_STuCengGC", {"pk_cols": ["GCSY", "TCZCBH", "TCYCBH", "TCCYCBH"]}),  # 工程标准地层 [cite: 14, 111]
            ("x_DiCeng", {"pk_cols": ["GCSY", "ZCBH", "YCBH", "CYCBH"]}),  # 地层参数汇总 [cite: 14, 117]
            # ("x_SheJi", {"pk_cols": ["GCSY", "ZCBH", "YCBH", "CYCBH", "TJTABLE", "TJFIELD"]}), # 设计参数统计 (主键复杂) [cite: 15, 117]
            # ("x_TuGong", {"pk_cols": ["GCSY", "ZCBH", "YCBH", "CYCBH"]}), # 土工试验汇总 [cite: 24, 117]
            # ("z_ZuanKong_Buf", {"pk_cols": ["GCSY", "ZKBH"]}), # 钻孔缓冲 [cite: 11, 117]
            ("p_PouXian", {"pk_cols": ["GCSY", "PXBH"]}),       # 剖面线定义 [cite: 15, 116]
            # ... 其他您认为需要导入的表，如 DCBHSJCon, g_JiChu 等
        ]

        imported_summary = []
        errors_occurred = []

        for table_name, table_info in tables_to_import_info:
            print(f"  正在处理表: {table_name}...")

            # 获取源表所有列名
            # 尝试用 TOP 1 获取列信息，如果表为空，则用 SELECT * 但不取数据
            source_cursor_desc_query = source_db_manager.project_cursor.execute(f"SELECT TOP 1 * FROM [{table_name}]")
            source_columns_data = source_cursor_desc_query.description

            if not source_columns_data:  # 如果表完全是空的，description可能是None
                # 尝试另一种方式获取列（如果需要，但通常MDB表即使空也有结构）
                # 或者如果确定所有表在模板中都有结构，可以从config_loader获取PZYMALL
                print(f"    无法获取源表 {table_name} 的列信息（可能是空表且驱动未返回列描述），跳过。")
                # errors_occurred.append(f"无法获取源表 {table_name} 列信息。")
                continue  # 或者尝试从配置加载列定义

            source_column_names = [desc[0] for desc in source_columns_data]
            if not source_column_names:
                print(f"    源表 {table_name} 列名为空，跳过。")
                continue

            select_cols_sql = ", ".join([f"[{col}]" for col in source_column_names])
            source_data_rows = source_db_manager.execute_query(
                f"SELECT {select_cols_sql} FROM [{table_name}] WHERE [GCSY] = ?",
                params=(source_original_gcsy,),
                db_type="project"
            )

            if source_data_rows is None:
                errors_occurred.append(f"读取源表 {table_name} 数据失败。")
                continue
            if not source_data_rows:
                print(f"    源表 {table_name} (GCSY={source_original_gcsy}) 中无数据。")
                continue

            insert_cols_sql = ", ".join([f"[{col}]" for col in source_column_names])
            placeholders = ", ".join(["?"] * len(source_column_names))
            insert_sql = f"INSERT INTO [{table_name}] ({insert_cols_sql}) VALUES ({placeholders})"

            successful_inserts = 0
            for row_tuple in source_data_rows:
                new_row_values = list(row_tuple)

                # 替换 GCSY
                try:
                    gcsy_col_index = source_column_names.index("GCSY")
                    new_row_values[gcsy_col_index] = target_gcsy_to_use
                except ValueError:
                    # 表中可能没有GCSY列（例如纯配置表，但不应出现在这里）
                    # 对于业务数据表，这通常是个问题，但我们按列表来，有些可能例外
                    pass

                    # 实现“覆盖”策略：先删除目标表中具有相同主键的记录
                pk_delete_conditions = []
                pk_delete_params = []
                can_build_pk_for_delete = True

                for pk_col_name in table_info["pk_cols"]:
                    try:
                        pk_col_idx = source_column_names.index(pk_col_name)
                        # 如果主键列是GCSY，用替换后的target_gcsy_to_use
                        pk_val = new_row_values[pk_col_idx] if pk_col_name != "GCSY" else target_gcsy_to_use

                        if pk_val is None and pk_col_name in table_info["pk_cols"]:  # 主键部分不应为None
                            print(
                                f"    警告: 表 {table_name}, 主键字段 {pk_col_name} 的值为 None，无法用于删除条件。跳过此行删除尝试。")
                            can_build_pk_for_delete = False
                            break
                        pk_delete_conditions.append(f"[{pk_col_name}] = ?")
                        pk_delete_params.append(pk_val)
                    except ValueError:  # 主键列名不在源数据列中
                        errors_occurred.append(f"主键列 {pk_col_name} 不在表 {table_name} 的源数据列中。")
                        can_build_pk_for_delete = False
                        break

                if not can_build_pk_for_delete:
                    errors_occurred.append(f"无法为表 {table_name} 构建删除条件，行: {row_tuple[:3]}")
                    continue  # 跳过此行的导入

                if pk_delete_conditions:
                    delete_sql = f"DELETE FROM [{table_name}] WHERE {' AND '.join(pk_delete_conditions)}"
                    # print(f"    尝试删除: {delete_sql} 参数: {tuple(pk_delete_params)}")
                    self.db_manager.execute_query(delete_sql, tuple(pk_delete_params), db_type="project")

                # 尝试插入新数据
                if self.db_manager.execute_query(insert_sql, tuple(new_row_values), db_type="project"):
                    successful_inserts += 1
                else:
                    errors_occurred.append(
                        f"插入数据到表 {table_name} 失败 (数据: {str(new_row_values[:3])[:100]}...)")

            print(f"    表 {table_name}: 尝试导入 {len(source_data_rows)} 条, 成功 {successful_inserts} 条。")
            if successful_inserts > 0:
                imported_summary.append(f"{table_name}: {successful_inserts} 条")

        source_db_manager.close_project_db()

        if errors_occurred:
            error_msg = "导入过程中发生以下错误：\n" + "\n".join(errors_occurred[:10])
            if len(errors_occurred) > 10: error_msg += f"\n...等共 {len(errors_occurred)} 条错误。"
            return False, error_msg
        elif not imported_summary:
            return True, "源工程中没有与指定GCSY相关的数据可导入，或所有相关表均为空。"
        else:
            return True, "数据导入尝试完成。\n汇总:\n" + "\n".join(imported_summary)