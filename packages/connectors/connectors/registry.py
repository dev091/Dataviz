from connectors.base import Connector
from connectors.impl.csv_connector import CSVConnector
from connectors.impl.google_sheets_connector import GoogleSheetsConnector
from connectors.impl.mysql_connector import MySQLConnector
from connectors.impl.postgres_connector import PostgresConnector
from connectors.impl.salesforce_connector import SalesforceConnector


REGISTRY: dict[str, type[Connector]] = {
    "postgresql": PostgresConnector,
    "mysql": MySQLConnector,
    "csv": CSVConnector,
    "google_sheets": GoogleSheetsConnector,
    "salesforce": SalesforceConnector,
}


def get_connector(connector_type: str) -> Connector:
    cls = REGISTRY.get(connector_type)
    if not cls:
        raise ValueError(f"Unsupported connector type: {connector_type}")
    return cls()
