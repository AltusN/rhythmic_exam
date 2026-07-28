import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from rhytmic_exam_app.models import User

@pytest.fixture(scope="module")
def new_user():
    user = User(username="jessy", name="James", surname="May", sagf_id = "123", email="james@may.com")
    return user