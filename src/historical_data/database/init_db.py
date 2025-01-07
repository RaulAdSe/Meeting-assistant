#!/usr/bin/env python3
# src/historical_data/database/init_db.py

import sys
from pathlib import Path
import logging

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from src.speakers.database.connection import DatabaseConnection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_historical_database():
    """Initialize the historical data database schema."""
    db = DatabaseConnection.get_instance()
    conn = db.get_connection()
    
    try:
        with conn.cursor() as cur:
            # Read schema file
            schema_path = Path(__file__).parent / 'schema.sql'
            schema_sql = schema_path.read_text()
            
            logger.info("Creating historical data schema...")
            # Execute the entire schema as one statement
            cur.execute(schema_sql)
            
            conn.commit()
            logger.info("Historical data schema created successfully")
            
    except Exception as e:
        logger.error(f"Error creating historical data schema: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    init_historical_database()