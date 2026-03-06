import os

import pytest

from connectors.impl.google_sheets_connector import GoogleSheetsConnector
from connectors.impl.mysql_connector import MySQLConnector
from connectors.impl.postgres_connector import PostgresConnector
from connectors.impl.salesforce_connector import SalesforceConnector


@pytest.mark.integration
def test_live_postgres_connector_discover() -> None:
    uri = os.getenv("LIVE_POSTGRES_URI")
    if not uri:
        pytest.skip("LIVE_POSTGRES_URI is not configured")

    connector = PostgresConnector()
    connector.validate_config({"uri": uri})
    datasets = connector.discover({"uri": uri})
    assert datasets


@pytest.mark.integration
def test_live_mysql_connector_discover() -> None:
    uri = os.getenv("LIVE_MYSQL_URI")
    if not uri:
        pytest.skip("LIVE_MYSQL_URI is not configured")

    connector = MySQLConnector()
    connector.validate_config({"uri": uri})
    datasets = connector.discover({"uri": uri})
    assert datasets


@pytest.mark.integration
def test_live_google_sheets_connector_discover() -> None:
    csv_export_url = os.getenv("LIVE_GOOGLE_SHEETS_CSV_URL")
    if not csv_export_url:
        pytest.skip("LIVE_GOOGLE_SHEETS_CSV_URL is not configured")

    connector = GoogleSheetsConnector()
    connector.validate_config({"csv_export_url": csv_export_url})
    datasets = connector.discover({"csv_export_url": csv_export_url})
    assert datasets


@pytest.mark.integration
def test_live_salesforce_connector_discover() -> None:
    username = os.getenv("LIVE_SALESFORCE_USERNAME")
    password = os.getenv("LIVE_SALESFORCE_PASSWORD")
    security_token = os.getenv("LIVE_SALESFORCE_SECURITY_TOKEN")
    domain = os.getenv("LIVE_SALESFORCE_DOMAIN", "login")
    object_name = os.getenv("LIVE_SALESFORCE_OBJECT", "Account")

    if not (username and password and security_token):
        pytest.skip("LIVE_SALESFORCE_USERNAME/PASSWORD/SECURITY_TOKEN are not configured")

    connector = SalesforceConnector()
    payload = {
        "username": username,
        "password": password,
        "security_token": security_token,
        "domain": domain,
        "object_name": object_name,
    }
    connector.validate_config(payload)
    datasets = connector.discover(payload)
    assert datasets
