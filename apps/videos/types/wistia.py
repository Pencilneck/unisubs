# Amara, universalsubtitles.org
#
# Copyright (C) 2012 Participatory Culture Foundation
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

import urlparse

from vidscraper.sites import wistia
from vidscraper.errors import Error as VidscraperError
from base import VideoType
#from django.conf import settings
from django.utils.html import strip_tags

# wistia.WISTIA_API_KEY = getattr(settings, 'WISTIA_API_KEY')
# wistia.WISTIA_API_SECRET = getattr(settings, 'WISTIA_API_SECRET')


class WistiaVideoType(VideoType):

    abbreviation = 'W'
    name = 'Wistia.com'
    site = 'wistia.com'
    linkurl = None

    requires_url_exists = True

    def __init__(self, url):
        self.url = url
        self.videoid = self._get_wistia_id(url)
        # not sure why this is being done, it breaks external URL
        self.linkurl = url.replace('/embed/', '/medias/')
        try:
            self.shortmem = wistia.get_shortmem(url)
        except VidscraperError:
            # we're not raising an error here because it
            # disallows us from adding private Wistia videos.
            pass

    @property
    def video_id(self):
        return self.videoid

    def convert_to_video_url(self):
        return "http://fast.wistia.net/embed/iframe/%s" % self.videoid

    @classmethod
    def video_url(cls, obj):
        return obj.url

    @classmethod
    def matches_video_url(cls, url):
        return bool(wistia.WISTIA_REGEX.match(url))

    def create_kwars(self):
        return {'videoid': self.videoid}

    def set_values(self, video_obj):
        try:
            thumb = wistia.get_thumbnail_url(self.url, self.shortmem)
            video_obj.thumbnail = thumb or ''
            video_obj.small_thumbnail = ''
            if thumb:
                # this is cumbersome, but Wistia offers only a dynamic
                # thumbnail service that expects desired dimensions and
                # populates a cache with a generated image, so the only thing
                # to do here is provide a placeholder with sensible defaults,
                # that have the correct proportions
                try:
                    su = urlparse.urlparse(thumb)
                    dims = su.query.rsplit('=')[1].split('x')
                    height = (200 * dims[1]) / dims[0]
                    new_qs = '%sx%s' % '200', height
                    new_url = urlparse.ParseResult(scheme=su.scheme,
                                                   netloc=su.netloc,
                                                   path=su.path,
                                                   params=su.params,
                                                   query=new_qs,
                                                   fragment=su.fragment)
                    video_obj.small_thumbnail = new_url
                except:
                    # if anything failed, it was because the original thumbnail
                    # URL was bogus, so not small thumbnail is available anyway
                    pass
            video_obj.title = wistia.scrape_title(self.url, self.shortmem)
            description = wistia.scrape_description(self.url, self.shortmem)
            video_obj.description = strip_tags(description)
            video_obj.save()
        except Exception:
            # in case the Wistia video is private.
            pass
        return video_obj

    def _get_wistia_id(self, video_url):
        return wistia.WISTIA_REGEX.match(video_url).groupdict().get('video_id')
