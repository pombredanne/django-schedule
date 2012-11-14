from django.test import TestCase
from django.conf import settings
from django.db.models.loading import load_app
from django.core.management import call_command

APP_NAME = 'eventtools.tests.eventtools_testapp'

class TestCaseWithApp(TestCase):

    """Make sure to call super(..).setUp and tearDown on subclasses"""
    
    def setUp(self):
        self.__class__.__module__ = self.__class__.__name__

        self.old_INSTALLED_APPS = settings.INSTALLED_APPS
        settings.INSTALLED_APPS += [APP_NAME]
        load_app(APP_NAME)
        call_command('flush', verbosity=0, interactive=False)
        call_command('syncdb', verbosity=0, interactive=False)
        
    def tearDown(self):
        settings.INSTALLED_APPS = self.old_INSTALLED_APPS
