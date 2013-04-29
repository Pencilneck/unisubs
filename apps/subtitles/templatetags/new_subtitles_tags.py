# -*- coding: utf-8 -*-
# Amara, universalsubtitles.org
#
# Copyright (C) 2013 Participatory Culture Foundation
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License along
# with this program.  If not, see http://www.gnu.org/licenses/agpl-3.0.html.

from django import template
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _

register = template.Library()

@register.filter
def visibility_display(subtitle_version):
    '''
    Returns a human readable representation of the interaction between
    visibility and visibility_override for display purpouses.
    '''
    visibility = subtitle_version.visibility_override or subtitle_version.visibility
    return force_unicode({
        'public': _("Public"),
        'private': _("Private"),
        'deleted': _("Deleted")
    }[visibility])