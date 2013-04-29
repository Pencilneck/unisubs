#!/usr/bin/python
# -*- coding: utf-8 -*-
from apps.webdriver_testing.webdriver_base import WebdriverTestCase
from apps.webdriver_testing.pages.site_pages import watch_page
from apps.webdriver_testing.pages.site_pages import video_page
from apps.webdriver_testing.pages.site_pages import search_results_page
from apps.webdriver_testing.data_factories import UserFactory 
from apps.webdriver_testing.data_factories import VideoFactory 
from apps.webdriver_testing import data_helpers
from django.core import management
import datetime
import time
import os

class TestCaseWatchPageSearch(WebdriverTestCase):
    """TestSuite for site video searches.  """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseWatchPageSearch, cls).setUpClass()
        management.call_command('update_index', interactive=False)
        cls.watch_pg = watch_page.WatchPage(cls)
        cls.data = data_helpers.DataHelpers()
        testdata = {'url': 'http://www.youtube.com/watch?v=WqJineyEszo',
                    'video__title': ('X Factor Audition - Stop Looking At My '
                                    'Mom Rap - Brian Bradley'),
                    'type': 'Y'
                   }

        video = cls.data.create_video(**testdata)
        cls.data.upload_subs(video)
        
        cls.data.create_videos_with_fake_subs('apps/webdriver_testing/'
                                         'subtitle_data/fake_subs.json')
        VideoFactory.create(title = u'不过这四个问题')
        video = VideoFactory.create(title = "my test vid")
        data = {
                'language_code': 'zh-cn',
                'video_language': 'zh-cn',
                'video': video.pk,
                'draft': open('apps/webdriver_testing/subtitle_data/'
                              'Timed_text.zh-cn.sbv'),
                'is_complete': True
               }
        test_video = cls.data.create_video_with_subs(video_url = 
                       "http://unisubs.example.com/test_nonascii.mp4",
                       data = data)
        management.call_command('update_index', interactive=False)



    def setUp(self):
        super(TestCaseWatchPageSearch, self).setUp()
        self.watch_pg.open_watch_page()
        
    def test_search__simple(self):
        """Search for text contained in video title.

        """
        test_text = 'X factor'
        results_pg = self.watch_pg.basic_search(test_text)
        self.assertTrue(results_pg.search_has_results())

    def test_search__subs_nonascii(self):
        """Search for sub content with non-ascii char strings.
 
        """
        test_text = u'不过这四个问题'
        results_pg = self.watch_pg.basic_search(test_text)
        self.assertTrue(results_pg.search_has_results())

    def test_search__title_nonascii(self):
        """Search title content with non-ascii char strings.
 
        """
        
        #Search for: chinese chars by opening entering the text 
        #via javascript because webdriver can't type those characters.
        self.browser.execute_script("document.getElementsByName"
                               "('q')[1].value='不过这四个问题'")
        results_pg = self.watch_pg.advanced_search()
        self.assertTrue(results_pg.search_has_results())
       

    def test_search__sub_content(self):
        """Search contents in subtitle text.

        """
        test_text = '[Zeus]'
        results_pg = self.watch_pg.basic_search(test_text)
        self.assertTrue(results_pg.search_has_results())

    def test_search__video_lang(self):
        """Search for videos by video language.
 
        """
        results_pg = self.watch_pg.advanced_search(orig_lang='English')
        self.assertTrue(results_pg.page_has_video(
            'original english with incomplete pt'))
        self.assertEqual(2, len(results_pg.page_videos()))

    def test_search__trans_lang(self):
        """Search for videos by translations language.
 
        """
        results_pg = self.watch_pg.advanced_search(trans_lang='Portuguese')
        self.assertTrue(results_pg.page_has_video(
            'original english with incomplete pt'))
        self.assertEqual(1, len(results_pg.page_videos()))

    def test_search__trans_and_video_lang(self):
        """Search for videos by video lang and translations language.
 
        """
        results_pg = self.watch_pg.advanced_search(orig_lang = 'English', 
            trans_lang='Portuguese')
        self.assertTrue(results_pg.page_has_video(
            'original english with incomplete pt'))
        self.assertEqual(1, len(results_pg.page_videos()))

    def test_search__text_trans_video(self):
        """Search for videos by text, video lang and translation.
 
        """
        self.browser.execute_script("document.getElementsByName('q')[1].value='subs'")
        results_pg = self.watch_pg.advanced_search(
            orig_lang = 'Arabic', 
            trans_lang='English')
        self.assertTrue(results_pg.page_has_video(
            'original ar with en complete subs'))
        self.assertEqual(1, len(results_pg.page_videos()))


class TestCaseWatchPageListings(WebdriverTestCase):
    """TestSuite for watch page latest videos section.  """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseWatchPageListings, cls).setUpClass()
        management.call_command('clear_index', interactive=False)

        cls.watch_pg = watch_page.WatchPage(cls)
        cls.data = data_helpers.DataHelpers()
        cls.data.create_videos_with_fake_subs('apps/webdriver_testing/subtitle_data/fake_subs.json')

        #create a video and mark as featured.
        cls.feature_vid = cls.data.create_video_with_subs(video_url = 
                                        "http://vimeo.com/903633")
        cls.feature_vid.featured=datetime.datetime.now()
        cls.feature_vid.save()
       
        #update solr index
        management.call_command('update_index', interactive=False)

        cls.expected_videos = [ 'original ar with en complete subs',
                                 'original english with incomplete pt', 
                                 'original pt-br incomplete 4 lines', 
                                 'original russian with pt-br subs',
                                 'original swa incomplete 2 lines' ]

    def setUp(self):
        super(TestCaseWatchPageListings, self).setUp()
        #Open the watch page as a test starting point.
        self.watch_pg.open_watch_page()

    def test_latest__section(self):
        """Latest section displays the expected videos.

        """
        video_list = self.watch_pg.section_videos(section='latest')
        for vid in self.expected_videos:
            self.assertIn(vid, video_list)


    def test_latest__page(self):
        """Latest page opens when 'More' clicked and displays videos.

        """
        self.watch_pg.display_more(section='latest')
        self.watch_pg.search_complete()
        video_list = self.watch_pg.section_videos(section='featured')
        for vid in self.expected_videos:
            self.assertIn(vid, video_list)

    def test_popular__section(self):
        """Popular section displays expected videos.

        """
        video_list = self.watch_pg.section_videos(section='popular')
        for vid in self.expected_videos:
            self.assertIn(vid, video_list)

    def test_popular__default_week(self):
        """Sort by week is the default sort value.

        """
        default_sort = self.watch_pg.popular_current_sort()
        self.assertEqual('This Week', default_sort)

    def test_popular__sort_year(self):
        """Sort by year displays correct value and link with sort parameter.

        """
        self.watch_pg.popular_sort('year')
        self.assertEqual('This Year', self.watch_pg.popular_current_sort())
        self.assertIn('sort=year', self.watch_pg.popular_more_link())


    def test_popular__sort_today(self):
        """Sort by today displays correct value and link with sort parameter.

        """
        self.watch_pg.popular_sort('today')
        self.assertEqual('Today', self.watch_pg.popular_current_sort())
        self.assertIn('sort=today', self.watch_pg.popular_more_link())

    def test_popular__sort_alltime(self):
        """Sort by alltime displays correct value and link with sort parameter.

        """
        self.watch_pg.popular_sort('total')
        self.assertEqual('All Time', self.watch_pg.popular_current_sort())
        self.assertIn('sort=total', self.watch_pg.popular_more_link())

    def test_popular__sort_month(self):
        """Sort by month displays correct value and link with sort parameter.

        """
        self.watch_pg.popular_sort('month')
        self.assertEqual('This Month', self.watch_pg.popular_current_sort())
        self.assertIn('sort=month', self.watch_pg.popular_more_link())


    def test_popular__page(self):
        """Popular page opens when 'More' clicked and displays videos.

        """
        self.watch_pg.display_more(section='popular')
        video_list = self.watch_pg.section_videos(section='popular')
        for vid in self.expected_videos:
            self.assertIn(vid, video_list)


    def test_featured__section(self):
        """Featured section only displays featured videos.

        """
        video_list = self.watch_pg.section_videos(section='featured')
        self.assertEqual([self.feature_vid.title], video_list)

    def test_featured__page(self):
        """Featured page opens when 'More' clicked and displays videos.

        """
        self.watch_pg.display_more(section='featured')
        video_list = self.watch_pg.section_videos(section='featured')
        self.assertEqual([self.feature_vid.title], video_list)
