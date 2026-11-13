import pytest

from app.services import settings as service


def test_defaults(app):
    with app.state.user_sessions() as session:
        assert service.get_all(session) == {"theme": "system", "daily_goal_minutes": 20}


def test_set_and_persist(app):
    with app.state.user_sessions() as session:
        service.set_value(session, "theme", "dark")
        service.set_value(session, "theme", "light")
    with app.state.user_sessions() as session:
        assert service.get_all(session)["theme"] == "light"


@pytest.mark.parametrize(
    ("key", "value"),
    [("theme", "pink"), ("daily_goal_minutes", 2), ("daily_goal_minutes", "20"),
     ("daily_goal_minutes", True), ("daily_goal_minutes", 20.5), ("daily_goal_minutes", 500)],
)
def test_invalid_values_rejected(app, key, value):
    with app.state.user_sessions() as session:
        with pytest.raises(service.SettingError):
            service.set_value(session, key, value)


def test_unknown_key_rejected(app):
    with app.state.user_sessions() as session:
        with pytest.raises(KeyError):
            service.set_value(session, "nope", 1)
