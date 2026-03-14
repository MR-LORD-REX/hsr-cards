class HSR_Error(Exception):
    """Base class for exceptions in this module."""
    pass

class AnomalyDataError(HSR_Error):
    """Exception raised for errors in the anomaly data."""
    def __init__(self, message="Error",code=None):
        self.message = message
        if code == 10102:
            self.message = "data is not set to public"
        elif code == 10001:
            self.message = f"invalid cookies check your .env file and load it properly ,code:{code}"
        else:
            self.message = f"Unknown error with code {code}"
        super().__init__(self.message)
        
class MOCDataError(HSR_Error):
    """Exception raised for errors in the MOC data."""
    def __init__(self, message="Error",code=None):
        self.message = message
        if code == 10102:
            self.message = "data is not set to public"
        elif code == 000:
            self.message = "fast clear"
        elif code == 10104:
            self.message = "data is not provided by server"
        elif code == 10001:
            self.message = "invalid cookies check your .env file and load it properly"
        super().__init__(self.message)

class APIError(HSR_Error):
    """Exception raised for errors in the API calls."""
    def __init__(self, message="API Error"):
        self.message = message
        super().__init__(self.message)
        
class PFError(HSR_Error):
    """Exception raised for errors in the PFE rendering."""
    def __init__(self, message="PFE Rendering Error",code=None):
        self.message = message
        if code == 10102:
            self.message = "data is not set to public"
        elif code == 000:
            self.message = "fast clear"
        elif code == 10104:
            self.message = "data is not provided by server"
        elif code == 10001:
            self.message = "invalid cookies check your .env file and load it properly"
        super().__init__(self.message)