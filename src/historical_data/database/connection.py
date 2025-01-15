import os
import psycopg2
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path
import logging

# Enable UUID adaptation
class DatabaseConnection:
    _instance: Optional['DatabaseConnection'] = None
    
    @classmethod
    def get_instance(cls) -> 'DatabaseConnection':
        if cls._instance is None:
            cls._instance = DatabaseConnection()
        return cls._instance
    
    def __init__(self):
        # Load environment variables from project root
        env_path = Path(__file__).parent.parent.parent / '.env'
        load_dotenv(env_path)
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Database configuration
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_port = os.getenv('DB_PORT', '5432')
        self.db_name = os.getenv('DB_NAME', 'postgres')
        self.db_user = os.getenv('DB_USER', 'postgres')
        self.db_password = os.getenv('DB_PASSWORD', '')
        
    def get_connection(self): 
        """Create and return a database connection with UUID support"""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password
                )
            return conn
            
        except Exception as e:
            self.logger.error(f"Database connection error: {str(e)}")
            self.logger.error(f"Connection details: host={self.db_host}, "
                          f"port={self.db_port}, dbname={self.db_name}, "
                          f"user={self.db_user}")
            raise

    def execute_query(self, query: str, params: tuple = None):
        """Execute a query and return results"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:  # If the query returns data
                    return cur.fetchall()
                conn.commit()
                return None
        finally:
            conn.close()