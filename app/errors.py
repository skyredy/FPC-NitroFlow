class ProviderError(Exception):
    def __init__(self, code, status=0):
        self.code, self.status = code, status
        super().__init__(code)
