from contextlib import contextmanager
from django.test import Client
from django.conf import settings

class Browser(Client):
    def __init__(self):
        super().__init__(enforce_csrf_checks=True)

    def request(self, **request):
        response = super().request(**request)
        response.location = response.headers.get('Location')
        response.is_json = response.headers.get('Content-Type', '').startswith('application/json')
        return response

    @contextmanager
    def session_transaction(self):
        session = self.session
        yield session
        session.save()
        self.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
