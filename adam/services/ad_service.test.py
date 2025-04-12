import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
import ldap
from adam.services.ad_service import connect_to_ad
from adam.config import config

@pytest.fixture
def mock_ldap():
    with patch('adam.services.ad_service.ldap') as mock:
        yield mock

def test_connect_to_ad_success(mock_ldap):
    pass
