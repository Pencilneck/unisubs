import os
import time

from django.core import management

from apps.webdriver_testing.webdriver_base import WebdriverTestCase
from apps.webdriver_testing.pages.site_pages import video_page
from apps.webdriver_testing.pages.site_pages import video_language_page
from apps.webdriver_testing.pages.site_pages import watch_page
from apps.webdriver_testing import data_helpers
from apps.webdriver_testing.data_factories import UserFactory
from apps.webdriver_testing.data_factories import VideoUrlFactory
from apps.webdriver_testing.pages.editor_pages import subtitle_editor
from apps.webdriver_testing.pages.editor_pages import unisubs_menu 
from apps.webdriver_testing.data_factories import TeamVideoFactory
from apps.webdriver_testing.data_factories import TeamMemberFactory
from apps.webdriver_testing.data_factories import TeamAdminMemberFactory
from apps.webdriver_testing.data_factories import TeamContributorMemberFactory
from apps.webdriver_testing.data_factories import WorkflowFactory
from apps.webdriver_testing.data_factories import TeamLangPrefFactory
from apps.webdriver_testing.data_factories import UserLangFactory
from apps.webdriver_testing.pages.site_pages.teams.tasks_tab import TasksTab
from apps.webdriver_testing.pages.site_pages.teams.videos_tab import VideosTab
from apps.webdriver_testing.pages.editor_pages import dialogs
from apps.webdriver_testing.pages.editor_pages import subtitle_editor

class TestCaseUnpublishLast(WebdriverTestCase):
    """TestSuite for Unapprove / Delete last version of language.  """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseUnpublishLast, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.create_modal = dialogs.CreateLanguageSelection(cls)
        cls.sub_editor = subtitle_editor.SubtitleEditor(cls)
        cls.tasks_tab = TasksTab(cls)
        cls.video_pg = video_page.VideoPage(cls)
        cls.watch_pg = watch_page.WatchPage(cls)
        cls.user = UserFactory.create()
        cls.owner = UserFactory.create()
        cls.team = TeamMemberFactory.create(team__workflow_enabled=True,
                                            team__translate_policy=20, #any team
                                            team__subtitle_policy=20, #any team
                                            team__task_assign_policy=10, #any team
                                            user = cls.owner,
                                            ).team
        cls.workflow = WorkflowFactory(team = cls.team,
                                       autocreate_subtitle=True,
                                       autocreate_translate=True,
                                       approve_allowed = 10, # manager
                                       review_allowed = 10, # peer
                                       )
        lang_list = ['en', 'ru', 'pt-br', 'de', 'sv']
        for language in lang_list:
            TeamLangPrefFactory.create(team=cls.team, language_code=language,
                                       preferred=True)

        cls.admin = TeamAdminMemberFactory(team=cls.team).user
        cls.contributor = TeamMemberFactory(team=cls.team).user
        cls.subs_dir = os.path.join(os.getcwd(), 'apps', 'webdriver_testing', 
                                    'subtitle_data') 
        cls.video, cls.tv = cls.create_source_with_multiple_revisions()
        translation = os.path.join(cls.subs_dir, 'Timed_text.sv.dfxp')
        
        #Upload subs - sv - incomplete, de - reviewed, ru - complete needs review
        cls.logger.info("""Uploading subs to get tasks in various stages: """)
        cls.logger.info("""
                         sv: translation started, incomplete
                         ru: translation submitted, needs review
                         de: translation reviewed, needs approve
                         pt-br: not started
                         """)

        cls._upload_lang(cls.video, translation, 'sv', cls.contributor)
        cls._upload_lang(cls.video, translation, 'de', cls.contributor,
                         complete=True)
        cls.data_utils.complete_review_task(cls.tv, 20, cls.admin)
        cls._upload_lang(cls.video, translation, 'ru', cls.contributor,
                         complete=True)

        cls.logger.info('Setting visibility override on v3 to private')
        cls.en = cls.video.subtitle_language('en')
        en_v3 = cls.en.get_tip(full=True)
        en_v3.visibility_override = 'private'
        en_v3.save() 
        cls.tasks_tab.open_page('teams/%s/tasks/?lang=all&assignee=anyone'
                                 % cls.team.slug)
 


    def tearDown(self):
        self.tasks_tab.open_team_page(self.team.slug)
        self.tasks_tab.handle_js_alert('accept')


    @classmethod
    def _upload_lang(cls, video, subs, lc, user, complete=False):
        auth_creds = dict(username=user.username, password='password')
        draft_data = {'language_code': lc,
                     'video': video.pk,
                     'draft': open(subs),
                     'complete': int(complete),
                     'is_complete': complete,
                    }
        if lc == 'en':
            draft_data['primary_audio_language_code'] = 'en'
        cls.data_utils.upload_subs(video, draft_data, user=auth_creds)

    @classmethod
    def _add_team_video(cls):
        video = cls.data_utils.create_video()
        tv = TeamVideoFactory(team=cls.team, added_by=cls.owner, video=video)
        return video, tv

    @classmethod
    def create_source_with_multiple_revisions(cls):
        cls.logger.info("Create a team video with 4 revisions:")
        cls.logger.info("""
                            v1: private (draft version only)
                            v2: private (draft version only)
                            v3: public 
                        """)
        video, tv = cls._add_team_video()

        #REV1 (draft)
        rev1_subs = os.path.join(cls.subs_dir, 'Timed_text.en.srt')
        cls._upload_lang(video, rev1_subs, 'en', user=cls.contributor)

        #REV2 (draft)
        rev2_subs = os.path.join(cls.subs_dir, 'Timed_text.rev2.en.srt')
        cls._upload_lang(video, rev2_subs, 'en', 
                             user=cls.contributor, complete=True)

        #REV3, reviewed and approved (public)
        rev3_subs = os.path.join(cls.subs_dir, 'Timed_text.rev3.en.srt')
        cls._upload_lang(video, rev3_subs, 'en', user=cls.admin, 
                             complete=True)
        cls.data_utils.complete_review_task(tv, 20, cls.admin)
        cls.data_utils.complete_approve_task(tv, 20, cls.owner)
        return video, tv

    def test_unpublish_last__perform_review(self):
        """Deleting last source can review

        """
        self.tasks_tab.log_in(self.owner, 'password')
        self.tasks_tab.open_page('teams/%s/tasks/?lang=ru&assignee=anyone'
                                 % self.team.slug)

        self.tasks_tab.perform_and_assign_task('Review Russian Subtitles', 
                                               self.video.title)
        self.assertEqual('Review subtitles', self.sub_editor.dialog_title())
        self.sub_editor.continue_to_next_step() #to subtitle info 
        self.sub_editor.complete_review(result='Accept')
        self.sub_editor.mark_subs_complete()
        self.sub_editor.click_saved_ok()
        self.assertTrue(self.tasks_tab.task_present('Approve Russian Subtitles',
                                           self.video.title))

    def test_unpublish_last__perform_approve(self):
        """Deleting last source can approve
        """
        self.tasks_tab.log_in(self.owner, 'password')
        self.tasks_tab.open_page('teams/%s/tasks/?lang=de&assignee=anyone'
                                 % self.team.slug)

        self.tasks_tab.perform_and_assign_task('Approve German Subtitles', 
                                               self.video.title)
        self.assertEqual('Approve subtitles', self.sub_editor.dialog_title())
        self.sub_editor.continue_to_next_step() #to subtitle info 
        self.sub_editor.complete_approve(result='Approve')
        self.sub_editor.mark_subs_complete()
        self.sub_editor.click_saved_ok()
        self.assertTrue(self.video.subtitle_language('de').get_tip(public=True))
        self.tasks_tab.open_page('teams/%s/tasks/?lang=all&assignee=anyone'
                                 % self.team.slug)
        self.assertFalse(self.tasks_tab.task_present(
                        'Approve German Subtitles', self.video.title))


    def test_unpublish__edit_forked_translation(self):
        """In-progress translations editable after last source deleted.

        """
        self.tasks_tab.log_in(self.contributor.username, 'password')
        self.tasks_tab.open_page('teams/{0}/tasks/?team_video={1}'
                                 '&assignee=anyone&lang=sv'.format(
                                 self.team.slug, self.tv.pk))

        task_text = 'Translate Subtitles into Swedish'
        self.tasks_tab.perform_assigned_task(task_text, self.video.title)
        self.assertEqual('Typing', self.sub_editor.dialog_title())


    def test_unpublish__revision_not_searchable(self):
        """Unpublished (deleted) revision text doesn't show in search results.

        """
        self.watch_pg.log_out()
        management.call_command('update_index', interactive=False)

        self.watch_pg.open_watch_page()
        test_text = 'This is revision 3'
        results_pg = self.watch_pg.basic_search(test_text)
        self.assertTrue(results_pg.search_has_no_results())



class TestCaseDeleteLast(WebdriverTestCase):
    """TestSuite for Unapprove / Delete last version of language.  """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseDeleteLast, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.create_modal = dialogs.CreateLanguageSelection(cls)
        cls.sub_editor = subtitle_editor.SubtitleEditor(cls)
        cls.tasks_tab = TasksTab(cls)
        cls.video_pg = video_page.VideoPage(cls)
        cls.watch_pg = watch_page.WatchPage(cls)
        cls.user = UserFactory.create()
        cls.owner = UserFactory.create()
        cls.team = TeamMemberFactory.create(team__workflow_enabled=True,
                                            team__translate_policy=20, #any team
                                            team__subtitle_policy=20, #any team
                                            team__task_assign_policy=10, #any team
                                            user = cls.owner,
                                            ).team
        cls.workflow = WorkflowFactory(team = cls.team,
                                       autocreate_subtitle=True,
                                       autocreate_translate=True,
                                       approve_allowed = 10, # manager
                                       review_allowed = 10, # peer
                                       )
        lang_list = ['en', 'ru', 'pt-br', 'de', 'sv']
        for language in lang_list:
            TeamLangPrefFactory.create(team=cls.team, language_code=language,
                                       preferred=True)

        cls.admin = TeamAdminMemberFactory(team=cls.team).user
        cls.contributor = TeamMemberFactory(team=cls.team).user
        cls.subs_dir = os.path.join(os.getcwd(), 'apps', 'webdriver_testing', 
                                    'subtitle_data') 
        cls.video, cls.tv = cls.create_source_with_multiple_revisions()
        translation = os.path.join(cls.subs_dir, 'Timed_text.sv.dfxp')
        
        #Upload subs - sv - incomplete, de - reviewed, ru - complete needs review
        cls.logger.info("""Uploading subs to get tasks in various stages: """)
        cls.logger.info("""
                         sv: translation started, incomplete
                         ru: translation submitted, needs review
                         de: translation reviewed, needs approve
                         pt-br: not started
                         """)

        cls._upload_lang(cls.video, translation, 'sv', cls.contributor)
        cls._upload_lang(cls.video, translation, 'de', cls.contributor,
                         complete=True)
        cls.data_utils.complete_review_task(cls.tv, 20, cls.admin)
        cls._upload_lang(cls.video, translation, 'ru', cls.contributor,
                         complete=True)

        cls.logger.info('Setting visibility override on v3 to private')
        cls.en = cls.video.subtitle_language('en')
        en_v3 = cls.en.get_tip(full=True)
        en_v3.visibility_override = 'deleted'
        en_v3.save() 
        cls.tasks_tab.open_page('teams/%s/tasks/?lang=all&assignee=anyone'
                                 % cls.team.slug)
 


    def tearDown(self):
        self.tasks_tab.open_team_page(self.team.slug)
        self.tasks_tab.handle_js_alert('accept')


    @classmethod
    def _upload_lang(cls, video, subs, lc, user, complete=False):
        auth_creds = dict(username=user.username, password='password')
        draft_data = {'language_code': lc,
                     'video': video.pk,
                     'draft': open(subs),
                     'complete': int(complete),
                     'is_complete': complete,
                    }
        if lc == 'en':
            draft_data['primary_audio_language_code'] = 'en'
        cls.data_utils.upload_subs(video, draft_data, user=auth_creds)

    @classmethod
    def _add_team_video(cls):
        video = cls.data_utils.create_video()
        tv = TeamVideoFactory(team=cls.team, added_by=cls.owner, video=video)
        return video, tv

    @classmethod
    def create_source_with_multiple_revisions(cls):
        cls.logger.info("Create a team video with 4 revisions:")
        cls.logger.info("""
                            v1: private (draft version only)
                            v2: private (draft version only)
                            v3: public 
                        """)
        video, tv = cls._add_team_video()

        #REV1 (draft)
        rev1_subs = os.path.join(cls.subs_dir, 'Timed_text.en.srt')
        cls._upload_lang(video, rev1_subs, 'en', user=cls.contributor)

        #REV2 (draft)
        rev2_subs = os.path.join(cls.subs_dir, 'Timed_text.rev2.en.srt')
        cls._upload_lang(video, rev2_subs, 'en', 
                             user=cls.contributor, complete=True)

        #REV3, reviewed and approved (public)
        rev3_subs = os.path.join(cls.subs_dir, 'Timed_text.rev3.en.srt')
        cls._upload_lang(video, rev3_subs, 'en', user=cls.admin, 
                             complete=True)
        cls.data_utils.complete_review_task(tv, 20, cls.admin)
        cls.data_utils.complete_approve_task(tv, 20, cls.owner)
        return video, tv

    def test_delete_last__perform_review(self):
        """Deleting last source can review

        """
        self.tasks_tab.log_in(self.owner, 'password')
        self.tasks_tab.open_page('teams/%s/tasks/?lang=ru&assignee=anyone'
                                 % self.team.slug)

        self.tasks_tab.perform_and_assign_task('Review Russian Subtitles', 
                                               self.video.title)
        self.assertEqual('Review subtitles', self.sub_editor.dialog_title())
        self.sub_editor.continue_to_next_step() #to subtitle info 
        self.sub_editor.complete_review(result='Accept')
        self.sub_editor.mark_subs_complete()
        self.sub_editor.click_saved_ok()
        self.assertTrue(self.tasks_tab.task_present('Approve Russian Subtitles',
                                           self.video.title))

    def test_delete_last__perform_approve(self):
        """Deleting last source can approve
        """
        self.tasks_tab.log_in(self.owner, 'password')
        self.tasks_tab.open_page('teams/%s/tasks/?lang=de&assignee=anyone'
                                 % self.team.slug)

        self.tasks_tab.perform_and_assign_task('Approve German Subtitles', 
                                               self.video.title)
        self.assertEqual('Approve subtitles', self.sub_editor.dialog_title())
        self.sub_editor.continue_to_next_step() #to subtitle info 
        self.sub_editor.complete_approve(result='Approve')
        self.sub_editor.mark_subs_complete()
        self.sub_editor.click_saved_ok()
        self.assertTrue(self.video.subtitle_language('de').get_tip(public=True))
        self.tasks_tab.open_page('teams/%s/tasks/?lang=all&assignee=anyone'
                                 % self.team.slug)
        self.assertFalse(self.tasks_tab.task_present(
                        'Approve German Subtitles', self.video.title))


    def test_delete_last__team_language_ui(self):
        """Unpublish last public version, team members see lang on video page.


        """
        self.video_pg.log_in(self.contributor.username, 'password')
        self.video_pg.open_video_page(self.video.video_id)
        available_langs = self.video_pg.subtitle_languages()
        self.logger.info(available_langs)
        self.assertIn('English (in progress)', available_langs)



    def test_delete__edit_forked_translation(self):
        """In-progress translations editable after last source deleted.

        """
        self.tasks_tab.log_in(self.contributor.username, 'password')
        self.tasks_tab.open_page('teams/{0}/tasks/?team_video={1}'
                                 '&assignee=anyone&lang=sv'.format(
                                 self.team.slug, self.tv.pk))

        task_text = 'Translate Subtitles into Swedish'
        self.tasks_tab.perform_assigned_task(task_text, self.video.title)
        self.assertEqual('Typing', self.sub_editor.dialog_title())


    def test_delete__revision_not_searchable(self):
        """Unpublished (deleted) revision text doesn't show in search results.

        """
        self.watch_pg.log_out()
        management.call_command('update_index', interactive=False)

        self.watch_pg.open_watch_page()
        test_text = 'This is revision 3'
        results_pg = self.watch_pg.basic_search(test_text)
        self.assertTrue(results_pg.search_has_no_results())
