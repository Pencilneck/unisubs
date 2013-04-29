import codecs
import os

from apps.webdriver_testing.webdriver_base import WebdriverTestCase
from apps.webdriver_testing.pages.site_pages import video_page
from apps.webdriver_testing.pages.site_pages import video_language_page
from apps.webdriver_testing import data_helpers
from apps.webdriver_testing.data_factories import UserFactory
from apps.webdriver_testing.data_factories import VideoUrlFactory
from apps.webdriver_testing.pages.editor_pages import subtitle_editor
from apps.webdriver_testing.pages.editor_pages import unisubs_menu 


class TestCaseSubtitles(WebdriverTestCase):
    """TestSuite for download subtitles from the video's lanugage page   """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseSubtitles, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.menu = unisubs_menu.UnisubsMenu(cls)

        cls.user = UserFactory.create()
        cls.video_pg = video_page.VideoPage(cls)
        cls.video_language_pg = video_language_page.VideoLanguagePage(cls)
        cls.subs_data_dir = os.path.join(os.getcwd(), 'apps', 
            'webdriver_testing', 'subtitle_data')

    def test_subs_with_markdown(self):
        """Subtitles are available for subtitles with markdown formatting.

        """
        sub_file = os.path.join(self.subs_data_dir, 'subs_with_markdown.dfxp')
        video = VideoUrlFactory().video
        data = {'language_code': 'en',
                'video': video.pk,
                'primary_audio_language_code': 'en',
                'draft': open(sub_file),
                'is_complete': True,
                'complete': 1
                }
        self.data_utils.upload_subs(video, data)
        self.video_pg.open_video_page(video.video_id)
        self.assertEqual('English', self.menu.visible_menu_text())
