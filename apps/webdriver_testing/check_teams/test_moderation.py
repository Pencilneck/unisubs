# -*- coding: utf-8 -*-
import os

from apps.webdriver_testing.webdriver_base import WebdriverTestCase
from apps.webdriver_testing.data_factories import TeamMemberFactory
from apps.webdriver_testing.data_factories import TeamContributorMemberFactory
from apps.webdriver_testing.data_factories import TeamManagerMemberFactory
from apps.webdriver_testing.data_factories import TeamVideoFactory
from apps.webdriver_testing.data_factories import WorkflowFactory
from apps.webdriver_testing.data_factories import UserFactory
from apps.webdriver_testing import data_helpers
from apps.webdriver_testing.pages.site_pages import video_page
from apps.webdriver_testing.pages.site_pages import video_language_page
from apps.webdriver_testing.pages.editor_pages import unisubs_menu
from apps.webdriver_testing.pages.editor_pages import dialogs


class TestCasePublishedVideos(WebdriverTestCase):    
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCasePublishedVideos, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.video_pg = video_page.VideoPage(cls)
        cls.video_lang_pg = video_language_page.VideoLanguagePage(cls)
        cls.menu = unisubs_menu.UnisubsMenu(cls)
        cls.create_modal = dialogs.CreateLanguageSelection(cls)


        cls.user = UserFactory(username = 'user', is_partner=True)
        cls.data_utils.create_user_api_key(cls.user)
        #Add a team with workflows, tasks and preferred languages
        cls.logger.info('setup: Create a team with tasks enabled')
        cls.team = TeamMemberFactory.create(team__workflow_enabled=True,
                                            team__translate_policy=20,
                                            team__subtitle_policy=20,
                                            user = cls.user,
                                            ).team
        cls.team_workflow = WorkflowFactory(team = cls.team,
                                            autocreate_subtitle=True,
                                            autocreate_translate=True,
                                            approve_allowed = 10,
                                            review_allowed = 10,
                                           )
        cls.member = TeamContributorMemberFactory.create(
                team = cls.team,
                user = UserFactory(username='member')
                ).user
        cls.nonmember = UserFactory()

        #Add video to team with published subtitles
        cls.logger.info('Setup: Add video to team with published subs.')
        vid = cls.data_utils.create_video()
        cls.data_utils.upload_subs(vid)
        cls.published = TeamVideoFactory.create(
                team=cls.team, 
                video=vid,
                added_by=cls.user).video

        cls.video_pg.open_video_page(cls.published.video_id)
        cls.video_pg.set_skiphowto()


    def setUp(self):
        self.team.subtitle_policy=20
        self.team.save()
        self.team.translate_policy=20
        self.team.save()


    def test_subtitleme(self):
        """Subtitle Me button displayed on published transcript. """
        self.video_pg.open_video_page(self.published.video_id)
        self.assertTrue(self.video_pg.displays_subtitle_me())

    def test_video__add_subtitles(self):
        """No Add Subtitles option in the video view for moderated videos"""

        self.video_pg.open_video_page(self.published.video_id)
        self.assertFalse(self.video_pg.displays_add_subtitles())

    def test_video__upload_subtitles(self):
        """No Upload Subtitles option in the video view for moderated videos"""

        self.video_pg.open_video_page(self.published.video_id)
        self.assertFalse(self.video_pg.displays_upload_subtitles())

    def test_video__add_translation(self):
        """No Add Translation in the video view for moderated videos"""

        self.video_pg.open_video_page(self.published.video_id)
        self.assertFalse(self.video_pg.displays_add_translation())

    def test_playback(self):
        """Published version can be played on the video page."""
        self.video_pg.open_video_page(self.published.video_id)
        self.video_pg.log_in(self.member, 'password')
        self.menu.open_menu()
        self.menu.select_language('English')
        self.assertEqual('English', self.menu.visible_menu_text())

    def test_published__guest_display(self):
        """Published version is visible to guests in subtitle view"""
        self.video_pg.open_video_page(self.published.video_id)
        self.video_lang_pg.open_video_lang_page(self.published.video_id, 'en')
        self.assertTrue(self.video_lang_pg.displays_subtitles())

    def test_published__nonmember_display(self):
        """Published version is visible to non-members in subtitle view"""
        self.video_pg.open_video_page(self.published.video_id)
        self.video_pg.log_in(self.nonmember.username, 'password')
        self.video_lang_pg.open_video_lang_page(self.published.video_id, 'en')
        self.assertTrue(self.video_lang_pg.displays_subtitles())

    def test_sub_policy_members__guest(self):
        """Subtitle policy: members, guest has no improve subtitles in menu."""
        self.video_pg.open_video_page(self.published.video_id)
        self.menu.open_menu()
        self.assertFalse(self.menu.displays_improve_subtitles())

    def test_trans_policy_members__guest(self):
        """Translate policy: members, guest has no new translation in menu.

        """
        self.video_pg.log_out()
        self.video_pg.open_video_page(self.published.video_id)
        self.menu.open_menu()
        self.assertFalse(self.menu.displays_new_translation())
        self.assertTrue(self.menu.displays_moderated_message())


    def test_sub_policy_members__nonmember(self):
        """Subtitle policy: members, non-member has no improve subtitles menu.

        """
        self.video_pg.log_in(self.nonmember.username, 'password')
        self.video_pg.open_video_page(self.published.video_id)
        self.menu.open_menu()
        self.assertFalse(self.menu.displays_improve_subtitles())

    def test_trans_policy_members__nonmember(self):
        """Translate policy: members, non-member has no new translation menu.

        """
        self.video_pg.log_in(self.nonmember.username, 'password')
        self.video_pg.open_video_page(self.published.video_id)
        self.menu.open_menu()
        self.assertFalse(self.menu.displays_new_translation())

    def test_trans_policy_members__member(self):
        """Translate policy: members, member has new translation menu."""

        self.video_pg.log_in(self.member.username, 'password')
        self.video_pg.open_video_page(self.published.video_id)
        self.menu.open_menu()
        self.assertTrue(self.menu.displays_new_translation())

    def test_sub_policy_manager__member(self):
        """Subtitle policy: members, member has improve subtitles menu."""
        self.team.subtitle_policy=30
        self.team.save()
        self.video_pg.log_in(self.member.username, 'password')
        self.video_pg.open_video_page(self.published.video_id)
        self.menu.open_menu()
        self.assertFalse(self.menu.displays_improve_subtitles())

    def test_trans_policy_manager__member(self):
        """Translate policy: members, member has new translation menu."""
        self.team.translate_policy=30
        self.team.save()
        self.video_pg.log_in(self.member.username, 'password')
        self.video_pg.open_video_page(self.published.video_id)
        self.menu.open_menu()
        self.assertFalse(self.menu.displays_new_translation())


class TestCaseDraftVideos(WebdriverTestCase):    
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseDraftVideos, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.video_pg = video_page.VideoPage(cls)
        cls.video_lang_pg = video_language_page.VideoLanguagePage(cls)
        cls.menu = unisubs_menu.UnisubsMenu(cls)
        cls.create_modal = dialogs.CreateLanguageSelection(cls)


        cls.user = UserFactory(username = 'user', is_partner=True)
        cls.data_utils.create_user_api_key(cls.user)
        #Add a team with workflows, tasks and preferred languages
        cls.logger.info('setup: Create a team with tasks enabled')
        cls.team = TeamMemberFactory.create(team__workflow_enabled=True,
                                            team__subtitle_policy=20,
                                            team__translate_policy=20,
                                            user = cls.user,
                                            ).team
        cls.team_workflow = WorkflowFactory(team = cls.team,
                                            autocreate_subtitle=True,
                                            autocreate_translate=True,
                                            approve_allowed = 10,
                                            review_allowed = 10,
                                           )
        cls.member = TeamContributorMemberFactory.create(
                team = cls.team,
                user = UserFactory(username='member')
                ).user
        cls.nonmember = UserFactory()

        #Add video to team with draft subtitles
        cls.logger.info('Setup: Add video to team with draft subs.')
        cls.draft = TeamVideoFactory.create(
                team=cls.team, 
                video=cls.data_utils.create_video(),
                added_by=cls.user).video
        cls.data_utils.upload_subs(
                cls.draft, data=None, 
                user=dict(username=cls.user.username, password='password'))

        cls.video_pg.open_video_page(cls.draft.video_id)
        cls.video_pg.set_skiphowto()

    def setUp(self):
        self.team.translate_policy=20
        self.team.save()
        self.video_pg.open_video_page(self.draft.video_id)


    def test_subtitleme__draft(self):
        """No Subtitle Me button in the video view for draft transcript."""

        self.assertNotIn('Subtitle Me', self.menu.visible_menu_text())


    def test_video__add_subtitles(self):
        """No Add Subtitles option in the video view for moderated videos"""

        self.assertFalse(self.video_pg.displays_add_subtitles())

    def test_video__upload_subtitles(self):
        """No Upload Subtitles option in the video view for moderated videos"""

        self.assertFalse(self.video_pg.displays_upload_subtitles())

    def test_video__add_translation(self):
        """No Add Translation in the video view for moderated videos"""

        self.assertFalse(self.video_pg.displays_add_translation())

    def test_draft__guest_display(self):
        """Draft is not visible to guests in subtitle view."""
        self.video_lang_pg.open_video_lang_page(self.draft.video_id, 'en')
        self.assertFalse(self.video_lang_pg.displays_subtitles())

    def test_draft__nonmember_display(self):
        """Draft is not visible to non-members in subtitle view."""
        self.video_pg.log_in(self.nonmember.username, 'password')
        self.video_lang_pg.open_video_lang_page(self.draft.video_id, 'en')
        self.assertFalse(self.video_lang_pg.displays_subtitles())

    def test_draft__member_display(self):
        """Draft is visible to members in subtitle view."""
        self.video_pg.log_in(self.member.username, 'password')
        self.video_lang_pg.open_video_lang_page(self.draft.video_id, 'en')
        self.assertTrue(self.video_lang_pg.displays_subtitles())

    def test_draft__playback(self):
        """Draft can not be played on the video page."""
        self.video_pg.log_in(self.member, 'password')
        self.assertFalse(self.video_pg.displays_add_subtitles())

    def test_draft__guest_improve(self):
        """Subtitle policy: members, guest has no improve subtitles in menu."""
        self.assertFalse(self.video_pg.displays_add_subtitles())

    def test_draft__translate(self):
        """Draft can not be the source for a new translation.
        
        """
        #Opening up translation permissions, otherwise the menu is hidden
        self.team.translate_policy=10
        self.team.save()
        self.video_pg.log_in(self.member, 'password')
        self.video_pg.open_video_page(self.draft.video_id)
        self.assertFalse(self.video_pg.displays_subtitle_me())

