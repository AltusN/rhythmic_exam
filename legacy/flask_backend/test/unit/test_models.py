
def test_new_user(new_user):
    """
        Test new create users
    """
    pwd = "cat"

    new_user.set_password(pwd)
    
    assert new_user.username == "jessy"
    assert new_user.email == "james@may.com"
    assert new_user.name == "James"
    assert new_user.surname == "May"
    assert new_user.sagf_id == "123"
    assert True is new_user.check_password(pwd)

def test_new_user_is_enabled(new_user):
    """
        check if the new iser is enabled
    """
    assert not new_user.is_enabled()


def test_new_user_check_password_invalid(new_user):
    """Password comparison should fail for incorrect values."""
    new_user.set_password("correct-password")

    assert not new_user.check_password("wrong-password")


def test_user_admin_property_reflects_admin_flag(new_user):
    """The convenience property should return the underlying admin value."""
    new_user.admin = True
    assert new_user.is_admin is True

    new_user.admin = False
    assert new_user.is_admin is False