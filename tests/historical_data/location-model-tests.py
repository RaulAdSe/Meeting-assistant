# tests/historical_data/test_location_model.py

import pytest
import uuid
from datetime import datetime
from src.historical_data.models.models import Location

class TestLocationModel:
    def test_location_creation_with_string_uuid(self):
        """Test creating location with string UUID"""
        uuid_str = "123e4567-e89b-12d3-a456-426614174000"
        location = Location(
            id=uuid_str,
            name="Test Location",
            address="Test Address"
        )
        assert isinstance(location.id, uuid.UUID)
        assert str(location.id) == uuid_str

    def test_location_creation_with_uuid(self):
        """Test creating location with UUID object"""
        location_id = uuid.uuid4()
        location = Location(
            id=location_id,
            name="Test Location",
            address="Test Address"
        )
        assert location.id == location_id
        assert isinstance(location.id, uuid.UUID)

    def test_location_creation_with_invalid_uuid(self):
        """Test creating location with invalid UUID"""
        with pytest.raises(ValueError):
            Location(
                id="invalid-uuid",
                name="Test Location",
                address="Test Address"
            )

    def test_location_with_metadata(self):
        """Test location with metadata"""
        metadata = {
            "created_by": "test_user",
            "company": "test_company"
        }
        location = Location(
            id=uuid.uuid4(),
            name="Test Location",
            address="Test Address",
            metadata=metadata
        )
        assert location.metadata == metadata

    def test_location_timestamps(self):
        """Test location timestamps"""
        now = datetime.now()
        location = Location(
            id=uuid.uuid4(),
            name="Test Location",
            address="Test Address",
            created_at=now,
            updated_at=now
        )
        assert location.created_at == now
        assert location.updated_at == now

    def test_location_optional_fields(self):
        """Test location with optional fields"""
        location = Location(
            id=uuid.uuid4(),
            name="Test Location"
        )
        assert location.address is None
        assert location.metadata == {}
        assert isinstance(location.created_at, datetime)
        assert isinstance(location.updated_at, datetime)
