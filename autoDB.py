import pymssql
import logging
from typing import Optional, List, Dict, Any

class SQLQueryDirect:
    """
    Direct pymssql implementation without pandas
    """
    
    def __init__(self, server: str, database: str, username: str, password: str, port: int = 1433):
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.port = port
        self._connection: Optional[pymssql.Connection] = None

    def _get_connection(self) -> pymssql.Connection:
        """Create direct pymssql connection."""
        if self._connection is None:
            try:
                self._connection = pymssql.connect(
                    server=self.server,
                    database=self.database,
                    user=self.username,
                    password=self.password,
                    port=self.port
                )
                logging.info("✅ Direct connection to DB established successfully")
            except Exception as e:
                raise RuntimeError(f"Failed to create database connection: {e}") from e
        return self._connection

    def execute(self, query: str) -> List[Dict[str, Any]]:
        """Execute query and return results as list of dictionaries WITHOUT pandas."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description]
            
            # Convert to list of dictionaries
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            logging.info(f"✅ Query executed successfully. Retrieved {len(results)} rows.")
            return results
            
        except Exception as e:
            raise RuntimeError(f"Query execution failed: {e}") from e

    def execute_scalar(self, query: str) -> Any:
        """Execute query and return single value."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            raise RuntimeError(f"Query execution failed: {e}") from e

    def close(self) -> None:
        """Close the connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logging.info("🔌 Database connection closed.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Test the direct version
if __name__ == "__main__":
    pass