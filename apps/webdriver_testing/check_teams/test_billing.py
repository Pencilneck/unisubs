# -*- coding: utf-8 -*-
import os
import datetime
import csv
from collections import defaultdict


from apps.webdriver_testing.webdriver_base import WebdriverTestCase
from apps.webdriver_testing.data_factories import TeamMemberFactory
from apps.webdriver_testing.data_factories import TeamVideoFactory

from apps.webdriver_testing.data_factories import UserFactory
from apps.webdriver_testing.data_factories import VideoUrlFactory
from apps.webdriver_testing.data_factories import BillingFactory
from apps.webdriver_testing import data_helpers
from apps.webdriver_testing.pages.site_pages import billing_page 

class TestCaseBilling(WebdriverTestCase):
    NEW_BROWSER_PER_TEST_CASE = False

    @classmethod
    def setUpClass(cls):
        super(TestCaseBilling, cls).setUpClass()
        cls.data_utils = data_helpers.DataHelpers()
        cls.billing_pg = billing_page.BillingPage(cls)
        cls.terri = UserFactory.create(username='Terri', 
                                       is_staff=True, is_superuser=True)
        cls.user = UserFactory.create()
        cls.team = TeamMemberFactory.create(user = cls.user).team
        cls.subs_data_dir = os.path.join(os.getcwd(), 'apps', 
            'webdriver_testing', 'subtitle_data')
        cls.video, cls.tv = cls._create_tv_with_original_subs(cls.user)
        cls._upload_sv_translation(cls.video, cls.user, complete=True)

        cls.bill_dict = cls.create_team_bill()


    @classmethod
    def create_team_bill(cls):
        report = BillingFactory(team=cls.team, 
                                start_date=(datetime.date.today() - 
                                            datetime.timedelta(1)),
                                end_date=datetime.datetime.now(),
                                )
        report.process()
        cls.bill = 'user-data/%s' % report.csv_file
        bill_dict = cls._bill_dict(cls.bill)
        return bill_dict


    @classmethod
    def _create_tv_with_original_subs(cls, user, complete=True):
        member_creds = dict(username=user.username, password='password')
        sub_file = os.path.join(cls.subs_data_dir, 'Timed_text.en.srt')
        video = VideoUrlFactory().video
        tv = TeamVideoFactory.create(
            team=cls.team, 
            video=video, 
            added_by=user)
        data = {'language_code': 'en',
                'video': video.pk,
                'primary_audio_language_code': 'en',
                'draft': open(sub_file),
                'is_complete': complete,
                'complete': int(complete),
                }
        cls.data_utils.upload_subs(video, data, member_creds)
        #self.data_utils.complete_review_task(tv, 20, self.team_admin)
        #self.data_utils.complete_approve_task(tv, 20, self.team_admin)
        return video, tv

    @classmethod
    def _upload_sv_translation(cls, video, user, complete=False):
        member_creds = dict(username=user.username, password='password')

        data = {'language_code': 'sv',
                'video': video.pk,
                'from_language_code': 'en',
                'draft': open('apps/webdriver_testing/subtitle_data/'
                              'Timed_text.sv.dfxp'),
                'is_complete': complete,
                'complete': int(complete),}
        cls.data_utils.upload_subs(video, data=data, user=member_creds)

    @classmethod
    def _bill_dict(cls, bill_file):
        team_bill = defaultdict(dict)
        with open(bill_file, 'rb') as fp:
            reader = csv.DictReader(fp, dialect='excel')
            for rowdict in reader:
                video_id = rowdict.pop("Video ID")
                lang = rowdict.pop("Language")
                cls.logger.info(lang)
                team_bill[video_id][lang] = rowdict 
        return dict(team_bill)
        

    def test_complete(self):
        """Complete team videos are billed.

        """

        self.assertEqual('3.0', 
                         self.bill_dict[self.video.video_id]['en']['Minutes'])


    def test_incomplete(self):
        """Incomplete videos are not billed.

        """
        video, tv = self._create_tv_with_original_subs(self.user)
        inc_video, inc_tv = self._create_tv_with_original_subs(self.user, complete=False)

        report = BillingFactory(team=self.team, 
                                start_date=(datetime.date.today() - 
                                            datetime.timedelta(1)),
                                end_date=datetime.datetime.now(),
                                )
        report.process()
        bill = 'user-data/%s' % report.csv_file
        bill_dict = self._bill_dict(bill)
        self.assertNotIn(inc_video.video_id, bill_dict.keys())


    def test_primary_audio_language(self):
        """Primary audio lang true / false included in Original field.

        """
        self.logger.info(self.bill_dict)
        self.assertEqual('True',
                         self.bill_dict[self.video.video_id]['en']['Original'])
        self.assertEqual('False',
                         self.bill_dict[self.video.video_id]['sv']['Original'])


    def test_translation__complete(self):
        """Billing record added for complete translations

        """
        self.assertIn('sv', self.bill_dict[self.video.video_id].keys())

    def test_translation__incomplete(self):
        """Billing record NOT added for incomplete translations

        """
        video, tv = self._create_tv_with_original_subs(self.user)
        self._upload_sv_translation(video, self.user, complete=False)

        report = BillingFactory(team=self.team, 
                                start_date=(datetime.date.today() - 
                                            datetime.timedelta(1)),
                                end_date=datetime.datetime.now(),
                                )
        report.process()
        bill = 'user-data/%s' % report.csv_file
        bill_dict = self._bill_dict(bill)
        self.assertNotIn('sv', bill_dict[video.video_id].keys())


    def test_minutes(self):
        """Minutes from last synced sub rounded up to whole minute.

        """
        self.assertEqual('3.0', 
                         self.bill_dict[self.video.video_id]['en']['Minutes'])


    def test_source(self):
        """Source of subs is listed in data (youtube, upload, api...)

        """
        self.assertEqual('upload', 
                         self.bill_dict[self.video.video_id]['en']['Source'])

    def test_user(self):
        """User credit with subtitles is listed in the record.

        """
        testuser = TeamMemberFactory.create().user
        video, tv = self._create_tv_with_original_subs(self.user)
        self._upload_sv_translation(video, testuser, complete=True)

        report = BillingFactory(team=self.team, 
                                start_date=(datetime.date.today() - 
                                            datetime.timedelta(1)),
                                end_date=datetime.datetime.now(),
                                )
        report.process()
        bill = 'user-data/%s' % report.csv_file
        bill_dict = self._bill_dict(bill)
        self.assertEqual(self.user.username, bill_dict[video.video_id]['en']['User'])
        self.assertEqual(testuser.username, bill_dict[video.video_id]['sv']['User'])


    def test_team(self):
        """Team is listed in the record.

        """
        self.assertEqual(self.team.slug, 
                         self.bill_dict[self.video.video_id]['en']['Team'])
    
    def test_created(self):
        """Data subtitles completed is listed in the record.

        """
        en = self.video.subtitle_language('en').get_tip(full=True)
        self.logger.info(dir(en))
        self.assertEqual(en.created.strftime("%Y-%m-%d %H:%M:%S"), 
                         self.bill_dict[self.video.video_id]['en']['Created'])

    def test_video(self):
        """Video id is listed in the record.

        """
        self.assertIn(self.video.video_id, self.bill_dict.keys())


    def test_new_billing_fields(self):
        video, tv = self._create_tv_with_original_subs(self.user)
        report = BillingFactory(team=self.team, 
                                start_date=(datetime.date.today() - 
                                            datetime.timedelta(1)),
                                end_date=datetime.datetime.now(),
                                )
        report.process()
        bill = csv.DictReader(open('user-data/%s' %report.csv_file))
        expected_fields = ['Video ID', 'Language', 'Minutes', 'Original', 
                           'Team', 'Created', 'Source', 'User']
        self.assertEqual(expected_fields, bill.fieldnames)


    def test_old_billing_fields(self):
        video, tv = self._create_tv_with_original_subs(self.user)
        report = BillingFactory(type=1,
                                team=self.team, 
                                start_date=(datetime.date.today() - 
                                            datetime.timedelta(1)),
                                end_date=datetime.datetime.now(),
                                )
        report.process()
        bill = csv.DictReader(open('user-data/%s' %report.csv_file))
        expected_fields = ['Video title', 'Video URL', 'Video language',
                           'Source', 'Billable minutes', 'Version created',
                           'Language number']
        self.assertEqual(expected_fields, bill.fieldnames)

 
    def test_download__new_model(self):
        """Data range of records downloaded to a csv file for a team.

        """
        for x in range(3):
            video, tv = self._create_tv_with_original_subs(self.user)

        self.billing_pg.open_billing_page()
        self.billing_pg.log_in(self.terri.username, 'password')
        self.billing_pg.open_billing_page()
        start = (datetime.date.today() - datetime.timedelta(7))
        end =  (datetime.date.today() + datetime.timedelta(2))
        self.logger.info(start.strftime("%Y-%m-%d"))

        self.billing_pg.submit_billing_parameters(self.team.slug,
                                                  start.strftime("%Y-%m-%d"),
                                                  end.strftime("%Y-%m-%d"),
                                                  'New model')
        report_dl = self.billing_pg.check_latest_report_url()
        self.logger.info(report_dl)
        new_headers = 'Video ID,Language,Minutes,Original,Team,Created,Source,User' 
        self.assertEqual(6, len(report_dl))
        self.assertEqual(new_headers, report_dl[0])

    def test_download__old_model(self):
        """Data range of records downloaded to a csv file for a team.

        """
        for x in range(3):
            video, tv = self._create_tv_with_original_subs(self.user)

        self.billing_pg.open_billing_page()
        self.billing_pg.log_in(self.terri.username, 'password')
        self.billing_pg.open_billing_page()
        start = (datetime.date.today() - datetime.timedelta(7))
        end =  (datetime.date.today() + datetime.timedelta(2))
        self.logger.info(start.strftime("%Y-%m-%d"))

        self.billing_pg.submit_billing_parameters(self.team.slug,
                                                  start.strftime("%Y-%m-%d"),
                                                  end.strftime("%Y-%m-%d"),
                                                  'Old model')
        report_dl = self.billing_pg.check_latest_report_url()
        self.logger.info(report_dl)
        old_headers = ('Video title,Video URL,Video language,Source,Billable minutes,'
                       'Version created,Language number')
        self.assertEqual(6, len(report_dl))
        self.assertEqual(old_headers, report_dl[0])



