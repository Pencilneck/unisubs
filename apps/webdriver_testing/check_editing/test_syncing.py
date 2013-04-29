#!/usr/bin/python
# -*- coding: utf-8 -*-
from apps.webdriver_testing.webdriver_base import WebdriverTestCase
from apps.webdriver_testing import data_helpers
from apps.webdriver_testing.pages.site_pages import video_page
from apps.webdriver_testing.pages.site_pages import video_language_page
from apps.webdriver_testing.pages.editor_pages import dialogs
from apps.webdriver_testing.pages.editor_pages import unisubs_menu
from apps.webdriver_testing.pages.editor_pages import subtitle_editor 
from apps.webdriver_testing.data_factories import UserFactory
import os
import time

class TestCasePartialSync(WebdriverTestCase):
    """Tests for the Subtitle Syncing editor page.
        
    """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCasePartialSync, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.user = UserFactory.create(username = 'user')
        cls.create_modal = dialogs.CreateLanguageSelection(cls)
        cls.sub_editor = subtitle_editor.SubtitleEditor(cls)
        cls.unisubs_menu = unisubs_menu.UnisubsMenu(cls)
        cls.video_pg = video_page.VideoPage(cls)
        cls.video_language_pg = video_language_page.VideoLanguagePage(cls)

        td = {'url': ('http://qa.pculture.org/amara_tests/'
                   'Birds_short.mp4')
             }
        cls.test_video = cls.data_utils.create_video(**td)
        cls.video_pg.open_video_page(cls.test_video.video_id)
        cls.video_pg.log_in(cls.user.username, 'password')
        cls.video_pg.set_skiphowto()
        #Open the video page and sync the first 3 subs
        cls.video_pg.add_subtitles()
        cls.create_modal.create_original_subs('English', 'English')
        cls.typed_subs = cls.sub_editor.type_subs()
        cls.sub_editor.save_and_exit()

                        
    def setUp(self):
        super(TestCasePartialSync, self).setUp()
        self.video_language_pg.open_video_lang_page(self.test_video.video_id,
                                                    'en')  
        self.video_language_pg.edit_subtitles()
        self.sub_editor.continue_to_next_step()
        num_synced_subs = 3
        self.sub_editor.sync_subs(num_synced_subs)

    def tearDown(self):
        super(TestCasePartialSync, self).tearDown()
        self.video_pg.open_video_page(self.test_video.video_id)
        try:
            self.sub_editor.incomplete_alert_text()
        except:
            pass
        
    def test_display__normal(self):
        """Manually entered partially subs display in editor.

        """

        timing_list = self.sub_editor.sub_timings()
        self.logger.info( timing_list)
        #Verify synced subs are increasing
        try:
            self.assertGreater(float(timing_list[1]), float(timing_list[0]))
        except ValueError as e:
            self.fail(e)
        #Verify last sub is blank
        self.assertEqual(timing_list[-1], '')

       
    def test_save(self):
        """Manually entered partially subs are saved upon save and exit.
        
        """
        timing_list = self.sub_editor.sub_timings()
        curr_url = self.sub_editor.current_url()
        self.sub_editor.save_and_exit()
        self.sub_editor.open_page(curr_url)
        self.sub_editor.continue_to_next_step()
        #Verify sub timings are same as pre-save timings 
        self.assertEqual(timing_list, self.sub_editor.sub_timings())


    def test_download(self):
        """Manually entered partially synced subs can be download from check page.

        """
        timing_list = self.sub_editor.sub_timings()
        self.logger.info( timing_list)
        #Past Sync
        self.sub_editor.continue_to_next_step()
        #Past Description
        self.sub_editor.continue_to_next_step()
        #In Check Step - download subtitles
        saved_subs = self.sub_editor.download_subtitles()
        self.logger.info( saved_subs)
        #Verify timings are in the saved list
        time_check = timing_list[1].replace('.', ',')
        self.logger.info( time_check)
        self.assertIn(time_check, saved_subs)
            

        
class TestCaseSyncBrowserError(WebdriverTestCase):
    """Tests for the Subtitle Syncing editor page.
        
    """
    NEW_BROWSER_PER_TEST_CASE = True

    def setUp(self):
        super(TestCaseSyncBrowserError, self).setUp()
        self.data_utils = data_helpers.DataHelpers()
        self.user = UserFactory.create(username = 'user')
        self.create_modal = dialogs.CreateLanguageSelection(self)
        self.sub_editor = subtitle_editor.SubtitleEditor(self)
        self.unisubs_menu = unisubs_menu.UnisubsMenu(self)
        self.video_pg = video_page.VideoPage(self)
        self.video_language_pg = video_language_page.VideoLanguagePage(self)

        td = {'url': ('http://qa.pculture.org/amara_tests/'
                   'Birds_short.mp4')
             }
        self.test_video = self.data_utils.create_video(**td)
        self.video_pg.open_video_page(self.test_video.video_id)
        self.video_pg.log_in(self.user.username, 'password')
        self.video_pg.set_skiphowto()
        #Open the video page and sync the first 3 subs
        self.video_pg.add_subtitles()
        self.create_modal.create_original_subs('English', 'English')
        self.typed_subs = self.sub_editor.type_subs()
        self.sub_editor.continue_to_next_step()
        num_synced_subs = 3
        self.sub_editor.sync_subs(num_synced_subs)

    def test_close__abruptly(self):
        """Partially synced subs are saved when browser closes abruptly.
      
        Note: the browser needs to be open for about 80 seconds for saving.
        """
        timing_list = self.sub_editor.sub_timings()
        self.logger.info( 'sleeping for 90 seconds to initiate automatic save')
        time.sleep(90)
        self.sub_editor.open_page("")
        self.sub_editor.handle_js_alert('accept')
        time.sleep(5)
        self.video_pg.open_video_page(self.test_video.video_id)
        self.unisubs_menu.open_menu()

        self.assertEqual(self.create_modal.warning_dialog_title(), 
            'Resume editing?')

        # Resume dialog - click OK
        self.create_modal.resume_dialog_ok()
 
        #Move to the syncing screen
        self.sub_editor.continue_to_next_step()

        #Verify sub timings are same as pre-save timings 
        self.assertEqual(timing_list, self.sub_editor.sub_timings())

