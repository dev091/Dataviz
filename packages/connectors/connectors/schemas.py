from pydantic import BaseModel, Field


class PostgresConfig(BaseModel):
    uri: str


class MySQLConfig(BaseModel):
    uri: str


class CSVConfig(BaseModel):
    file_path: str
    file_format: str | None = Field(default=None, description="Detected or explicit uploaded file format")
    sheet_name: str | None = Field(default=None, description="Optional sheet name for spreadsheet sources")


class GoogleSheetsConfig(BaseModel):
    csv_export_url: str = Field(description="Published Google Sheets CSV export URL")


class SalesforceConfig(BaseModel):
    username: str
    password: str
    security_token: str
    domain: str = "login"
    object_name: str = "Opportunity"
