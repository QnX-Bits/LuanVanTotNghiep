import ssl

import pytest

from app.models import database_connection_settings


def test_manus_mysql_ssl_json_becomes_verified_pymysql_context():
    url, connect_args = database_connection_settings(
        'mysql://demo:placeholder@db.example.test/portfolio'
        '?ssl=%7B%22rejectUnauthorized%22%3Atrue%7D'
    )

    assert url.drivername == "mysql+pymysql"
    assert "ssl" not in url.query
    context = connect_args["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_mysql_ssl_json_can_disable_certificate_verification_when_explicit():
    url, connect_args = database_connection_settings(
        'mysql://demo:placeholder@db.example.test/portfolio'
        '?ssl=%7B%22rejectUnauthorized%22%3Afalse%7D'
    )

    assert "ssl" not in url.query
    context = connect_args["ssl"]
    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False


def test_mysql_without_ssl_option_keeps_driver_defaults():
    url, connect_args = database_connection_settings("mysql://demo:placeholder@db.example.test/portfolio")

    assert url.drivername == "mysql+pymysql"
    assert connect_args == {}


def test_postgres_scheme_is_normalized_without_mysql_ssl_handling():
    url, connect_args = database_connection_settings("postgres://demo:placeholder@db.example.test/portfolio")

    assert url.drivername == "postgresql+psycopg"
    assert connect_args == {}


def test_invalid_mysql_reject_unauthorized_type_is_rejected():
    with pytest.raises(ValueError, match="must be a boolean"):
        database_connection_settings(
            'mysql://demo:placeholder@db.example.test/portfolio'
            '?ssl=%7B%22rejectUnauthorized%22%3A%22yes%22%7D'
        )
