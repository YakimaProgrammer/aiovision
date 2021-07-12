import aiogoogle
from aiogoogle.auth.creds import ServiceAccountCreds

class SessionManager(aiogoogle.Aiogoogle):
    #"https://www.googleapis.com/auth/cloud-platform" means the SessionManager will be able to access everything as limited by IAM
    def __init__(self, service_account_creds,
                 scopes=["https://www.googleapis.com/auth/cloud-platform"]):

        super().__init__(service_account_creds = ServiceAccountCreds(
                            **service_account_creds,
                            scopes=scopes
                        ))

        self.discovered = {}

    async def discover(self, api_name, api_version=None, validate=True):
        key = f"{api_name}.{api_version}.{validate}"
        try:
            return self.discovered[key]
        except KeyError:
            doc = await super().discover(api_name, api_version, validate)
            self.discovered[key] = doc
            return doc
