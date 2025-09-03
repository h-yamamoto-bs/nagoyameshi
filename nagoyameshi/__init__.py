try:
	import pymysql  # type: ignore
	pymysql.install_as_MySQLdb()
except Exception:
	# mysqlclient (MySQLdb) が入っていればそちらが使われる。未インストール時のみPyMySQLをMySQLdbとして登録。
	pass
import pymysql

pymysql.install_as_MySQLdb()