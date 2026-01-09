from soongo_data.connectors.mercedes_benz.full_data import MercedesBenzData

class TestConnectorsMercedesBenz:
    def tests_connectors_mercedes_benz_name(self):
        mercedes = MercedesBenzData("test_folder", "acorus")
        assert mercedes.NAME == "MERCEDES_BENZ"