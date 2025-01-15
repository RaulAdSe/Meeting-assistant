# tests/historical_data/test_uuid_handling.py

import pytest
import uuid
from datetime import datetime
from src.historical_data.database.location_repository import LocationRepository
from src.historical_data.models.models import Location
from src.batch_processing.processors.enhanced_batch_transcriber import EnhancedBatchTranscriber

@pytest.fixture
def location_repo():
    return LocationRepository()

@pytest.fixture
def batch_transcriber():
    return EnhancedBatchTranscriber()

class TestUUIDHandling:
    def test_to_uuid_conversion(self, location_repo):
        """Test UUID conversion with different input types"""
        # Test with string UUID
        uuid_str = "123e4567-e89b-12d3-a456-426614174000"
        result = location_repo._to_uuid(uuid_str)
        assert isinstance(result, uuid.UUID)
        assert str(result) == uuid_str

        # Test with existing UUID
        existing_uuid = uuid.uuid4()
        result = location_repo._to_uuid(existing_uuid)
        assert result == existing_uuid

        # Test with None
        result = location_repo._to_uuid(None)
        assert result is None

        # Test with invalid string
        result = location_repo._to_uuid("invalid-uuid")
        assert result is None

    def test_get_by_name_with_existing_location(self, location_repo):
        """Test retrieving location by name when it exists"""
        # First create a location
        test_name = "Test Location"
        created = location_repo.create(
            name=test_name,
            address="Test Address"
        )
        assert created is not None
        assert isinstance(created.id, uuid.UUID)

        # Now try to retrieve it
        retrieved = location_repo.get_by_name(test_name)
        assert retrieved is not None
        assert isinstance(retrieved.id, uuid.UUID)
        assert retrieved.name == test_name

    def test_location_creation_with_uuid(self, location_repo):
        """Test creating location and verifying UUID handling"""
        location = location_repo.create(
            name="New Location",
            address="New Address",
            metadata={"test": "data"}
        )
        
        assert location is not None
        assert isinstance(location.id, uuid.UUID)
        
        # Try to retrieve it using the UUID
        retrieved = location_repo.get(location.id)
        assert retrieved is not None
        assert retrieved.id == location.id

    def test_handle_location_with_string(self, batch_transcriber):
        """Test handling location with string input"""
        location = batch_transcriber._handle_location(location_name="Test Location")
        assert location is not None
        assert isinstance(location.id, uuid.UUID)
        assert location.name == "Test Location"

    def test_handle_location_with_uuid(self, batch_transcriber):
        """Test handling location with UUID input"""
        # First create a location to get a UUID
        initial_location = batch_transcriber._handle_location(location_name="UUID Test Location")
        assert initial_location is not None
        
        # Now try to handle it with the UUID
        location = batch_transcriber._handle_location(location_name=initial_location.id)
        assert location is not None
        assert isinstance(location.id, uuid.UUID)
        assert location.id == initial_location.id

    def test_handle_location_with_none(self, batch_transcriber):
        """Test handling location with None input"""
        location = batch_transcriber._handle_location(location_name=None)
        assert location is not None
        assert isinstance(location.id, uuid.UUID)
        assert location.name == "Default Construction Site"

    def test_handle_location_with_empty_string(self, batch_transcriber):
        """Test handling location with empty string input"""
        location = batch_transcriber._handle_location(location_name="")
        assert location is not None
        assert isinstance(location.id, uuid.UUID)
        assert location.name == "Default Construction Site"

    def test_handle_location_with_location_data(self, batch_transcriber):
        """Test handling location with location data input"""
        location_data = {
            'main_site': {
                'company': 'Test Company',
                'site': 'Test Site'
            }
        }
        
        location = batch_transcriber._handle_location(
            location_name=None,
            location_data=location_data
        )
        
        assert location is not None
        assert isinstance(location.id, uuid.UUID)
        assert location.name == "Test Company - Test Site"
