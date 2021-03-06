#!/usr/bin/python
# Amara, universalsubtitles.org
# 
# Copyright (C) 2013 Participatory Culture Foundation
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see 
# http://www.gnu.org/licenses/agpl-3.0.html.

# annoying as this is, it's meant to silence the damn keydcache warning
import warnings
import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
logging.getLogger('keyedcache').addHandler(NullHandler())


from django.core.management import execute_manager

# put apps dir in python path, like pinax
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps')) 
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'libs')) 
os.environ.setdefault("CELERY_LOADER", "djcelery.loaders.DjangoLoader")

try:
    import settings # Assumed to be in the same directory.
except ImportError:
    import sys
    sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
    sys.exit(1)

if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore",category=DeprecationWarning)
        warnings.filterwarnings("ignore",category=UserWarning, message=".*was already imported from.*")
        warnings.filterwarnings("ignore",message=".*integer argument expected, got float.*")

        execute_manager(settings)
