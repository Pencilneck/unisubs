import os

from apps.webdriver_testing.webdriver_base import WebdriverTestCase
from apps.webdriver_testing import data_helpers
from apps.webdriver_testing.pages.site_pages import video_language_page
from apps.webdriver_testing.pages.site_pages import video_page
from apps.webdriver_testing.pages.site_pages import diffing_page
from apps.webdriver_testing.data_factories import TeamVideoFactory
from apps.webdriver_testing.data_factories import TeamMemberFactory
from apps.webdriver_testing.data_factories import TeamAdminMemberFactory
from apps.webdriver_testing.data_factories import TeamManagerMemberFactory
from apps.webdriver_testing.data_factories import TeamContributorMemberFactory
from apps.webdriver_testing.data_factories import WorkflowFactory
from apps.webdriver_testing.data_factories import TeamLangPrefFactory
from apps.webdriver_testing.data_factories import UserFactory


class TestCaseApprovalWorkflow(WebdriverTestCase):
    """TestSuite for display of Edit Subtitles button on a revision. """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseApprovalWorkflow, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.video_lang_pg = video_language_page.VideoLanguagePage(cls)
        cls.video_pg = video_page.VideoPage(cls)
        cls.diffing_pg = diffing_page.DiffingPage(cls)
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


    def _upload_en_draft(self, video, subs, user, complete=False):
        auth_creds = dict(username=user.username, password='password')
        draft_data = {'language_code': 'en',
                     'video': video.pk,
                     'primary_audio_language_code': 'en',
                     'draft': open(subs),
                     'complete': int(complete),
                     'is_complete': complete,
                    }
        self.data_utils.upload_subs(video, draft_data, user=auth_creds)

    def _add_team_video(self):
        video = self.data_utils.create_video()
        tv = TeamVideoFactory(team=self.team, added_by=self.owner, video=video)
        return video, tv

    def _review_and_approve(self, tv):
        """Review and approve version.

        """
        if self.workflow.review_enabled:
            self.data_utils.complete_review_task(tv, 20, self.owner)
        if self.workflow.approve_enabled:
            self.data_utils.complete_approve_task(tv, 20, self.owner)

    def tearDown(self):
        if self.team.task_assign_policy > 10: #reset to default start value
            self.team.task_assign_policy = 10
            self.team.save()

    def _create_two_drafts(self, video, user):
        rev1 = os.path.join(self.subs_dir, 'Timed_text.en.srt')
        rev2 = os.path.join(self.subs_dir, 'Timed_text.rev2.en.srt')

        self._upload_en_draft(video, rev1, user)
        en = video.subtitle_language('en')
        en_v1 = en.get_tip()
        self._upload_en_draft(video, rev2, user)
        en_v2 = en.get_tip()
        return en_v1, en_v2

    def _create_complete_rev(self, video, user):
        rev1 = os.path.join(self.subs_dir, 'Timed_text.en.srt')
        rev2 = os.path.join(self.subs_dir, 'Timed_text.rev2.en.srt')

        self._upload_en_draft(video, rev1, user)
        en = video.subtitle_language('en')
        en_v1 = en.get_tip()
        self._upload_en_draft(video, rev2, user, complete=True)
        en_v2 = en.get_tip()
        return en_v1, en_v2


    def test_rollback_draft__assignee(self):
        """Rollback available for task assignee.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_two_drafts(video, self.contributor)
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())

    def test_diffing_rollback_draft__assignee(self):
        """Rollback available for task assignee.

        """
        video, tv = self._add_team_video()
        v1, v2 = self._create_two_drafts(video, self.contributor)
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')
        self.diffing_pg.open_diffing_page(v1.id, v2.id)
        self.assertTrue(self.diffing_pg.rollback_exists())

    def test_review_reject__assignee(self):
        """Rollback available for assignee after transcript fails review.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        #Reject transcript in review phase
        self.data_utils.complete_review_task(tv, 30, self.admin)
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())

    def test_diffing_rollback_review_reject__assignee(self):
        """Rollback on diffing page for assignee, if transcript fails review.

        """
        video, tv = self._add_team_video()
        v1, v2 = self._create_complete_rev(video, self.contributor)

        #Reject transcript in review phase
        self.data_utils.complete_review_task(tv, 30, self.admin)
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')
        self.diffing_pg.open_diffing_page(v1.id, v2.id)
        self.assertTrue(self.diffing_pg.rollback_exists())


    def test_approve_reject__assignee(self):
        """Rollback NOT available for transcriber when approve fails.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)
        #Accept transcript in review phase
        self.data_utils.complete_review_task(tv, 20, self.admin)
        #Reject transcript in the approve phase
        self.data_utils.complete_approve_task(tv, 30, self.owner)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())

    def test_review_unstarted__transcriber(self):
        """Rollback active for transcriber when waiting review.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())

    def test_diffing_rollback_review_unstarted__transcriber(self):
        """Rollback on diffing page for transcriber when waiting review.

        """
        video, tv = self._add_team_video()
        v1, v2 = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')
        self.diffing_pg.open_diffing_page(v1.id, v2.id)
        self.assertTrue(self.diffing_pg.rollback_exists())


    def test_approver_sent_back__reviewer(self):
        """Rollback active for reviewer after transcript fails approve.

        """
        reviewer = TeamContributorMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        #Accept transcript in review phase
        self.data_utils.complete_review_task(tv, 20, reviewer)
        #Reject transcript in the approve phase
        self.data_utils.complete_approve_task(tv, 30, self.owner)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(reviewer.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())



    def test_draft__not_task_assignee(self):
        """Rollback not active for member not assigned with task.

        """
        member2 = TeamContributorMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_two_drafts(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(member2.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())

    def test_diffing_page__not_task_assignee(self):
        """Rollback not active for member not assigned with task.

        """
        member2 = TeamContributorMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, v2 = self._create_two_drafts(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(member2.username, 'password')

        self.diffing_pg.open_diffing_page(v1.id, v2.id)
        self.assertFalse(self.diffing_pg.rollback_exists())


    def test_draft__team_admin(self):
        """Rollback not active for admin when task started by member.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_two_drafts(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.admin.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())


    def test_non_member_no_rollback(self):
        """Rollback not visible for non-member.
        """
        siteuser = UserFactory.create()
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(siteuser.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())


    def test_guest_sees_no_button(self):
        """Rollback not visible for guest.
        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)


        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_out()
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())


    def test_public__member_with_create_tasks(self):
        """Member can rollback to draft when create tasks is any team member.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)
        self._review_and_approve(tv)

        member2 = TeamContributorMemberFactory(team=self.team).user
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(member2.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())



    def test_public__member_with_no_create_tasks(self):
        """Member can not rollback version when create tasks is manager level.

        """
        self.team.task_assign_policy = 30
        self.team.save()
        self.logger.info("Task assign policy: %s" % self.team.task_assign_policy)
        member2 = TeamContributorMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)
        self._review_and_approve(tv)


        self.video_pg.open_video_page(video.video_id)
        self.video_lang_pg.log_in(member2.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())

    def test_public__manager_with_create_tasks(self):
        """Manager can rollback to draft when create tasks is manager level.

        """
        self.team.task_assign_policy = 20
        self.team.save()
        self.logger.info(self.team.task_assign_policy)

        teammanager = TeamManagerMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)
        self._review_and_approve(tv)

        self.video_pg.open_video_page(video.video_id)
        self.video_lang_pg.log_in(teammanager.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())

    def test_public__manager_with_no_create_tasks(self):
        """Manager can NOT rollback to draft when create tasks is admin level.

        """
        self.team.task_assign_policy = 30
        self.team.save()
        self.logger.info('TASK POLICY is %s' % self.team.task_assign_policy)
        tm = TeamManagerMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)
        self._review_and_approve(tv)


        self.video_pg.open_video_page(video.video_id)
        self.video_lang_pg.log_in(tm.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())


    def test_public__admin_always(self):
        """Admin can always rollback public version.

        """
        self.team.task_assign_policy = 30
        self.team.save()
        self.logger.info(self.team.task_assign_policy)

        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)
        self._review_and_approve(tv)


        self.video_pg.open_video_page(video.video_id)
        self.video_lang_pg.log_in(self.admin.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())



    def test_public__owner_always(self):
        """Owner can always rollback public version.

        """
        self.team.task_assign_policy = 30
        self.team.save()
        self.logger.info(self.team.task_assign_policy)

        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)
        self._review_and_approve(tv)

        self.video_pg.open_video_page(video.video_id)
        self.video_lang_pg.log_in(self.owner.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())



class TestCaseNoReviews(WebdriverTestCase):
    """TestSuite for Rollback of No-Review / Approve team. """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseNoReviews, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.video_lang_pg = video_language_page.VideoLanguagePage(cls)
        cls.video_pg = video_page.VideoPage(cls)

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
                                       approve_allowed = 00, # none
                                       review_allowed = 00, # none
                                       )
        lang_list = ['en', 'ru', 'pt-br', 'de', 'sv']
        for language in lang_list:
            TeamLangPrefFactory.create(team=cls.team, language_code=language,
                                       preferred=True)

        cls.admin = TeamAdminMemberFactory(team=cls.team).user
        cls.contributor = TeamMemberFactory(team=cls.team).user
        cls.subs_dir = os.path.join(os.getcwd(), 'apps', 'webdriver_testing', 
                                    'subtitle_data') 


    def _upload_en_draft(self, video, subs, user, complete=False):
        auth_creds = dict(username=user.username, password='password')
        draft_data = {'language_code': 'en',
                     'video': video.pk,
                     'primary_audio_language_code': 'en',
                     'draft': open(subs),
                     'complete': int(complete),
                     'is_complete': complete,
                    }
        self.data_utils.upload_subs(video, draft_data, user=auth_creds)

    def _add_team_video(self):
        video = self.data_utils.create_video()
        tv = TeamVideoFactory(team=self.team, added_by=self.owner, video=video)
        return video, tv

    def tearDown(self):
        if self.team.task_assign_policy > 10: #reset to default start value
            self.team.task_assign_policy = 10
            self.team.save()

    def _create_two_drafts(self, video, user):
        rev1 = os.path.join(self.subs_dir, 'Timed_text.en.srt')
        rev2 = os.path.join(self.subs_dir, 'Timed_text.rev2.en.srt')

        self._upload_en_draft(video, rev1, user)
        en = video.subtitle_language('en')
        en_v1 = en.get_tip()
        self._upload_en_draft(video, rev2, user)
        en_v2 = en.get_tip()
        return en_v1, en_v2

    def _create_complete_rev(self, video, user):
        rev1 = os.path.join(self.subs_dir, 'Timed_text.en.srt')
        rev2 = os.path.join(self.subs_dir, 'Timed_text.rev2.en.srt')

        self._upload_en_draft(video, rev1, user)
        en = video.subtitle_language('en')
        en_v1 = en.get_tip()
        self._upload_en_draft(video, rev2, user, complete=True)
        en_v2 = en.get_tip()
        return en_v1, en_v2


    def test_rollback_draft__assignee(self):
        """Rollback available for task assignee.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_two_drafts(video, self.contributor)
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())

    def test_draft__not_task_assignee(self):
        """Rollback active for member when task not started.

        """
        member2 = TeamContributorMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_two_drafts(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(member2.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())



    def test_public__2nd_member(self):
        """Rollback active for 2nd team member on published version

        """
        member2 = TeamContributorMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(member2.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())


    def test_public__team_admin(self):
        """Rollback active for admin on published version.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.admin.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())


    def test_non_member_no_rollback(self):
        """Rollback not visible for non-member.
        """
        siteuser = UserFactory.create()
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(siteuser.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())


    def test_guest_sees_no_button(self):
        """Rollback not visible for guest.
        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)


        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_out()
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())


    def test_public__member_with_no_create_tasks(self):
        """Member can rollback to draft when create tasks is any team member.

        """
        self.team.task_assign_policy = 30
        self.team.save()
        self.logger.info("Task assign policy: %s" % self.team.task_assign_policy)

        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        member2 = TeamContributorMemberFactory(team=self.team).user
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(member2.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())


class TestCaseNoWorkflow(WebdriverTestCase):
    """TestSuite for Rollback of No Workflow team. """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseNoWorkflow, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.video_lang_pg = video_language_page.VideoLanguagePage(cls)
        cls.video_pg = video_page.VideoPage(cls)

        cls.user = UserFactory.create()
        cls.owner = UserFactory.create()
        cls.team = TeamMemberFactory.create( team__translate_policy=20, #any team
                                            team__subtitle_policy=20, #any team
                                            user = cls.owner,
                                            ).team
        cls.admin = TeamAdminMemberFactory(team=cls.team).user
        cls.contributor = TeamMemberFactory(team=cls.team).user
        cls.subs_dir = os.path.join(os.getcwd(), 'apps', 'webdriver_testing', 
                                    'subtitle_data') 


    def _upload_en_draft(self, video, subs, user, complete=False):
        auth_creds = dict(username=user.username, password='password')
        draft_data = {'language_code': 'en',
                     'video': video.pk,
                     'primary_audio_language_code': 'en',
                     'draft': open(subs),
                     'complete': int(complete),
                     'is_complete': complete,
                    }
        self.data_utils.upload_subs(video, draft_data, user=auth_creds)

    def _add_team_video(self):
        video = self.data_utils.create_video()
        tv = TeamVideoFactory(team=self.team, added_by=self.owner, video=video)
        return video, tv


    def _create_two_drafts(self, video, user):
        rev1 = os.path.join(self.subs_dir, 'Timed_text.en.srt')
        rev2 = os.path.join(self.subs_dir, 'Timed_text.rev2.en.srt')

        self._upload_en_draft(video, rev1, user)
        en = video.subtitle_language('en')
        en_v1 = en.get_tip()
        self._upload_en_draft(video, rev2, user)
        en_v2 = en.get_tip()
        return en_v1, en_v2

    def _create_complete_rev(self, video, user):
        rev1 = os.path.join(self.subs_dir, 'Timed_text.en.srt')
        rev2 = os.path.join(self.subs_dir, 'Timed_text.rev2.en.srt')

        self._upload_en_draft(video, rev1, user)
        en = video.subtitle_language('en')
        en_v1 = en.get_tip()
        self._upload_en_draft(video, rev2, user, complete=True)
        en_v2 = en.get_tip()
        return en_v1, en_v2


    def test_rollback_incomplete__current_editor(self):
        """Rollback available for member currently editing draft.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_two_drafts(video, self.contributor)
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())

    def test_incomplete__2nd_member(self):
        """Rollback not active for 2nd team member

        """
        member2 = TeamContributorMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_two_drafts(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(member2.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())


    def test_incomplete__team_admin(self):
        """Rollback not active for admin when task started by member.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_two_drafts(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.admin.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())

    def test_public__2nd_member(self):
        """Rollback active for 2nd team member on published version

        """
        member2 = TeamContributorMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(member2.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())


    def test_public__team_admin(self):
        """Rollback active for admin on published version.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.admin.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback_exists())


    def test_non_member_no_rollback(self):
        """Rollback not visible for non-member.
        """
        siteuser = UserFactory.create()
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(siteuser.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())


    def test_guest_sees_no_button(self):
        """Rollback not visible for guest.
        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)


        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_out()
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertFalse(self.video_lang_pg.rollback_exists())




class TestCaseRollbackRevision(WebdriverTestCase):
    """TestSuite for clicking Rollback button on a revision. """
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseRollbackRevision, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.video_lang_pg = video_language_page.VideoLanguagePage(cls)
        cls.diffing_pg = diffing_page.DiffingPage(cls)
        cls.video_pg = video_page.VideoPage(cls)
        cls.user = UserFactory.create()

        cls.owner = UserFactory.create()
        cls.team = TeamMemberFactory.create(team__workflow_enabled=True,
                                            team__translate_policy=20, #any team
                                            team__subtitle_policy=20, #any team
                                            team__task_assign_policy=10, #any team
                                            user = cls.owner,
                                            ).team
        cls.team_workflow = WorkflowFactory(team = cls.team,
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

    def _add_team_video(self):
        video = self.data_utils.create_video()
        tv = TeamVideoFactory(team=self.team, added_by=self.owner, video=video)
        return video, tv

    def _upload_en_draft(self, video, subs, user, complete=False):
        auth_creds = dict(username=user.username, password='password')
        draft_data = {'language_code': 'en',
                     'video': video.pk,
                     'primary_audio_language_code': 'en',
                     'draft': open(subs),
                     'complete': int(complete),
                     'is_complete': complete,
                    }
        self.data_utils.upload_subs(video, draft_data, user=auth_creds)

    def _create_two_drafts(self, video, user):
        rev1 = os.path.join(self.subs_dir, 'Timed_text.en.srt')
        rev2 = os.path.join(self.subs_dir, 'Timed_text.rev2.en.srt')

        self._upload_en_draft(video, rev1, user)
        en = video.subtitle_language('en')
        en_v1 = en.get_tip()
        self._upload_en_draft(video, rev2, user)
        en_v2 = en.get_tip()
        return en_v1, en_v2

    def _create_complete_rev(self, video, user):
        rev1 = os.path.join(self.subs_dir, 'Timed_text.en.srt')
        rev2 = os.path.join(self.subs_dir, 'Timed_text.rev2.en.srt')

        self._upload_en_draft(video, rev1, user)
        en = video.subtitle_language('en')
        en_v1 = en.get_tip()
        self._upload_en_draft(video, rev2, user, complete=True)
        en_v2 = en.get_tip()
        return en_v1, en_v2



    def test_unstarted_review__transcriber_rollback(self):
        """Transcriber can rollback while waiting review.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')

        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback())
        
        en_v3 = video.subtitle_language('en').get_tip()
        self.video_lang_pg.open_page(en_v3.get_absolute_url())
        self.assertTrue(self.video_lang_pg.is_draft())
        self.assertIn('Revision 3', self.video_lang_pg.view_notice())

    def test_unstarted_review__diffing_page_rollback(self):
        """Transcriber can rollback while waiting review.

        """
        video, tv = self._add_team_video()
        v1, v2 = self._create_complete_rev(video, self.contributor)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.contributor.username, 'password')

        self.diffing_pg.open_diffing_page(v1.id, v2.id)
        self.assertTrue(self.diffing_pg.rollback())
        
        en_v3 = video.subtitle_language('en').get_tip()
        self.video_lang_pg.open_page(en_v3.get_absolute_url())
        self.assertTrue(self.video_lang_pg.is_draft())
        self.assertIn('Revision 3', self.video_lang_pg.view_notice())

    def test_failed_approve__reviewer_rollback(self):
        """Reviewer can rollback after transcript fails approve.

        """
        reviewer = TeamContributorMemberFactory(team=self.team).user
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)

        #Accept transcript in review phase
        self.data_utils.complete_review_task(tv, 20, reviewer)
        #Reject transcript in the approve phase
        self.data_utils.complete_approve_task(tv, 30, self.owner)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(reviewer.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback())
        
        en_v3 = video.subtitle_language('en').get_tip()
        self.video_lang_pg.open_page(en_v3.get_absolute_url())
        self.assertTrue(self.video_lang_pg.is_draft())
        self.assertIn('Revision 3', self.video_lang_pg.view_notice())


    def test_rolledback_draft_is_public(self):
        """Post-approval rollback to draft produces public version.

        """
        video, tv = self._add_team_video()
        v1, _ = self._create_complete_rev(video, self.contributor)
        #Accept transcript in review phase
        self.data_utils.complete_review_task(tv, 20, self.admin)
        #Reject transcript in the approve phase
        self.data_utils.complete_approve_task(tv, 20, self.owner)
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.admin.username, 'password')
        self.video_lang_pg.open_page(v1.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback())
        
        en_v3 = video.subtitle_language('en').get_tip()
        self.video_lang_pg.open_page(en_v3.get_absolute_url())
        self.assertFalse(self.video_lang_pg.is_draft())
        self.assertIn('Revision 3', self.video_lang_pg.view_notice())

    def test_diffing_page_rolledback_draft_is_public(self):
        """Post-approval diffing page rollback to draft produces public 

           version.

        """
        video, tv = self._add_team_video()
        v1, v2 = self._create_complete_rev(video, self.contributor)
        #Accept transcript in review phase
        self.data_utils.complete_review_task(tv, 20, self.admin)
        #Reject transcript in the approve phase
        self.data_utils.complete_approve_task(tv, 20, self.owner)
        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.admin.username, 'password')

        self.diffing_pg.open_diffing_page(v1.id, v2.id)
        self.assertTrue(self.diffing_pg.rollback())
        
        en_v3 = video.subtitle_language('en').get_tip()
        self.video_lang_pg.open_page(en_v3.get_absolute_url())
        self.assertFalse(self.video_lang_pg.is_draft())
        self.assertIn('Revision 3', self.video_lang_pg.view_notice())



    def test_unpublished__rollback(self):
        """Rollback to unpublished version produce new public version.
        
        """
        video, tv = self._add_team_video()
        self._create_complete_rev(video, self.contributor)
        rev3 = os.path.join(self.subs_dir, 'Timed_text.rev3.en.srt')
        self._upload_en_draft(video, rev3, self.admin, complete=True)
        #Accept transcript in review phase
        self.data_utils.complete_review_task(tv, 20, self.admin)
        #Reject transcript in the approve phase
        self.data_utils.complete_approve_task(tv, 20, self.owner)
        rev4 = os.path.join(self.subs_dir, 'Timed_text.rev4.en.srt')
        self._upload_en_draft(video, rev4, self.admin, complete=True)

        #set v3 visibilility_override to private
        en_v3 = video.subtitle_language('en').version(version_number=3)
        en_v3.visibility_override = 'private'
        en_v3.save() 

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.admin.username, 'password')
        self.video_lang_pg.open_page(en_v3.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback())
        en_v5 = video.subtitle_language('en').version(version_number=5)
        self.video_lang_pg.open_page(en_v5.get_absolute_url())
        self.assertFalse(self.video_lang_pg.is_draft())
        self.assertIn('Revision 5', self.video_lang_pg.view_notice())

    def test_diffing_page_unpublished__rollback(self):
        """Rollback to unpublished version (diffing page) => new public version.
        
        """
        video, tv = self._add_team_video()
        self._create_complete_rev(video, self.contributor)
        rev3 = os.path.join(self.subs_dir, 'Timed_text.rev3.en.srt')
        self._upload_en_draft(video, rev3, self.admin, complete=True)
        #Accept transcript in review phase
        self.data_utils.complete_review_task(tv, 20, self.admin)
        #Reject transcript in the approve phase
        self.data_utils.complete_approve_task(tv, 20, self.owner)
        rev4 = os.path.join(self.subs_dir, 'Timed_text.rev4.en.srt')
        self._upload_en_draft(video, rev4, self.admin, complete=True)

        #set v3 visibilility_override to private
        en_v3 = video.subtitle_language('en').version(version_number=3)
        en_v3.visibility_override = 'private'
        en_v3.save() 
        en_v4 = video.subtitle_language('en').version(version_number=4)

        self.video_lang_pg.open_video_lang_page(video.video_id, 'en')
        self.video_lang_pg.log_in(self.admin.username, 'password')

        self.diffing_pg.open_diffing_page(en_v3.id, en_v4.id)
        self.assertTrue(self.diffing_pg.rollback())

        self.video_lang_pg.open_page(en_v3.get_absolute_url())
        self.assertTrue(self.video_lang_pg.rollback())
        en_v5 = video.subtitle_language('en').version(version_number=5)
        self.video_lang_pg.open_page(en_v5.get_absolute_url())
        self.assertFalse(self.video_lang_pg.is_draft())
        self.assertIn('Revision 5', self.video_lang_pg.view_notice())




