# YuGeoTech_Project/core/db_manager.py
import pyodbc
import os

# 假设 system_config.mdb 存放在项目下的 system_config_ref 文件夹中
SYSTEM_CONFIG_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'system_config_ref',
                                     'system_config.mdb')


class DBManager:
    def __init__(self):
        self.config_conn = None
        self.project_conn = None
        self.config_cursor = None
        self.project_cursor = None
        self._connect_config_db()

    def _get_connection_string(self, db_path):
        # 确保数据库文件存在
        if not os.path.exists(db_path):
            print(f"错误：数据库文件未找到 - {db_path}")
            return None
        return (
            r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
            rf'DBQ={db_path};'
        )

    def _connect_config_db(self):
        """连接到 system_config.mdb"""
        conn_str = self._get_connection_string(SYSTEM_CONFIG_DB_PATH)
        if conn_str:
            try:
                self.config_conn = pyodbc.connect(conn_str)
                self.config_cursor = self.config_conn.cursor()
                print("成功连接到 system_config.mdb")
            except pyodbc.Error as ex:
                sqlstate = ex.args[0]
                print(f"连接 system_config.mdb 失败: {sqlstate}")
                print(
                    f"请确保 SYSTEM_CONFIG_DB_PATH ('{SYSTEM_CONFIG_DB_PATH}') 正确，并已安装 Microsoft Access Database Engine。")
        else:
            print("无法获取 system_config.mdb 的连接字符串。")

    def connect_project_db(self, project_db_path):
        """连接到指定的工程数据库 (.mdb 文件)"""
        if self.project_conn:
            self.close_project_db()  # 关闭上一个工程连接

        conn_str = self._get_connection_string(project_db_path)
        if conn_str:
            try:
                self.project_conn = pyodbc.connect(conn_str)
                self.project_cursor = self.project_conn.cursor()
                print(f"成功连接到工程数据库: {project_db_path}")
                return True
            except pyodbc.Error as ex:
                sqlstate = ex.args[0]
                print(f"连接工程数据库 {project_db_path} 失败: {sqlstate}")
                return False
        return False

    def close_project_db(self):
        """关闭当前工程数据库连接"""
        if self.project_cursor:
            self.project_cursor.close()
            self.project_cursor = None
        if self.project_conn:
            self.project_conn.close()
            self.project_conn = None
        print("工程数据库连接已关闭")

    def execute_query(self, query, params=None, db_type="config"):
        """
        执行查询语句
        :param query: SQL 查询语句
        :param params: 查询参数 (元组)
        :param db_type: "config" 或 "project"
        :return: 查询结果 (列表形式的元组) 或 None
        """
        cursor = self.config_cursor if db_type == "config" else self.project_cursor
        if not cursor:
            print(f"错误: {db_type} 数据库未连接或游标无效。")
            return None
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # 对于 SELECT 语句，获取结果
            if query.strip().upper().startswith("SELECT"):
                try:
                    # 尝试获取列名 (如果需要的话)
                    # columns = [column[0] for column in cursor.description]
                    return cursor.fetchall()
                except pyodbc.ProgrammingError:  # 例如，如果查询不是SELECT或者没有结果
                    return []  # 或者根据情况返回None
            else:  # 对于 INSERT, UPDATE, DELETE 等操作
                if db_type == "project":  # 通常只在项目数据库中执行写操作
                    self.project_conn.commit()
                elif db_type == "config" and not query.strip().upper().startswith("SELECT"):
                    print("警告：尝试对 system_config.mdb 执行写操作。")
                    # self.config_conn.commit() # 通常配置库是只读的
                return True  # 表示执行成功
        except pyodbc.Error as ex:
            sqlstate = ex.args[0]
            print(f"执行查询失败 ({db_type} DB): {sqlstate} - 查询: {query} - 参数: {params}")
            return None

    def get_table_data(self, table_name, db_type="config", columns="*", condition=""):
        """获取指定表的数据"""
        query = f"SELECT {columns} FROM [{table_name}]"  # MDB表名可能需要方括号
        if condition:
            query += f" WHERE {condition}"
        return self.execute_query(query, db_type=db_type)

    def __del__(self):
        """确保在对象销毁时关闭连接"""
        if self.config_cursor:
            self.config_cursor.close()
        if self.config_conn:
            self.config_conn.close()
        self.close_project_db()


if __name__ == '__main__':
    # 测试 DBManager
    db_manager = DBManager()
    if db_manager.config_conn:
        print("\n测试从 system_config.mdb 读取 g_ZiDuan 表 (前5条):")
        # 假设 g_ZiDuan 是一个表名，您需要根据实际的 .mdb 内容替换
        # 注意：JSON文件中的表名与MDB中的实际表名可能需要确认
        # 例如，如果JSON文件是 g_ZiDuan.json，MDB中表名可能是 g_ZiDuan
        ziduan_data = db_manager.get_table_data("g_ZiDuan", db_type="config")
        if ziduan_data:
            for i, row in enumerate(ziduan_data):
                if i < 5:
                    print(row)
                else:
                    break
        else:
            print("未能读取到 g_ZiDuan 数据或表不存在。")

    # 测试连接一个示例工程数据库 (您需要创建一个空的 test_project.mdb 或使用一个 LZGICAD1.mdb 的副本)
    # current_dir = os.path.dirname(__file__)
    # test_project_path = os.path.join(current_dir, '..', 'workspace', 'TestProject', 'TestProject.mdb')
    # os.makedirs(os.path.join(current_dir, '..', 'workspace', 'TestProject'), exist_ok=True)
    # # 你需要手动创建一个空的 TestProject.mdb 或者复制一个模板工程MDB到该路径
    # if not os.path.exists(test_project_path):
    #     print(f"请创建测试工程文件: {test_project_path}")
    # elif db_manager.connect_project_db(test_project_path):
    #     print("\n测试从工程数据库读取 x_GongCheng 表:")
    #     # 假设 x_GongCheng 是工程库中的一个表名
    #     gongcheng_data = db_manager.get_table_data("x_GongCheng", db_type="project")
    #     if gongcheng_data:
    #         for row in gongcheng_data:
    #             print(row)
    #     else:
    #         print("未能读取到 x_GongCheng 数据或表不存在。")
    #     db_manager.close_project_db()