

class WooMockResponse:

    def __init__(self, json_data: dict, status_code: int = 200):
        self.status_code = status_code
        self.json_data = json_data

    def json(self) -> dict:
        return {"success": self.status_code == 200, "data": self.json_data}