from soongo_data.connectors.greenway.api import GreenwayExpensesSource


class TestConnectorsGreenwayApi:
    def test_greenway_api_good_init(self):
        data_source = GreenwayExpensesSource("test", "test_logger", "acorus", "test_s3_bucket")
        assert data_source.NAME == "EXPENSES"