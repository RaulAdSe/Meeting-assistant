import os
import psycopg2
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path
import logging

class DatabaseConnection:
    _instance: Optional['DatabaseConnection'] = None
    
    @classmethod
    def get_instance(cls) -> 'DatabaseConnection':
        if cls._instance is None:
            cls._instance = DatabaseConnection()
        return cls._instance
    
    def __init__(self):
        # Load environment variables from project root
        env_path = Path(__file__).parent.parent.parent.parent / '.env'
        load_dotenv(env_path)
        
        logging.getLogger("psycopg2").setLevel(logging.ERROR)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.WARNING)

        self.instance_connection_name = os.getenv('INSTANCE_CONNECTION_NAME')
        self.db_user = os.getenv('DB_USER', 'postgres')
        self.db_pass = os.getenv('DB_PASSWORD')
        self.db_name = os.getenv('DB_NAME', 'MeetingAssistant')
        
    def get_connection(self):
        try:
            # Check if running on Cloud Run
            if os.getenv('K_SERVICE'):
                host = f'/cloudsql/{self.instance_connection_name}'
            else:
                host = os.getenv('DB_HOST', '34.175.111.125')
                
            
            conn = psycopg2.connect(
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_pass,
                host=host
            )
            #print("Database connection successful")
            return conn
            
        except Exception as e:
            print(f"Database connection error: {str(e)}")
            print("\nConnection details:")
            print(f"- Running on Cloud Run: {os.getenv('K_SERVICE') is not None}")
            print(f"- INSTANCE_CONNECTION_NAME: {self.instance_connection_name}")
            print(f"- DB_HOST: {os.getenv('DB_HOST')}")
            print(f"- DB_NAME: {self.db_name}")
            print(f"- DB_USER: {self.db_user}")
            raise