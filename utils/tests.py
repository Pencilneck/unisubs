# -*- coding: utf-8 -*-
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see
# http://www.gnu.org/licenses/agpl-3.0.html.

from string import printable as chars
from random import randint, choice

from django.core.urlresolvers import reverse
from django.test import TestCase
import simplejson as json

from teams.models import Task
from videos.models import Video
from utils import test_factories
from utils.multi_query_set import MultiQuerySet
from utils.compress import compress, decompress
from utils.chunkediter import chunkediter

class MultiQuerySetTest(TestCase):
    fixtures = ['test.json']

    def test_full(self):
        self.assertEqual(list(Video.objects.all()),
                         list(MultiQuerySet(Video.objects.all())),
                         "Full, single MQS didn't match full QS.")

        self.assertEqual(list(Video.objects.all()),
                         list(MultiQuerySet(Video.objects.none(),
                                            Video.objects.all(),
                                            Video.objects.none())),
                         "Full MQS with blanks didn't match full QS.")

        self.assertEqual(list(Video.objects.all()) + list(Video.objects.all()),
                         list(MultiQuerySet(Video.objects.none(),
                                            Video.objects.all(),
                                            Video.objects.none(),
                                            Video.objects.all())),
                         "Double MQS with blanks didn't match double full QS.")

    def test_slice(self):
        qs = Video.objects.all()
        mqs = MultiQuerySet(Video.objects.all())

        self.assertEqual(list(qs[0:1]),
                         list(mqs[0:1]),
                         "MQS[:1] failed.")

        self.assertEqual(list(qs[0:2]),
                         list(mqs[0:2]),
                         "MQS[:2] failed.")

        self.assertEqual(list(qs[0:3]),
                         list(mqs[0:3]),
                         "MQS[:3] (out-of-bounds endpoint) failed.")

        self.assertEqual(list(qs[1:3]),
                         list(mqs[1:3]),
                         "MQS[1:3] failed.")

        self.assertEqual(list(qs[2:3]),
                         list(mqs[2:3]),
                         "MQS[2:3] failed.")

        self.assertEqual(list(qs[1:1]),
                         list(mqs[1:1]),
                         "MQS[1:1] (empty slice) failed.")

    def test_slice_multiple(self):
        qs = list(Video.objects.all())
        qs = qs + qs + qs
        mqs = MultiQuerySet(Video.objects.all(),
                            Video.objects.all(),
                            Video.objects.all())

        self.assertEqual(qs[0:3],
                         list(mqs[0:3]),
                         "MQS[:3] failed.")

        self.assertEqual(qs[0:6],
                         list(mqs[0:6]),
                         "MQS[:6] (entire range) failed.")

        self.assertEqual(qs[0:7],
                         list(mqs[0:7]),
                         "MQS[:7] (out-of-bounds endpoint) failed.")

        self.assertEqual(qs[1:3],
                         list(mqs[1:3]),
                         "MQS[1:3] failed.")

        self.assertEqual(qs[1:6],
                         list(mqs[1:6]),
                         "MQS[1:6] (entire range) failed.")

        self.assertEqual(qs[1:7],
                         list(mqs[1:7]),
                         "MQS[1:7] (out-of-bounds endpoint) failed.")

        self.assertEqual(qs[3:3],
                         list(mqs[3:3]),
                         "MQS[3:3] failed.")

        self.assertEqual(qs[3:6],
                         list(mqs[3:6]),
                         "MQS[3:6] (entire range) failed.")

        self.assertEqual(qs[3:7],
                         list(mqs[3:7]),
                         "MQS[3:7] (out-of-bounds endpoint) failed.")


class CompressTest(TestCase):
    def test_compression(self):
        # Make sure the empty string is handled.
        self.assertEqual('', decompress(compress('')))

        # Make sure a bunch of random ASCII data compresses correctly.
        for _ in xrange(100):
            l = randint(1, 4096)
            data = ''.join(choice(chars) for _ in xrange(l))
            self.assertEqual(data, decompress(compress(data)))

        # Make sure a bunch of random bytes compress correctly.
        for _ in xrange(100):
            l = randint(1, 4096)
            data = ''.join(chr(randint(0, 255)) for _ in xrange(l))
            self.assertEqual(data, decompress(compress(data)))

        # Make sure a bunch of random Unicode data compresses correctly.
        for _ in xrange(100):
            l = randint(1, 1024)
            data = ''.join(choice(u'☃ಠ_ಠ✿☺☻☹♣♠♥♦⌘⌥✔★☆™※±×~≈÷≠π'
                                  u'αßÁáÀàÅåÄäÆæÇçÉéÈèÊêÍíÌìÎîÑñ'
                                  u'ÓóÒòÔôÖöØøÚúÙùÜüŽž')
                           for _ in xrange(l))

            encoded_data = data.encode('utf-8')
            round_tripped = decompress(compress(encoded_data)).decode('utf-8')

            self.assertEqual(data, round_tripped)


# TODO: Test chunking somehow.
class ChunkedIterTest(TestCase):
    def test_iterate(self):
        data = [1, 10, 100, 1000, 10000]

        sum = 0
        for i in chunkediter(data):
            sum += i
        self.assertEqual(sum, 11111)

        sum = 0
        for i in chunkediter(data, 2):
            sum += i
        self.assertEqual(sum, 11111)

        sum = 0
        for i in chunkediter(data, 1):
            sum += i
        self.assertEqual(sum, 11111)

    def test_empty(self):
        data = []

        sum = 0
        for i in chunkediter(data):
            sum += i
        self.assertEqual(sum, 0)

        sum = 0
        for i in chunkediter(data, 1):
            sum += i
        self.assertEqual(sum, 0)


class BleachSanityTest(TestCase):

    def test_weird_input(self):
        import bleach
        html = "<b>hello</b>"
        value = bleach.clean(html, strip=True, tags=[], attributes=[])
        self.assertEquals(u"hello", value)

        html = "<b></b>"
        value = bleach.clean(html, strip=True, tags=[], attributes=[])
        self.assertEquals(u"", value)

        html = '<p><iframe frameborder="0" height="315" src="http://www.youtube.com/embed/6ydeY0tTtF4" width="560"></iframe></p>'
        value = bleach.clean(html, strip=True, tags=[], attributes=[])
        self.assertEquals(u"", value)

class TestEditor(object):
    """Simulates the editor widget for unit tests"""
    def __init__(self, client, video, original_language_code=None,
                 base_language_code=None, mode=None):
        """Construct a TestEditor

        :param client: django TestClient object for HTTP requests
        :param video: Video object to edit
        :param original_language_code: language code for the video audio.
        Should be set if and only if the primary_audio_language_code hasn't
        been set for the video.
        :param base_language_code: base language code for to use for
        translation tasks.
        :param mode: one of ("review", "approve" or None)
        """
        self.client = client
        self.video = video
        self.base_language_code = base_language_code
        if original_language_code is None:
            self.original_language_code = video.primary_audio_language_code
        else:
            if video.primary_audio_language_code is not None:
                raise AssertionError(
                    "primary_audio_language_code is set (%r)" %
                    video.primary_audio_language_code)
            self.original_language_code = original_language_code
        self.mode = mode
        self.task_approved = None
        self.task_id = None
        self.task_notes = None
        self.task_type = None

    def set_task_data(self, task, approved, notes):
        """Set data for the task that this edit is for.

        :param task: Task object
        :param approved: did the user approve the task.  Should be one of the
        values of Task.APPROVED_IDS.
        :param notes: String to set for notes
        """
        type_map = {
            10: 'subtitle',
            20: 'translate',
            30: 'review',
            40: 'approve',
        }
        self.task_id = task.id
        self.task_type = type_map[task.type]
        self.task_notes = notes
        self.task_approved = approved

    def _submit_widget_rpc(self, method, **data):
        """POST data to the widget:rpc view."""

        url = reverse('widget:rpc', args=(method,))
        post_data = dict((k, json.dumps(v)) for k, v in data.items())
        response = self.client.post(url, post_data)
        response_data = json.loads(response.content)
        if 'error' in response_data:
            raise AssertionError("Error calling widget rpc method %s:\n%s" %
                                 (method, response_data['error']))
        return response_data

    def run(self, language_code, completed=True, save_for_later=False):
        """Make the HTTP requests to simulate the editor

        We will use test_factories.dxfp_sample() for the subtitle data.

        :param language_code: code for the language of these subtitles
        :param completed: simulate the completed checkbox being set
        :param save_for_later: simulate the save for later button
        """

        self._submit_widget_rpc('fetch_start_dialog_contents',
                video_id=self.video.video_id)
        existing_language = self.video.subtitle_language(language_code)
        if existing_language is not None:
            subtitle_language_pk = existing_language.pk
        else:
            subtitle_language_pk = None

        response_data = self._submit_widget_rpc(
            'start_editing',
            video_id=self.video.video_id,
            language_code=language_code,
            original_language_code=self.original_language_code,
            base_language_code=self.base_language_code,
            mode=self.mode,
            subtitle_language_pk=subtitle_language_pk)
        session_pk = response_data['session_pk']

        self._submit_widget_rpc('finished_subtitles',
                                completed=completed,
                                save_for_later=save_for_later,
                                session_pk=session_pk,
                                subtitles=test_factories.dxfp_sample('en'),
                                task_approved=self.task_approved,
                                task_id=self.task_id,
                                task_notes=self.task_notes,
                                task_type=self.task_type)
