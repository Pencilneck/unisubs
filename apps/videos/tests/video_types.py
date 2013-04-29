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

import datetime

from django.test import TestCase

from babelsubs.storage import SubtitleLine, SubtitleSet

from apps.auth.models import CustomUser as User
from apps.teams.models import Team, TeamVideo
from apps.subtitles import pipeline
from apps.subtitles.models import SubtitleLanguage, SubtitleVersion
from apps.videos.models import Video, VIDEO_TYPE_BRIGHTCOVE
from apps.videos.types import video_type_registrar, VideoTypeError
from apps.videos.types.base import VideoType, VideoTypeRegistrar
from apps.videos.types.bliptv import BlipTvVideoType
from apps.videos.types.brigthcove  import BrightcoveVideoType
from apps.videos.types.dailymotion import DailymotionVideoType
from apps.videos.types.flv import FLVVideoType
from apps.videos.types.htmlfive import HtmlFiveVideoType
from apps.videos.types.mp3 import Mp3VideoType
from apps.videos.types.vimeo import VimeoVideoType
from apps.videos.types.youtube import (
    YoutubeVideoType, save_subtitles_for_lang,
    _prepare_subtitle_data_for_version, add_credit, should_add_credit
)
from utils import test_utils

class YoutubeVideoTypeTest(TestCase):
    fixtures = ['test.json']

    def setUp(self):
        self.vt = YoutubeVideoType
        self.data = [{
            'url': 'http://www.youtube.com/watch#!v=UOtJUmiUZ08&feature=featured&videos=Qf8YDn9mbGs',
            'video_id': 'UOtJUmiUZ08'
        },{
            'url': 'http://www.youtube.com/v/6Z5msRdai-Q',
            'video_id': '6Z5msRdai-Q'
        },{
            'url': 'http://www.youtube.com/watch?v=woobL2yAxD4',
            'video_id': 'woobL2yAxD4'
        },{
            'url': 'http://www.youtube.com/watch?v=woobL2yAxD4&amp;playnext=1&amp;videos=9ikUhlPnCT0&amp;feature=featured',
            'video_id': 'woobL2yAxD4'
        }]
        self.shorter_url = "http://youtu.be/HaAVZ2yXDBo"

    def test_create_kwars(self):
        vt = self.vt('http://www.youtube.com/watch?v=woobL2yAxD4')
        kwargs = vt.create_kwars()
        self.assertEqual(kwargs, {'videoid': 'woobL2yAxD4'})

    def test_set_values(self):
        youtbe_url = 'http://www.youtube.com/watch?v=_ShmidkrcY0'

        video, created = Video.get_or_create_for_url(youtbe_url)
        vu = video.videourl_set.all()[:1].get()

        self.assertEqual(vu.videoid, '_ShmidkrcY0')
        self.assertTrue(video.title)
        self.assertEqual(video.duration, 79)
        self.assertTrue(video.thumbnail)

    def test_matches_video_url(self):
        for item in self.data:
            self.assertTrue(self.vt.matches_video_url(item['url']))
            self.assertFalse(self.vt.matches_video_url('http://some-other-url.com'))
            self.assertFalse(self.vt.matches_video_url(''))
            self.assertFalse(self.vt.matches_video_url('http://youtube.com/'))
            self.assertFalse(self.vt.matches_video_url('http://youtube.com/some-video/'))
            self.assertTrue(self.vt.matches_video_url(self.shorter_url))

    def test_get_video_id(self):
        for item in self.data:
            self.failUnlessEqual(item['video_id'], self.vt._get_video_id(item['url']))

    def test_shorter_format(self):
        vt = self.vt(self.shorter_url)
        self.assertTrue(vt)
        self.assertEqual(vt.video_id , self.shorter_url.split("/")[-1])

    def test_subtitles_saving(self):
        youtube_url = 'http://www.youtube.com/watch?v=L4XpSM87VUk'

        test_utils.youtube_get_subtitled_languages.return_value = [
            {'lang_code': 'en', 'name': 'My Subtitles'}
        ]
        vt = self.vt(youtube_url)
        video, created = Video.get_or_create_for_url(youtube_url)

        langs = vt.get_subtitled_languages()
        lang = None
        for candidate in langs:
            if candidate['lang_code'] == 'en':
                lang = candidate
                break
        self.assertTrue(lang, "This video must have an 'en' language whose last sub is 'Thanks'")

        save_subtitles_for_lang(lang, video.pk, video.videourl_set.all()[0].videoid)

        sl = video.subtitle_language(lang['lang_code'])

        subtitles = sl.get_tip().get_subtitles()
        self.assertTrue(len(subtitles))
        self.assertEqual(list(subtitles)[-1][2], u'English subtitles.')

    def test_data_prep(self):
        video = Video.objects.all()[0]
        subs = [
            (0, 1000, 'Hi'),
            (2000, 3000, 'How are you?'),
        ]
        new_sv = pipeline.add_subtitles(video, 'en', subs)
        content, t, code = _prepare_subtitle_data_for_version(new_sv)

        srt = "1\r\n00:00:00,000 --> 00:00:01,000\r\nHi\r\n\r\n2\r\n00:00:02,000 --> 00:00:03,000\r\nHow are you?\r\n\r\n3\r\n00:01:52,000 --> 00:01:55,000\r\nSubtitles by the Amara.org community\r\n"
        self.assertEquals(srt, content)

        self.assertEquals('', t)
        self.assertEquals('en', code)

class HtmlFiveVideoTypeTest(TestCase):
    def setUp(self):
        self.vt = HtmlFiveVideoType

    def test_type(self):
        url = 'http://someurl.com/video.ogv?val=should&val1=be#removed'
        clean_url = 'http://someurl.com/video.ogv'

        video, created = Video.get_or_create_for_url(url)
        vu = video.videourl_set.all()[:1].get()

        self.assertEqual(vu.url, clean_url)
        self.assertEqual(self.vt.video_url(vu), vu.url)

        self.assertTrue(self.vt.matches_video_url(url))
        self.assertTrue(self.vt.matches_video_url('http://someurl.com/video.ogg'))
        self.assertTrue(self.vt.matches_video_url('http://someurl.com/video.mp4'))
        self.assertTrue(self.vt.matches_video_url('http://someurl.com/video.m4v'))
        self.assertTrue(self.vt.matches_video_url('http://someurl.com/video.webm'))

        self.assertFalse(self.vt.matches_video_url('http://someurl.ogv'))
        self.assertFalse(self.vt.matches_video_url(''))
        #for this is other type
        self.assertFalse(self.vt.matches_video_url('http://someurl.com/video.flv'))
        self.assertFalse(self.vt.matches_video_url('http://someurl.com/ogv.video'))

class Mp3VideoTypeTest(TestCase):
    def setUp(self):
        self.vt = Mp3VideoType

    def test_type(self):
        url = 'http://someurl.com/audio.mp3?val=should&val1=be#removed'
        clean_url = 'http://someurl.com/audio.mp3'

        video, created = Video.get_or_create_for_url(url)
        vu = video.videourl_set.all()[:1].get()

        self.assertEqual(vu.url, clean_url)
        self.assertEqual(self.vt.video_url(vu), vu.url)

        self.assertTrue(self.vt.matches_video_url(url))

        self.assertTrue(self.vt.matches_video_url('http://someurl.com/audio.mp3'))
        self.assertFalse(self.vt.matches_video_url('http://someurl.com/mp3.audio'))

class BlipTvVideoTypeTest(TestCase):
    def setUp(self):
        self.vt = BlipTvVideoType

    def test_type(self):
        url = 'http://blip.tv/day9tv/day-9-daily-438-p3-build-orders-made-easy-newbie-tuesday-6066868'
        video, created = Video.get_or_create_for_url(url)
        vu = video.videourl_set.all()[:1].get()

        # this is the id used to embed videos
        self.assertEqual(vu.videoid, 'hdljgvKmGAI')
        self.assertTrue(video.title)
        self.assertTrue(video.thumbnail)
        self.assertTrue(vu.url)

        self.assertTrue(self.vt.matches_video_url(url))
        self.assertTrue(self.vt.matches_video_url('http://blip.tv/day9tv/day-9-daily-438-p3-build-orders-made-easy-newbie-tuesday-6066868'))
        self.assertFalse(self.vt.matches_video_url('http://blip.tv'))
        self.assertFalse(self.vt.matches_video_url(''))

    def test_video_title(self):
        url = 'http://blip.tv/day9tv/day-9-daily-100-my-life-of-starcraft-3505715'
        video, created = Video.get_or_create_for_url(url)
        #really this should be jsut not failed
        self.assertTrue(video.get_absolute_url())

    def test_creating(self):
        # this test is for ticket: https://www.pivotaltracker.com/story/show/12996607
        url = 'http://blip.tv/day9tv/day-9-daily-1-flash-vs-hero-3515432'
        video, created = Video.get_or_create_for_url(url)

class DailymotionVideoTypeTest(TestCase):
    def setUp(self):
        self.vt = DailymotionVideoType

    def test_type(self):
        url = 'http://www.dailymotion.com/video/x7u2ww_juliette-drums_lifestyle#hp-b-l'

        video, created = Video.get_or_create_for_url(url)
        vu = video.videourl_set.all()[:1].get()

        self.assertEqual(vu.videoid, 'x7u2ww')
        self.assertTrue(video.title)
        self.assertTrue(video.thumbnail)
        self.assertEqual(vu.url, 'http://dailymotion.com/video/x7u2ww')
        self.assertTrue(self.vt.video_url(vu))

        self.assertTrue(self.vt.matches_video_url(url))
        self.assertFalse(self.vt.matches_video_url(''))
        self.assertFalse(self.vt.matches_video_url('http://www.dailymotion.com'))

    def test_type1(self):
        url = u'http://www.dailymotion.com/video/edit/xjhzgb_projet-de-maison-des-services-a-fauquembergues_news'
        vt = self.vt(url)
        try:
            vt.get_metadata(vt.videoid)
            self.fail('This link should return wrong response')
        except VideoTypeError:
            pass

class FLVVideoTypeTest(TestCase):
    def setUp(self):
        self.vt = FLVVideoType

    def test_type(self):
        url = 'http://someurl.com/video.flv?val=should&val1=be#removed'
        clean_url = 'http://someurl.com/video.flv'

        video, created = Video.get_or_create_for_url(url)
        vu = video.videourl_set.all()[:1].get()

        self.assertEqual(vu.url, clean_url)
        self.assertEqual(self.vt.video_url(vu), vu.url)

        self.assertTrue(self.vt.matches_video_url(url))

        self.assertFalse(self.vt.matches_video_url('http://someurl.flv'))
        self.assertFalse(self.vt.matches_video_url(''))
        self.assertFalse(self.vt.matches_video_url('http://someurl.com/flv.video'))

    def test_blip_type(self):
        url = 'http://blip.tv/file/get/Coldguy-SpineBreakersLiveAWizardOfEarthsea210.FLV'
        video, created = Video.get_or_create_for_url(url)
        video_url = video.videourl_set.all()[0]
        self.assertEqual(self.vt.abbreviation, video_url.type)

class VimeoVideoTypeTest(TestCase):
    def setUp(self):
        self.vt = VimeoVideoType

    def test_type(self):
        url = 'http://vimeo.com/15786066?some_param=111'

        video, created = Video.get_or_create_for_url(url)
        vu = video.videourl_set.all()[:1].get()

        self.assertEqual(vu.videoid, '15786066')
        self.assertTrue(self.vt.video_url(vu))

        self.assertTrue(self.vt.matches_video_url(url))

        self.assertFalse(self.vt.matches_video_url('http://vimeo.com'))
        self.assertFalse(self.vt.matches_video_url(''))

    def test1(self):
        #For this video Vimeo API returns response with strance error
        #But we can get data from this response. See vidscraper.sites.vimeo.get_shortmem
        #So if this test is failed - maybe API was just fixed and other response is returned
        # FIXME: restablish when vimeo api is back!
        return
        url = u'http://vimeo.com/22070806'
        video, created = Video.get_or_create_for_url(url)

        self.assertNotEqual(video.title, '')
        self.assertNotEqual(video.description, '')
        vu = video.videourl_set.all()[:1].get()

        self.assertEqual(vu.videoid, '22070806')
        self.assertTrue(self.vt.video_url(vu))

class VideoTypeRegistrarTest(TestCase):
    def test_base(self):
        registrar = VideoTypeRegistrar()

        class MockupVideoType(VideoType):
            abbreviation = 'mockup'
            name = 'MockUp'

        registrar.register(MockupVideoType)
        self.assertEqual(registrar[MockupVideoType.abbreviation], MockupVideoType)
        self.assertEqual(registrar.choices[-1], (MockupVideoType.abbreviation, MockupVideoType.name))

    def test_video_type_for_url(self):
        type = video_type_registrar.video_type_for_url('some url')
        self.assertEqual(type, None)
        type = video_type_registrar.video_type_for_url('http://youtube.com/v=UOtJUmiUZ08')
        self.assertTrue(isinstance(type, YoutubeVideoType))
        return
        self.assertRaises(VideoTypeError, video_type_registrar.video_type_for_url,
                          'http://youtube.com/v=100500')

class BrightcoveVideoTypeTest(TestCase):
    def setUp(self):
        self.vt = BrightcoveVideoType

    def test_type(self):
        url  = 'http://link.brightcove.com/services/player/bcpid955357260001?bckey=AQ~~,AAAA3ijeRPk~,jc2SmUL6QMyqTwfTFhUbWr3dg6Oi980j&bctid=956115196001'
        video, created = Video.get_or_create_for_url(url)
        vu = video.videourl_set.all()[:1].get()
        self.assertTrue(vu.type ==  VIDEO_TYPE_BRIGHTCOVE == BrightcoveVideoType.abbreviation)
        self.assertTrue(self.vt.video_url(vu))
        self.assertTrue(self.vt.matches_video_url(url))

    def test_redirection(self):
        url  = 'http://bcove.me/7fa5828z'
        vt = video_type_registrar.video_type_for_url(url)
        self.assertTrue(vt)
        self.assertEqual(vt.video_id, '956115196001')


class CreditTest(TestCase):

    def setUp(self):
        original_video , created = Video.get_or_create_for_url("http://www.example.com/original.mp4")
        original_video.duration  = 10
        original_video.save()
        self.original_video = original_video
        self.language = SubtitleLanguage.objects.create(
            video=original_video, language_code='en', is_forked=True)
        self.version = pipeline.add_subtitles(
            self.original_video,
            self.language.language_code,
            [],
            created=datetime.datetime.now(),
        )

    def _sub_list_to_sv(self, subs):
        sublines = []
        for sub in subs:
            sublines.append(SubtitleLine(
                sub['start'],
                sub['end'],
                sub['text'],
                {},
            ))
        user = User.objects.all()[0]
        new_sv = pipeline.add_subtitles(
            self.original_video,
            self.language.language_code,
            sublines,
            author=user,
        )
        return new_sv

    def _subs_to_sset(self, subs):
        sset = SubtitleSet(self.language.language_code)
        for s in subs:
            sset.append_subtitle(*s)
        return sset

    def test_last_sub_not_synced(self):
        subs = [SubtitleLine(
            2 * 1000,
            None,
            'text',
            {},
        )]

        last_sub = subs[-1]

        self.assertEquals(last_sub.end_time, None)

        subs = add_credit(self.version, self._subs_to_sset(subs))
        
        self.assertEquals(last_sub.text, subs[-1].text)

    def test_straight_up_video(self):
        subs = [SubtitleLine(
            2 * 1000,
            3 * 1000,
            'text',
            {},
        )]

        subs = add_credit(self.version, self._subs_to_sset(subs))
        last_sub = subs[-1]
        self.assertEquals(last_sub.text,
                "Subtitles by the Amara.org community")
        self.assertEquals(last_sub.start_time, 7000)
        self.assertEquals(last_sub.end_time, 10 * 1000)

    def test_only_a_second_left(self):
        subs = [SubtitleLine(
            2 * 1000,
            9 * 1000,
            'text',
            {},
        )]

        subs = add_credit(self.version, self._subs_to_sset(subs))
        last_sub = subs[-1]
        self.assertEquals(last_sub.text,
                "Subtitles by the Amara.org community")
        self.assertEquals(last_sub.start_time, 9000)
        self.assertEquals(last_sub.end_time, 10 * 1000)

    def test_no_space_left(self):
        self.original_video.duration = 10
        self.original_video.save()
        subs = [SubtitleLine(
            2 * 1000,
            10 * 1000,
            'text',
            {},
        )]

        subs = add_credit(self.version, self._subs_to_sset(subs))
        self.assertEquals(len(subs), 1)
        last_sub = subs[-1]
        self.assertEquals(last_sub.text, 'text')

    def test_should_add_credit(self):
        sv = SubtitleVersion.objects.filter(
                subtitle_language__video__teamvideo__isnull=True)[0]

        self.assertTrue(should_add_credit(sv))

        video = sv.subtitle_language.video
        team, created = Team.objects.get_or_create(name='name', slug='slug')
        user = User.objects.all()[0]

        TeamVideo.objects.create(video=video, team=team, added_by=user)

        sv = SubtitleVersion.objects.filter(
                subtitle_language__video__teamvideo__isnull=False)[0]

        self.assertFalse(should_add_credit(sv))


