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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see
# http://www.gnu.org/licenses/agpl-3.0.html.

"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

import json

from django.test import TestCase
from babelsubs.storage import SubtitleSet
import babelsubs
from auth.models import CustomUser
from videos.models import Video, Action, SubtitleLanguage
from videos import models
from subtitles import models as sub_models
from apps.subtitles.pipeline import rollback_to
from widget.models import SubtitlingSession
from widget.rpc import Rpc
from widget.null_rpc import NullRpc
from django.core.urlresolvers import reverse
from widget import video_cache
from datetime import datetime, timedelta
from django.conf import settings
from utils import test_utils, test_factories

VIDEO_URL = 'http://videos.mozilla.org/firefox/3.5/switch/switch.ogv'

def create_subtitle_set(number_of_subtitles=0, synced=True):
    subtitle_set = SubtitleSet('en')

    for x in xrange(0, number_of_subtitles+1):
        start = x * 1000 if synced else None
        end = x * 1000 + 1000 if synced else None
        subtitle_set.append_subtitle(start, end, 'hey you %s' % x)

    return subtitle_set

class FakeDatetime(object):
    def __init__(self, now):
        self.now_date = now

    def now(self):
        return self.now_date

class RequestMockup(object):
    def __init__(self, user, browser_id="a"):
        self.user = user
        self.session = {}
        self.browser_id = browser_id
        self.COOKIES = {}
        self.META = {}
        self.GET = {}

class NotAuthenticatedUser:
    def __init__(self):
        self.session = {}
    def is_authenticated(self):
        return False
    def is_anonymous(self):
        return True

rpc = Rpc()
null_rpc = NullRpc()

class TestRpcView(TestCase):

    def test_views(self):
        #UnicodeEncodeError: 500 status
        data = {
            'русский': '{}'
        }
        self.client.post(reverse('widget:rpc', args=['show_widget']), data)

        #broken json: 500 status
        data = {
            'param': '{broken - json "'
        }
        self.client.post(reverse('widget:rpc', args=['show_widget']), data)
        #call private method
        self.client.get(reverse('widget:rpc', args=['_subtitle_count']))
        #500, because method does not exists: 500 status
        self.client.get(reverse('widget:rpc', args=['undefined_method']))
        #incorect arguments number: 500 status
        self.client.get(reverse('widget:rpc', args=['show_widget']))

    def test_rpc(self):
        video_url = 'http://www.youtube.com/watch?v=z2U_jf0urVQ'
        video, created = Video.get_or_create_for_url(video_url)

        url = reverse('widget:rpc', args=['show_widget'])
        data = {
            'is_remote': u'false',
            'base_state': u'{"language_pk":%s,"language_code":"en"}',
            'video_url': u'"%s"' % video_url
        }
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 200)


class TestRpc(TestCase):
    fixtures = ['test_widget.json', 'test.json']

    def setUp(self):
        self.user_0 = CustomUser.objects.get(pk=3)
        self.user_1 = CustomUser.objects.get(pk=4)
        self.video_pk = 12
        video_cache.invalidate_video_id(VIDEO_URL)

    def test_actions_for_subtitle_edit(self):
        request = RequestMockup(self.user_0)
        action_ids = [a.id for a in Action.objects.all()]
        self._create_basic_version(request)
        # this is querying for a ADD_TRANSLATION action, btw
        qs = Action.objects.exclude(id__in=action_ids).exclude(action_type=Action.ADD_VIDEO)
        self.assertEqual(qs.count(), 1)

    def test_no_user_for_video_creation(self):
        request = RequestMockup(self.user_0)
        [i.id for i in Action.objects.all()]
        rpc.show_widget(request, VIDEO_URL, False)

    def test_fetch_subtitles(self):
        request = RequestMockup(self.user_0)
        version = self._create_basic_version(request)

        subs = rpc.fetch_subtitles(request, version.video.video_id, version.language.pk)

        sset = SubtitleSet('en', initial_data=subs['subtitles'])
        self.assertEqual(1, len(sset))

    def test_add_alternate_urls(self):
        url_0 = VIDEO_URL
        url_1 = 'http://ia700406.us.archive.org/16/items/PeopleOfHtml5-BruceLawsonmp4Version/PeopleOfHtml5-BruceLawson.mp4'

        request = RequestMockup(self.user_0)
        return_value = rpc.show_widget(request, url_0,
                                       False, additional_video_urls=[url_1])

        video_id = return_value['video_id']
        return_value = rpc.start_editing(request, video_id, 'en', 
                                         original_language_code='en')
        session_pk = return_value['session_pk']

        rpc.finished_subtitles(request, session_pk, create_subtitle_set().to_xml());
        return_value = rpc.show_widget(request, url_1,
                                       False, additional_video_urls=[url_0])

        self.assertEqual(video_id, return_value['video_id'])

        subs = rpc.fetch_subtitles(request, video_id,
                                   return_value['drop_down_contents'][0]['pk'])

        self.assertEquals(1, len(SubtitleSet('en', subs['subtitles'])))

        return_value = rpc.show_widget(request, url_1, False)

        self.assertEqual(video_id, return_value['video_id'])

    def test_keep_subtitling_dialog_open(self):
        request = RequestMockup(self.user_0)
        return_value = rpc.show_widget(request, VIDEO_URL, False)
        video_id = return_value['video_id']
        return_value = rpc.start_editing(
            request, video_id, 'en',
            original_language_code='en')
        self.assertEqual(True, return_value['can_edit'])
        subs = return_value['subtitles']
        self.assertEqual(0, subs['version'])
        subtitles = SubtitleSet('es', subs['subtitles'])
        self.assertEqual(0, len(subtitles))
        # the subtitling dialog pings the server, even
        # though we've done no subtitling work yet.
        rpc.regain_lock(request, return_value['session_pk'])
        video = Video.objects.get(video_id=video_id)
        # if video.latest_version() returns anything other than None,
        # video.html will show that the video has subtitles.
        self.assertEqual(None, video.latest_version())

    def test_update_after_clearing_session(self):
        request = RequestMockup(self.user_1)
        session = self._start_editing(request)
        # this will fail if locking is dependent on anything in session,
        # which can get cleared after login.
        request.session = {}
        rpc.finished_subtitles(request, session.pk, create_subtitle_set(1))
        video = Video.objects.get(pk=session.video.pk)
        self.assertEquals(1, video.subtitle_language().subtitleversion_set
                                                      .full()
                                                      .count())

    def test_finish(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_version(request)
        language = session.language

        self.assertTrue(sub_models.SubtitleLanguage
                                  .objects.having_versions()
                                  .filter(pk=language.pk).exists())

        self.assertTrue(sub_models.SubtitleLanguage
                                  .objects.having_nonempty_tip()
                                  .filter(pk=language.pk).exists())

        sv = sub_models.SubtitleVersion.objects.order_by('-id')[0]
        self.assertEqual(sv.origin, sub_models.ORIGIN_LEGACY_EDITOR)

        self.assertTrue(language.video.is_subtitled)

    def test_get_widget_url(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_version(request)
        Video.objects.get(
            video_id=session.video.video_id).subtitle_language()
        # succeeds if no error.

    def test_change_set(self):
        request = RequestMockup(self.user_0)
        session = create_two_sub_session(request)
        return_value = rpc.start_editing(request, session.video.video_id, 'en')
        session_pk = return_value['session_pk']

        subtitle_set = SubtitleSet('en')
        subtitle_set.append_subtitle(0, 1000, 'hey you 3')
        subtitle_set.append_subtitle(1000, 2000, 'hey you 1')
        subtitle_set.append_subtitle(2000, 3000, 'hey you 1')

        rpc.finished_subtitles(request, session_pk, subtitle_set.to_xml())
        video = Video.objects.get(pk=session.video.pk)
        language = video.subtitle_language('en')

        self.assertEqual(2, language.subtitleversion_set.full().count())

        version = language.get_tip()
        time_change, text_change = version.get_changes()

        self.assertTrue(text_change > 0 and text_change <= 1)
        self.assertEqual(time_change, 0)

    def test_cant_edit_because_locked(self):
        request_0 = RequestMockup(self.user_0)
        return_value = rpc.show_widget(request_0, VIDEO_URL, False)
        video_id = return_value['video_id']

        rpc.start_editing(request_0, video_id, 'en', original_language_code='en')

        request_1 = RequestMockup(self.user_1, "b")
        rpc.show_widget(request_1, VIDEO_URL, False)

        return_value = rpc.start_editing(request_1, video_id, 'en')

        self.assertEqual(False, return_value['can_edit'])
        self.assertEqual(unicode(self.user_0), return_value['locked_by'])

    def test_basic(self):
        request_0 = RequestMockup(self.user_0)
        return_value = rpc.show_widget(request_0, VIDEO_URL, False)
        video_id = return_value['video_id']
        return_value = rpc.start_editing(
            request_0, video_id, 'en', original_language_code='en')
        session_pk = return_value['session_pk']

        subtitle_set = create_subtitle_set()
        rpc.finished_subtitles(request_0, session_pk, subtitle_set.to_xml())

        video, _ = models.Video.get_or_create_for_url(VIDEO_URL)

        self.assertEqual(1, video.newsubtitlelanguage_set.count())
        subtitle_language = video.subtitle_language("en")
        self.assertEqual(1, len(subtitle_language.get_tip().get_subtitles()))

    def test_not_complete(self):
        request_0 = RequestMockup(self.user_0)
        return_value = rpc.show_widget(request_0, VIDEO_URL, False)
        video_id = return_value['video_id']
        return_value = rpc.start_editing(
            request_0, video_id, 'en', original_language_code='en')
        session_pk = return_value['session_pk']

        subtitle_set = create_subtitle_set()
        rpc.finished_subtitles(request_0, session_pk, subtitle_set.to_xml(), completed=False)

        v = models.Video.objects.get(video_id=video_id)
        sl = v.subtitle_language('en')
        self.assertFalse(sl.subtitles_complete)

    def test_complete_but_not_synced(self):
        request = RequestMockup(self.user_0)
        session = create_two_sub_session(request, completed=True)
        language = sub_models.SubtitleLanguage.objects.get(pk=session.language.pk)

        self.assertTrue(language.is_complete_and_synced())

        # right now video is complete.
        completed_langs = session.video.completed_subtitle_languages()

        self.assertTrue(session.video.is_complete)
        self.assertEquals(1, len(completed_langs))
        self.assertEquals('en', completed_langs[0].language_code)

        return_value = rpc.start_editing(
            request, session.video.video_id, 'en',
            subtitle_language_pk=session.language.pk)

        subtitle_set = create_subtitle_set(1, False)

        rpc.finished_subtitles(request, return_value['session_pk'],
                               subtitles=subtitle_set.to_xml(), completed=True)

        video = Video.objects.get(pk=session.language.video.pk)
        language = video.subtitle_language('en')
        
        self.assertFalse(language.is_complete_and_synced())

        # since we have one unsynced subtitle, the video is no longer complete.
        self.assertFalse(video.is_complete)
        self.assertEquals(0, len(session.video.completed_subtitle_languages()))

    def test_complete_with_incomplete_translation(self):
        request = RequestMockup(self.user_0)
        session = create_two_sub_session(request, completed=True)
        response = rpc.start_editing(
            request, session.video.video_id, 'es', base_language_code='en')
        session_pk = response['session_pk']

        rpc.finished_subtitles(request, session_pk, subtitles=create_subtitle_set().to_xml())
        video = Video.objects.get(pk=session.video.pk)

        self.assertTrue(video.is_complete)
        self.assertEquals(1, len(video.completed_subtitle_languages()))
        self.assertEquals(
            'en', video.completed_subtitle_languages()[0].language_code)

    def test_incomplete_with_complete_translation(self):
        request = RequestMockup(self.user_0)
        session = create_two_sub_dependent_session(request)
        # we now have a 100% translation of an incomplete language.
        video = Video.objects.get(pk=session.video.pk)
        self.assertFalse(video.is_complete)
        self.assertEquals(0, len(video.completed_subtitle_languages()))

    def test_finish_then_other_user_opens(self):
        request_0 = RequestMockup(self.user_0)
        return_value = rpc.show_widget(request_0, VIDEO_URL, False)
        video_id = return_value['video_id']
        return_value = rpc.start_editing(
            request_0, video_id, 'en', original_language_code='en')
        session_pk = return_value['session_pk']
        rpc.finished_subtitles(request_0, session_pk, subtitles=create_subtitle_set().to_xml())

        # different user opens the dialog for video
        request_1 = RequestMockup(self.user_1, "b")
        return_value = rpc.start_editing(request_1, video_id, 'en')

        # make sure we are getting back finished subs.
        self.assertEqual(True, return_value['can_edit'])
        subs = return_value['subtitles']

        self.assertEqual(1, subs['version'])
        self.assertEqual(1, len(SubtitleSet('en', subs['subtitles'])))

    def test_regain_lock_while_not_authenticated(self):
        request_0 = RequestMockup(NotAuthenticatedUser())
        return_value = rpc.show_widget(request_0, VIDEO_URL, False)
        video_id = return_value['video_id']
        return_value = rpc.start_editing(
            request_0, video_id, 'en', original_language_code='en')
        session_pk = return_value['session_pk']
        inserted = [{'subtitle_id': 'aa',
                     'text': 'hey!',
                     'start_time': 2300,
                     'end_time': 3400,
                     'sub_order': 1.0}]
        response = rpc.regain_lock(request_0, session_pk)
        self.assertEqual('ok', response['response'])
        response = rpc.finished_subtitles(
            request_0, session_pk, subtitles=inserted)
        self.assertEqual('not_logged_in', response['response'])

    def test_log_in_then_save(self):
        request_0 = RequestMockup(NotAuthenticatedUser())
        return_value = rpc.show_widget(request_0, VIDEO_URL, False)
        video_id = return_value['video_id']
        return_value = rpc.start_editing(
            request_0, video_id, 'en', original_language_code='en')
        session_pk = return_value['session_pk']
        sset = SubtitleSet('en')
        sset.append_subtitle(2300, 3400, 'hey')
        response = rpc.regain_lock(request_0, session_pk)
        self.assertEqual('ok', response['response'])
        request_0.user = self.user_0
        rpc.finished_subtitles(request_0, session_pk, sset.to_xml())
        sversion = sub_models.SubtitleVersion.objects.order_by('-pk')[0]
        sversion.subtitle_count = 1
        self.assertEqual(request_0.user.pk, sversion.author.pk)

    def test_zero_out_version_1(self):
        request_0 = RequestMockup(self.user_0)
        version = self._create_basic_version(request_0)

        # different user opens dialog for video
        request_1 = RequestMockup(self.user_1, "b")
        rpc.show_widget(request_1, VIDEO_URL, False)
        return_value = rpc.start_editing(request_1, version.language.video.video_id, 'en')
        session_pk = return_value['session_pk']
        # user_1 deletes all the subs
        rpc.finished_subtitles(request_1, session_pk, SubtitleSet('en').to_xml())
        video = Video.objects.get(pk=version.language.video.pk)
        language = SubtitlingSession.objects.get(pk=session_pk).language
        self.assertEqual(2, language.subtitleversion_set.full().count())
        self.assertEqual( 0, len(language.version().get_subtitles()))
        self.assertTrue(sub_models.SubtitleLanguage.objects.having_nonempty_versions().filter(pk=language.pk).exists())
        self.assertFalse(sub_models.SubtitleLanguage.objects.having_nonempty_tip().filter(pk=language.pk).exists())

    def test_zero_out_version_0(self):
        request_0 = RequestMockup(self.user_0)
        return_value = rpc.show_widget(request_0, VIDEO_URL, False, base_state={})
        video_id = return_value['video_id']
        # we submit only blank subs.
        response = rpc.start_editing(
            request_0, video_id,
            'en', original_language_code='en')
        session_pk = response['session_pk']
        rpc.finished_subtitles(
            request_0,
            session_pk,
            subtitles=[])
        video = Video.objects.get(video_id=video_id)
        language = SubtitlingSession.objects.get(pk=session_pk).language
        self.assertEquals(0, language.subtitleversion_set.full().count())
        self.assertEquals(None, language.version())
        self.assertFalse(sub_models.SubtitleLanguage.objects.having_nonempty_versions().filter(pk=language.pk).exists())

    def test_start_translating(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_version(request)
        sl_en = session.language

        # open translation dialog.
        response = rpc.start_editing(request, session.video.video_id,
                                     'es', base_language_code=sl_en.language_code)

        session_pk = response['session_pk']
        subs = response['subtitles']

        self.assertEquals(True, response['can_edit'])
        self.assertEquals(0, subs['version'])
        self.assertEquals(0, len(SubtitleSet('es', subs['subtitles'])))

        rpc.finished_subtitles(request, session_pk, create_subtitle_set().to_xml())
        video = models.Video.objects.get(id=session.video.id)
        translations = rpc.fetch_subtitles(request, video.video_id, video.subtitle_language('es').pk)

        subtitles = SubtitleSet('es',translations['subtitles'])
        self.assertEquals(1, len(subtitles))
        self.assertEquals('hey you 0', subtitles[0][2])

        language = video.subtitle_language('es')

        self.assertEquals(1, language.subtitleversion_set.full().count())
        self.assertEquals(language.get_translation_source_language_code(), 'en')

        version = language.get_tip()

        self.assertTrue('en' in version.get_lineage())

        response = rpc.start_editing(request, session.video.video_id,
                                     'es', base_language_code=sl_en.language_code)

        rpc.finished_subtitles(request, session_pk, create_subtitle_set(2).to_xml())
        translations = rpc.fetch_subtitles(request, video.video_id, video.subtitle_language('es').pk)

        subtitles = SubtitleSet('es',translations['subtitles'])
        self.assertEquals(3, len(subtitles))
        self.assertEquals('hey you 0', subtitles[0][2])
        self.assertEquals('hey you 1', subtitles[1][2])
        self.assertEquals('hey you 2', subtitles[2][2])

        language = video.subtitle_language('es')

        self.assertEquals(2, language.subtitleversion_set.full().count())
        self.assertEquals(language.get_translation_source_language_code(), 'en')

        version = language.get_tip()

        self.assertTrue('en' in version.get_lineage())

    def test_zero_out_trans_version_1(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_dependent_version(request)
        en_sl = session.video.subtitle_language('en')
        # user_1 opens translate dialog
        request_1 = RequestMockup(self.user_1, "b")
        rpc.show_widget(request_1, VIDEO_URL, False)
        response = rpc.start_editing(
            request_1, session.video.video_id, 'es', base_language_code='en')
        session_pk = response['session_pk']
        self.assertEquals(True, response['can_edit'])
        subs = response['subtitles']
        subtitles = SubtitleSet('en', subs['subtitles'])
        self.assertEquals(1, subs['version'])
        self.assertEquals(1, len(subtitles))
        # user_1 deletes the subtitles.
        rpc.finished_subtitles(request_1, session_pk, SubtitleSet('en').to_xml())
        language = SubtitlingSession.objects.get(pk=session_pk).language
        self.assertEquals(2, language.subtitleversion_set.full().count())
        self.assertEquals(0, len(language.version().get_subtitles()))
        self.assertTrue(sub_models.SubtitleLanguage.objects.having_nonempty_versions().filter(pk=language.pk).exists())
        self.assertFalse(sub_models.SubtitleLanguage.objects.having_nonempty_tip().filter(pk=language.pk).exists())

    def test_zero_out_trans_version_0(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_version(request)
        original_language = session.language
        response = rpc.start_editing(
            request, original_language.video.video_id, 'es', base_language_code=original_language.language_code)
        session_pk = response['session_pk']
        new_language = SubtitlingSession.objects.get(pk=session_pk).language
        rpc.finished_subtitles(request, session_pk, SubtitleSet('en').to_xml())
        # creating an empty version should not store empty stuff on the db
        self.assertEquals(0, new_language.subtitleversion_set.full().count())

        self.assertFalse(sub_models.SubtitleLanguage.objects.having_nonempty_versions().filter(pk=new_language.pk).exists())
        self.assertFalse(sub_models.SubtitleLanguage.objects.having_nonempty_tip().filter(pk=new_language.pk).exists())

    def test_edit_existing_original(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_version(request)
        language = sub_models.SubtitleLanguage.objects.get(pk=session.language.pk)
        return_value = rpc.show_widget(request, VIDEO_URL, False)
        return_value = rpc.start_editing(request, session.video.video_id, 'en', subtitle_language_pk=language.pk)

        self.assertEquals(len(SubtitleSet('en', return_value['subtitles']['subtitles'])), 1)
        self.assertFalse('original_subtitles' in return_value)

    def test_finish_twice(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_version(request)
        language = session.language
        self.assertEquals(1, language.version().subtitle_count)
        first_version = language.version()
        response = rpc.start_editing(
            request, session.video.video_id, 'en', subtitle_language_pk=session.language.pk)
        session_pk = response['session_pk']
        new_subs = create_subtitle_set(4)
        rpc.finished_subtitles(request, session_pk, new_subs.to_xml())
        language = session.language
        second_version = language.version()
        self.assertTrue(second_version.version_number > first_version.version_number)
        self.assertTrue(first_version.pk != second_version.pk)
        self.assertEquals(len(new_subs), second_version.subtitle_count)

    def test_fork_then_edit(self):
        request = RequestMockup(self.user_0)
        video = self._create_two_sub_forked_subs(request)
        version = video.subtitle_language('es').get_tip()

        time_change, text_change = version.get_changes()

        self.assertTrue(text_change > 0 and text_change <= 1)
        self.assertTrue(time_change > 0 and time_change <= 1)

    def test_fork(self):
        request = RequestMockup(self.user_0)
        session = create_two_sub_dependent_session(request)

        language = sub_models.SubtitleLanguage.objects.get(pk=session.language.pk)
        self.assertEquals(False, language.is_forked)

        # now fork subtitles
        response = rpc.start_editing(request, session.video.video_id, 'es', subtitle_language_pk=language.pk)
        subtitles = create_subtitle_set(10)
        response = rpc.finished_subtitles(request, response['session_pk'], subtitles=subtitles.to_xml(), forked=True)

        self.assertEquals('ok', response['response'])
        es = session.video.newsubtitlelanguage_set.get(language_code='es' )
        self.assertTrue(es.is_forked)
        self.assertIn('en', es.get_tip().lineage)


    def test_fork_on_finish(self):
        request = RequestMockup(self.user_0)
        session = create_two_sub_dependent_session(request)

        language = sub_models.SubtitleLanguage.objects.get(pk=session.language.pk)
        self.assertEquals(False, language.is_forked)

        # open translation dialog
        base_language_pk = session.video.subtitle_language('en').language_code
        response = rpc.start_editing(request, session.video.video_id, 'es',
                                     subtitle_language_pk=language.pk,
                                     base_language_code=base_language_pk)

        session_pk = response['session_pk']

        subtitles = create_subtitle_set(3).to_xml()

        # save as forked.
        rpc.finished_subtitles(request, session_pk, subtitles=subtitles, forked=True)

        # assert models are in correct state
        video = models.Video.objects.get(id=session.video.id)
        self.assertEquals(2, video.newsubtitlelanguage_set.count())

        es = video.subtitle_language('es')

        self.assertEquals(True, es.is_forked)
        self.assertEquals(2, es.subtitleversion_set.full().count())

        subtitles = es.get_tip().get_subtitles()
        self.assertEquals(0, subtitles[0].start_time)
        self.assertEquals(1000, subtitles[0].end_time)
        self.assertEquals(1000, subtitles[1].start_time)
        self.assertEquals(2000, subtitles[1].end_time)

    # TODO: is this right?
    def test_change_original_language_legal(self):
        request = RequestMockup(self.user_0)
        return_value = rpc.show_widget(request, VIDEO_URL, False)
        video_id = return_value['video_id']

        # first claim that the original video language is english
        # and subs are in spanish.
        return_value = rpc.start_editing(request, video_id, 'es', original_language_code='en')
        session_pk = return_value['session_pk']

        rpc.finished_subtitles(request, session_pk, create_subtitle_set().to_xml())
        rpc.show_widget(request, VIDEO_URL, False)

        # now claim that spanish is the original language
        es_sl = models.Video.objects.get(video_id=video_id).subtitle_language('es')
        return_value = rpc.start_editing(request, video_id, 'es',
                                         subtitle_language_pk=es_sl.pk,
                                         original_language_code='es')

        session_pk = return_value['session_pk']

        rpc.finished_subtitles(request, session_pk, create_subtitle_set().to_xml())
        video = Video.objects.get(video_id=video_id)

        # even if you specify a new original language, we won't change the
        # original language.
        self.assertEquals('en', video.primary_audio_language_code)

    def test_only_one_version(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_version(request)
        self.assertEquals(1, session.video.newsubtitlelanguage_set.count())

    def test_only_one_video_url(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_version(request)
        self.assertEquals(1, session.video.videourl_set.count())

    def test_only_one_yt_video_url(self):
        request = RequestMockup(self.user_0)
        return_value = rpc.show_widget(
            request,
            'http://www.youtube.com/watch?v=MJRF8xGzvj4',
            False)
        video = models.Video.objects.get(video_id=return_value['video_id'])
        self.assertEquals(1, video.videourl_set.count())

    def test_autoplay_for_non_finished(self):
        request = RequestMockup(self.user_0)
        self._start_editing(request)

        # request widget with English subtitles preloaded. The widget
        # expected null subtitles in response when the language only
        # has a draft.
        return_value = rpc.show_widget(request, VIDEO_URL, False, base_state = { 'language': 'en' })
        subtitles = SubtitleSet('en', return_value['subtitles'])

        # this was None before, now it's 0 because we are actually always sending a dfpx file (even if empty).
        self.assertEquals(len(subtitles), 0)

    def test_ensure_language_locked_on_regain_lock(self):
        request = RequestMockup(self.user_0)
        session = self._start_editing(request)

        now = datetime.now().replace(microsecond=0) + timedelta(seconds=20)
        sub_models.datetime = FakeDatetime(now)

        response = rpc.regain_lock(request, session.pk)
        self.assertEquals('ok', response['response'])

        video = models.Video.objects.get(pk=session.video.pk)
        language = video.subtitle_language()

        self.assertEquals(now, language.writelock_time)

        models.datetime = datetime

    def test_title_and_description_from_video(self):
        request = RequestMockup(self.user_0)
        video = Video.objects.all()[0]
        title = "a title"
        description = 'something'
        video.title = title
        video.description = description
        video.save()
        lang = sub_models.SubtitleLanguage(language_code='en', video=video)
        lang.save()
        response = rpc.start_editing(
            request, video.video_id, 'en', subtitle_language_pk=lang.pk)
        self.assertEquals(response['subtitles']['title'], title)
        self.assertEquals(response['subtitles']['description'], description)

    def test_create_translation_dependent_on_dependent(self):
        request = RequestMockup(self.user_0)
        session = create_two_sub_dependent_session(request)
        response = rpc.start_editing(
            request, session.video.video_id, 'fr',
            base_language_code=session.language.language_code)

        session_pk = response['session_pk']
        orig_subs = SubtitleSet('en', response['original_subtitles']['subtitles'])

        self.assertEqual(3, len(orig_subs))

        rpc.finished_subtitles(request, session_pk, create_subtitle_set().to_xml())

        response = rpc.show_widget(request, VIDEO_URL, False)
        lang = [r for r in response['drop_down_contents'] if r['language'] == 'fr'][0]
        subs = rpc.fetch_subtitles(request, session.video.video_id,
                                   lang['pk'])

        subs = SubtitleSet('fr', subs['subtitles'])
        self.assertEqual(1, len(subs))
        self.assertEqual('hey you 0', subs[0].text)
        self.assertEqual(0, subs[0].start_time)
        self.assertEqual(1000, subs[0].end_time)

    def test_fork_translation_dependent_on_forked(self):
        request = RequestMockup(self.user_0)
        video = self._create_two_sub_forked_subs(request)
        response = rpc.start_editing(request, video.video_id, 'fr', base_language_code='es')
        session_pk = response['session_pk']
        rpc.finished_subtitles(request, session_pk, create_subtitle_set(2).to_xml())

        fr_sl = models.Video.objects.get(video_id=video.video_id).subtitle_language('fr')
        self.assertEquals(False, fr_sl.is_forked)

        # now fork french
        return_value = rpc.show_widget(request, VIDEO_URL, False)
        video_id = return_value['video_id']
        fr_sl = models.Video.objects.get(video_id=video_id).subtitle_language('fr')
        response = rpc.start_editing(request, video_id, 'fr', subtitle_language_pk=fr_sl.pk)
        session_pk = response['session_pk']

        subtitles = SubtitleSet('fr', response['subtitles']['subtitles'])

        self.assertEquals(3, len(subtitles))
        self.assertEquals('hey you 0', subtitles[0].text)
        self.assertEquals(0, subtitles[0].start_time)
        self.assertEquals(1000, subtitles[0].end_time)

        # update the timing on the French sub.
        updated = SubtitleSet('fr')

        updated.append_subtitle(1020, 1500, 'hey 0')
        updated.append_subtitle(2500, 3500, 'hey 1')

        rpc.finished_subtitles(request, session_pk, updated.to_xml(), forked=True)

        french_lang = models.Video.objects.get(video_id=video_id).subtitle_language('fr')
        fr_version = french_lang.get_tip()
        fr_version_subtitles = fr_version.get_subtitles()

        self.assertTrue(french_lang.is_forked)
        self.assertEquals(1020, fr_version_subtitles[0].start_time)

        spanish_lang = models.Video.objects.get(video_id=video_id).subtitle_language('es')
        es_version = spanish_lang.get_tip()
        es_version_subtitles = es_version.get_subtitles()

        self.assertEquals(True, spanish_lang.is_forked)
        self.assertEquals(500, es_version_subtitles[0].start_time)

    def test_two_subtitle_langs_can_exist(self):
        request = RequestMockup(self.user_0)

        # create es dependent on en
        session = self._create_basic_dependent_version(request)
        video = models.Video.objects.get(id=session.video.id)

        # create forked fr translations
        response = rpc.start_editing(request, session.video.video_id, 'fr')
        session_pk = response['session_pk']

        rpc.finished_subtitles(request, session_pk, create_subtitle_set().to_xml())

        # now someone tries to edit es based on fr.
        response = rpc.start_editing(request, session.video.video_id, 'es', base_language_code='fr')

        session_pk = response['session_pk']
        rpc.finished_subtitles(request, session_pk, create_subtitle_set(3).to_xml())

        sub_langs = video.newsubtitlelanguage_set.filter(language_code='es')
        self.assertEquals(1, sub_langs.count())

        # but wait, now the latest es version has fr on it's lineage.
        es_subtitle_language = sub_langs[0]
        version = es_subtitle_language.get_tip()

        self.assertTrue('fr' in version.get_lineage())
        self.assertTrue('es' in version.get_lineage())
        self.assertTrue('en' in version.get_lineage())

    def test_edit_zero_translation(self):
        request = RequestMockup(self.user_0)
        session = create_two_sub_session(request)

        # now create empty subs for a language. We can do this by
        # starting editing but not finishing. Should create a 0% language.
        response = rpc.start_editing(
            request, session.video.video_id, 'es',
            base_language_code='en')
        session_pk = response['session_pk']
        rpc.release_lock(request, session_pk)

        # now edit the language in earnest, calling finished_subtitles afterward.
        video = models.Video.objects.get(id=session.video.id)
        sl_en = video.subtitle_language('en')
        sl_es = video.subtitle_language('es')

        self.assertEquals(0, sl_es.subtitleversion_set.full().count())

        response = rpc.start_editing(
            request, video.video_id, 'es',
            subtitle_language_pk=sl_es.pk,
            base_language_code='en')
        session_pk = response['session_pk']
        # test passes if the following command executes without throwing an exception.
        response= rpc.finished_subtitles(
            request, session_pk,
            create_subtitle_set(1))

        sl_es = sub_models.SubtitleLanguage.objects.get(id=sl_es.id)
        self.assertEquals(1, sl_es.subtitleversion_set.full().count())

    def test_set_title(self):
        request = RequestMockup(self.user_0)
        session = self._create_basic_dependent_version(request)
        en_sl = session.video.subtitle_language('en')

        # user_1 opens translate dialog
        request_1 = RequestMockup(self.user_1, "b")
        rpc.show_widget(request_1, VIDEO_URL, False)
        response = rpc.start_editing(
            request_1, session.video.video_id, 'es', base_language_code=en_sl.language_code)
        session_pk = response['session_pk']
        title = 'new title'
        rpc.finished_subtitles(request_1, session_pk, new_title=title)
        language = SubtitlingSession.objects.get(id=session_pk).language
        self.assertEquals(title, language.get_title())

    def test_youtube_ei_failure(self):
        from utils.requestfactory import RequestFactory
        rf = RequestFactory()
        request = rf.get("/")
        rpc.log_youtube_ei_failure(request, "/test-page")

    def test_start_editing_null(self):
        request = RequestMockup(self.user_0)
        response = null_rpc.start_editing(request, 'sadfdsf', 'en')
        self.assertEquals(True, response['can_edit'])


    def _create_basic_version(self, request):
        return_value = rpc.show_widget(request, VIDEO_URL, 
                                       False, base_state={})
        video_id = return_value['video_id']
        response = rpc.start_editing(request, video_id, 'en', original_language_code='en')
        session_pk = response['session_pk']
        rpc.finished_subtitles(request, session_pk, create_subtitle_set().to_xml())
        return SubtitlingSession.objects.get(pk=session_pk)

    def _start_editing(self, request):
        return_value = rpc.show_widget(
            request,
            VIDEO_URL,
            False,
            base_state={})
        video_id = return_value['video_id']
        response = rpc.start_editing(
            request, video_id, 'en', original_language_code='en')
        return SubtitlingSession.objects.get(id=response['session_pk'])

    def _create_basic_dependent_version(self, request):
        session = self._create_basic_version(request)
        sl = session.language
        response = rpc.start_editing(request, sl.video.video_id, 'es', base_language_code=sl.language_code)
        session_pk = response['session_pk']
        rpc.finished_subtitles(request, session_pk, create_subtitle_set().to_xml())

        return SubtitlingSession.objects.get(pk=session_pk)

    def _create_two_sub_forked_subs(self, request):
        session = create_two_sub_dependent_session(request)
        # now fork subtitles
        response = rpc.start_editing(
            request, session.video.video_id, 'es',
            subtitle_language_pk=session.video.subtitle_language('es').pk)

        session_pk = response['session_pk']

        subtitle_set = SubtitleSet('es')
        subtitle_set.append_subtitle(500, 1500, 'hey')
        subtitle_set.append_subtitle(1600, 2500, 'you')

        rpc.finished_subtitles(request, session_pk, subtitle_set.to_xml(), forked=True)
        return Video.objects.get(pk=session.video.pk)

    def test_edit_cicle_creates_only_one_version(self):
        '''
        After starting and finishing a subtitling session we should
        end up with one additional subtitle version, no more, no less.
        '''
        request = RequestMockup(self.user_1, "b")
        initial_count = sub_models.SubtitleVersion.objects.count()
        return_value = rpc.show_widget(request, VIDEO_URL,
            False, base_state={})
        video_id = return_value['video_id']
        response = rpc.start_editing(request, video_id, 'en', original_language_code='en')
        self.assertEqual(sub_models.SubtitleVersion.objects.count(), initial_count)
        session_pk = response['session_pk']
        rpc.finished_subtitles(request, session_pk, create_subtitle_set().to_xml())
        self.assertEqual(sub_models.SubtitleVersion.objects.count(), initial_count +1)

def create_two_sub_session(request, completed=None):
    return_value = rpc.show_widget(request, VIDEO_URL, False)

    video_id = return_value['video_id']
    response = rpc.start_editing(request, video_id, 'en', original_language_code='en')
    session_pk = response['session_pk']

    subtitle_set = create_subtitle_set(2)

    rpc.finished_subtitles(request, session_pk, subtitle_set.to_xml(), completed=completed)

    return SubtitlingSession.objects.get(pk=session_pk)

def create_two_sub_dependent_session(request):
    session = create_two_sub_session(request)
    sl_en = session.video.subtitle_language('en')

    response = rpc.start_editing(request, session.video.video_id, 'es', base_language_code=sl_en.language_code)
    session_pk = response['session_pk']

    subtitle_set = create_subtitle_set(2)

    rpc.finished_subtitles(request, session_pk, subtitle_set.to_xml())
    return SubtitlingSession.objects.get(pk=session_pk)

def _make_packet(updated=[], inserted=[], deleted=[], packet_no=1):
    return {
        'packet_no': packet_no,
        'inserted': inserted,
        'deleted': deleted,
        'updated': updated
        }

class TestCache(TestCase):

    fixtures = ['test_widget.json']

    def setUp(self):
        self.user_0 = CustomUser.objects.get(pk=3)

    def test_get_cache_url_no_exceptions(self):
        e = None
        try:
            video_cache.get_video_urls("bad key")
        except models.Video.DoesNotExist,e:
            pass
        if e is None:
            self.fail("Bad cache key should fail")

    def test_video_id_not_empty_string(self):
        url = "http://videos-cdn.mozilla.net/serv/mozhacks/demos/screencasts/londonproject/screencast.ogv"
        cache_key = video_cache._video_id_key(url)
        video_cache.cache.set(cache_key, "", video_cache.TIMEOUT)
        video_id = video_cache.get_video_id(url)
        self.assertTrue(bool(video_id))

    def test_empty_id_show_widget(self):
        url = "http://videos-cdn.mozilla.net/serv/mozhacks/demos/screencasts/londonproject/screencast.ogv"
        cache_key = video_cache._video_id_key(url)
        video, create = Video.get_or_create_for_url(url)
        video_cache.cache.set(cache_key, "", video_cache.TIMEOUT)
        # we have a bogus url
        video_id = video_cache.get_video_id(url)
        self.assertTrue(bool(video_id))
        try:
            Video.objects.get(video_id=video_id)
        except Video.DoesNotExist:
            self.fail("Should not point to a non existing video")

    def test_cache_delete_valid_chars(self):
        # this tests depends on memcache being available
        try:
            from memcache.Client import MemcachedKeyCharacterError
        except ImportError:
            return
        request = RequestMockup(self.user_0)
        session = create_two_sub_session(request)
        video = session.video
        # make sure we have video on cache
        video_id =  video_cache.get_video_id(video.get_absolute_url(video.get_video_url()))
        self.assertEquals(video_id, video.video_id)
        self.assertTrue(bool(video_id))
        try:
            video_cache.invalidate_cache(video_id)
        except MemcachedKeyCharacterError:
            self.fail("Cache invalidation should not fail")

    def test_missing_lang_no_fail(self):
        # when sending a nonexisting lang, we should end up with the original lang, since
        # others might have been cleared and not gotten through the cache
        # we are asserting this won't raise an exception for https://www.pivotaltracker.com/story/show/15348901
        url = "http://videos-cdn.mozilla.net/serv/mozhacks/demos/screencasts/londonproject/screencast.ogv"
        cache_key = video_cache._video_id_key(url)
        video_cache.cache.set(cache_key, "", video_cache.TIMEOUT)
        video_id = video_cache.get_video_id(url)
        video_cache.get_subtitles_dict(video_id, 0, 0, lambda x: x)

class TestCaching(TestCase):
    fixtures = ['test_widget.json']

    def setUp(self):
        self.user_0 = CustomUser.objects.get(pk=3)
        self.user_1 = CustomUser.objects.get(pk=4)
        self.video_pk = 12
        video_cache.invalidate_video_id(VIDEO_URL)

    def test_get_from_cache(self):
        """
        Make sure that once the cache is warm, the number of database queries
        remains constant.
        """
        from django.db import connection

        try:
            settings.DEBUG = True

            request_0 = RequestMockup(self.user_0)
            request_1 = RequestMockup(self.user_0)
            request_2 = RequestMockup(self.user_0)

            rpc.show_widget(request_0, VIDEO_URL, False)

            rpc.show_widget(request_1, VIDEO_URL, False) 
            num = len(connection.queries)

            response = rpc.show_widget(request_2, VIDEO_URL, False)

            self.assertTrue(0 < len(response['languages']))
            self.assertTrue(0 != num)
            self.assertEquals(num, len(connection.queries))

        except Exception, e:
            raise e
        finally:
            settings.DEBUG = False


class TestFormatConvertion(TestCase):

    def setUp(self):
        self.subs = SubtitleSet(language_code='en')
        for x in range(0,10):
            self.subs.append_subtitle(
                from_ms=(x * 1000), to_ms=(x * 1000) + 1000,
                content="%s - and *italics* and **bold** and >>." % x
            )
            
    def _retrieve(self, format):
        res = self.client.post(reverse("widget:convert_subtitles"), {
            'subtitles': self.subs.to_xml(),
            'language_code': 'pt-br',
            'format': format,
        })
        self.assertEqual(res.status_code , 200)
        data = json.loads(res.content)
        self.assertNotIn('errors', data)
        parser = babelsubs.load_from(data['result'], format).to_internal()
        parsed = [x for x in parser.subtitle_items()]
        self.assertEqual(len(parsed), 10)
        return res.content, parsed


    def test_srt(self):
        raw, parsed = self._retrieve('srt')
        self.assertEqual(parsed[1], (1000, 2000, '1 - and *italics* and **bold** and >>.', {'new_paragraph': False}))

    def test_ssa(self):
        raw, parsed = self._retrieve('ssa')
        self.assertEqual(parsed[1], (1000, 2000, '1 - and *italics* and **bold** and >>.', {'new_paragraph': False}))

    def test_dfxp(self):
        raw, parsed = self._retrieve('dfxp')
        self.assertEqual(parsed[1], (1000, 2000, '1 - and *italics* and **bold** and >>.', {'new_paragraph': False}))

    def test_sbv(self):
        raw, parsed = self._retrieve('sbv')
        self.assertEqual(parsed[1], (1000, 2000, '1 - and *italics* and **bold** and >>.', {'new_paragraph': False}))

class TestLineageOnRPC(TestCase):
    def setUp(self):
        self.video = test_factories.create_video()
        self.user_0 = test_factories.create_user()

    def _edit_and_save(self, video, language_code, sset, translated_from_language_code=None):
        request = RequestMockup(self.user_0)

        response = rpc.start_editing(request, self.video.video_id,
            language_code, base_language_code=translated_from_language_code)
        session_pk = response['session_pk']
        rpc.finished_subtitles(request, session_pk, sset.to_xml())

    def test_correct_lineage(self):

        # German lineage for v1 should be en-v2
        # for ge-v2 should be en-v3

        # Create en-v1
        en_v1_sset = create_subtitle_set()

        self._edit_and_save(self.video, 'en', en_v1_sset)
        en = self.video.newsubtitlelanguage_set.get(language_code='en')
        en_v1 = en.subtitleversion_set.full().get(version_number=1)
        self.assertEquals(en_v1.lineage, dict())

        # create en-v2 with a changed timming
        en_v2_sset = create_subtitle_set(5)
        self._edit_and_save(self.video, 'en', en_v2_sset)
        en_v2 = en.subtitleversion_set.full().get(version_number=2)
        self.assertEquals(en_v2.lineage, {'en':1})

        # create ge-v1 from en-v2
        de_v1_sset = create_subtitle_set(3)
        self._edit_and_save(self.video, 'de', de_v1_sset, 'en')
        de = self.video.newsubtitlelanguage_set.get(language_code='de')
        de_v1 = de.subtitleversion_set.full().get(version_number=1)
        self.assertEquals(de_v1.lineage, {'en':2})

        # rollback the en-v2 to en-v1
        en_v3 = rollback_to(en_v1.subtitle_language.video,
            en_v1.subtitle_language.language_code,
            version_number=en_v1.version_number,
            rollback_author=self.user_0)
        # make sure this exists
        en_v3 = en.subtitleversion_set.full().get(version_number=3)

        # make sure we have the right lineages:
        de_v2_sset = create_subtitle_set()
        self._edit_and_save(self.video, 'de', de_v2_sset, 'en')
        de_v2 = de.subtitleversion_set.full().get(version_number=2)
        self.assertIn('en', de_v2.lineage)
        self.assertEquals(de_v2.lineage['en'], 3)
        self.assertEqual(en, de.get_translation_source_language())
