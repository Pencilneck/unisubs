import os

from apps.webdriver_testing.webdriver_base import WebdriverTestCase
from apps.webdriver_testing.pages.site_pages import video_page
from apps.webdriver_testing.pages.site_pages import create_page
from apps.webdriver_testing.pages.site_pages import video_language_page
from apps.webdriver_testing import data_helpers
from apps.webdriver_testing.data_factories import UserFactory
from apps.webdriver_testing.data_factories import VideoUrlFactory


class TestCaseFollowing(WebdriverTestCase):
    """TestSuite for download subtitles from the video's lanugage page   """
    NEW_BROWSER_PER_TEST_CASE = False
    FOLLOWING = u'\u2713 Following'
    NOT_FOLLOWING = 'Not Following'


    @classmethod
    def setUpClass(cls):
        super(TestCaseFollowing, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.user = UserFactory.create()
        cls.video_pg = video_page.VideoPage(cls)
        cls.video_language_pg = video_language_page.VideoLanguagePage(cls)
        cls.create_pg = create_page.CreatePage(cls)
        cls.create_pg.open_create_page()
        cls.video = cls.data_utils.create_video_with_subs()
        cls.subs_data_dir = os.path.join(os.getcwd(), 'apps', 
            'webdriver_testing', 'subtitle_data')
        cls.create_pg.open_create_page()


    def test_default__submitter_following_video(self):
        """Video submitter is following video by default.

        """
        self.create_pg.open_create_page()
        self.create_pg.log_in(self.user, 'password')
        url = 'https://www.youtube.com/watch?v=2JWUhW5yRdI'
        self.create_pg.submit_video(url)
        self.assertEqual(self.FOLLOWING, self.video_pg.follow_text())


    def test_default__subtitler_following_language(self):
        """Subtitler is set to following for language contributed.

        """
        self.video_pg.log_in(self.user, 'password')
        tv = VideoUrlFactory().video
        sub_file = os.path.join(self.subs_data_dir, 'Untimed_text.dfxp')
        self.video_pg.open_video_page(tv.video_id)
        self.video_pg.upload_subtitles('English', sub_file)
        self.video_language_pg.open_video_lang_page(tv.video_id, 'en')
        self.assertEqual(self.FOLLOWING, self.video_language_pg.follow_text())


    def test_default__subtitler_not_following_video(self):
        """Not following is setting for Video after contribution subtitles.

        """
        self.video_pg.log_in(self.user, 'password')
        tv = VideoUrlFactory().video
        sub_file = os.path.join(self.subs_data_dir, 'Untimed_text.dfxp')
        self.video_pg.open_video_page(tv.video_id)
        self.video_pg.upload_subtitles('English', sub_file)
        self.video_pg.open_video_page(tv.video_id)
        self.assertEqual(self.NOT_FOLLOWING, self.video_pg.follow_text())



    def test_default__not_following_video(self):
        """Non-contributor is not following video by default.

        """
        self.video_pg.log_in(self.user, 'password')
        self.video_pg.open_video_page(self.video.video_id)
        self.assertEqual(self.NOT_FOLLOWING, self.video_pg.follow_text())

    def test_default__not_following_language(self):
        """Non-contributor is not following language by default.

        """
        self.video_language_pg.log_in(self.user, 'password')
        self.video_language_pg.open_video_lang_page(self.video.video_id, 'en')
        self.assertEqual(self.NOT_FOLLOWING, self.video_pg.follow_text())

    def test_toggle__following_video(self):
        """Turn on and off following for a video
        """
        follower = UserFactory.create()
        self.video_pg.log_in(follower.username, 'password')
        self.video_pg.open_video_page(self.video.video_id)
        self.video_pg.toggle_follow()
        self.assertEqual(self.FOLLOWING, self.video_pg.follow_text())
        self.video_pg.toggle_follow()
        self.assertEqual(self.NOT_FOLLOWING, self.video_pg.follow_text())

    def test_toggle__following_language(self):
        """Turn on / off following for a language.

        """
        user = UserFactory.create()
        self.video_pg.log_in(user.username, 'password')
        self.video_language_pg.open_video_lang_page(self.video.video_id, 'en')
        self.video_pg.toggle_follow(lang=True)
        self.assertEqual(self.FOLLOWING, self.video_language_pg.follow_text())
        self.video_pg.toggle_follow(lang=True)
        self.assertEqual(self.NOT_FOLLOWING, self.video_language_pg.follow_text())

    def test_toggle_video__lang_unchanged(self):
        """Turn on following for a video, does not change languages.

        """
        follower = UserFactory.create()
        self.video_pg.log_in(follower.username, 'password')
        self.video_pg.open_video_page(self.video.video_id)
        self.video_pg.toggle_follow()
        self.assertEqual(self.FOLLOWING, self.video_pg.follow_text())
        self.video_language_pg.open_video_lang_page(self.video.video_id, 'en')
        self.assertEqual(self.NOT_FOLLOWING, self.video_language_pg.follow_text())

    def test_toggle_lang__video_unchanged(self):
        """Turn on / off following for a language does not change video setting.

        """
        user = UserFactory.create()
        self.video_pg.log_in(user.username, 'password')
        self.video_language_pg.open_video_lang_page(self.video.video_id, 'en')
        self.video_pg.toggle_follow(lang=True)
        self.assertEqual(self.FOLLOWING, self.video_language_pg.follow_text())
        self.video_pg.open_video_page(self.video.video_id)
        self.assertEqual(self.NOT_FOLLOWING, self.video_language_pg.follow_text())
