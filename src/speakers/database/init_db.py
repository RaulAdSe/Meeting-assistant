import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from src.speakers.database.connection import DatabaseConnection
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    # Load environment variables
    load_dotenv(project_root / '.env')
    
    # Get database connection
    db = DatabaseConnection.get_instance()
    conn = db.get_connection()
    
    try:
        with conn.cursor() as cur:
            # Read and execute schema
            schema_path = Path(__file__).parent / 'schema.sql'
            schema_sql = schema_path.read_text()
            
            logger.info("Creating database schema...")
            cur.execute(schema_sql)
            
            conn.commit()
            logger.info("Database schema created successfully")
            
    except Exception as e:
        logger.error(f"Error creating database schema: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    init_database()