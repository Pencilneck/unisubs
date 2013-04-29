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
import babelsubs
import chardet
import re
from datetime import datetime

from django import forms
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_unicode, DjangoUnicodeDecodeError
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from math_captcha.forms import MathCaptchaForm

from apps.videos.feed_parser import FeedParser
from apps.videos.models import Video, UserTestResult, VideoUrl
from apps.videos.permissions import can_user_edit_video_urls
from apps.videos.tasks import import_videos_from_feeds
from apps.videos.types import video_type_registrar, VideoTypeError
from apps.videos.types.youtube import yt_service
from utils.forms import AjaxForm, EmailListField, UsernameListField, StripRegexField, FeedURLField, ReCaptchaField
from utils.http import url_exists
from utils.translation import get_language_choices

ALL_LANGUAGES = [(val, _(name)) for val, name in settings.ALL_LANGUAGES]
KB_SIZELIMIT = 512

import logging
logger = logging.getLogger("videos-forms")

class TranscriptionFileForm(forms.Form, AjaxForm):
    txtfile = forms.FileField()

    def clean_txtfile(self):
        f = self.cleaned_data['txtfile']

        if f.name.split('.')[-1] != 'txt':
            raise forms.ValidationError(_('File should have txt format'))

        if f.size > KB_SIZELIMIT * 1024:
            raise forms.ValidationError(_(
                    u'File size should be less {0} kb'.format(KB_SIZELIMIT)))

        text = f.read()
        encoding = chardet.detect(text)['encoding']
        if not encoding:
            raise forms.ValidationError(_(u'Can not detect file encoding'))
        try:
            self.file_text = force_unicode(text, encoding)
        except DjangoUnicodeDecodeError:
            raise forms.ValidationError(_(u'Can\'t encode file. It should have utf8 encoding.'))
        f.seek(0)

        return f

    def clean_subtitles(self):
        subtitles = self.cleaned_data['subtitles']
        if subtitles.size > KB_SIZELIMIT * 1024:
            raise forms.ValidationError(_(
                    u'File size should be less {0} kb'.format(KB_SIZELIMIT)))
        parts = subtitles.name.split('.')
        extension = parts[-1].lower()
        if extension not in babelsubs.get_available_formats():
            raise forms.ValidationError(_(u'Incorrect format. Upload .%s ' % ", ".join(babelsubs.get_available_formats())))
        text = subtitles.read()
        encoding = chardet.detect(text)['encoding']
        if not encoding:
            raise forms.ValidationError(_(u'Can not detect file encoding'))
        try:
            parser = babelsubs.parsers.discover(extension)
            subtitle_set = parser('en', force_unicode(text, encoding))
        except babelsubs.SubtitleParserError:
            raise forms.ValidationError(_(u'Incorrect subtitles format'))
        subtitles.seek(0)
        return subtitles

class CreateVideoUrlForm(forms.ModelForm):

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(CreateVideoUrlForm, self).__init__(*args, **kwargs)
        self.fields['video'].widget = forms.HiddenInput()

    class Meta:
        model = VideoUrl
        fields = ('url', 'video')

    def clean_url(self):
        url = self.cleaned_data['url']

        try:
            video_type = video_type_registrar.video_type_for_url(url)

            video_url = video_type.video_url(video_type)

            if video_type.requires_url_exists and  not url_exists(video_url) :
                raise forms.ValidationError(_(u'This URL appears to be a broken link.'))

        except VideoTypeError, e:
            raise forms.ValidationError(e)

        if not video_type:
            raise forms.ValidationError(mark_safe(_(u"""Amara does not support that website or video format.
If you'd like to us to add support for a new site or format, or if you
think there's been some mistake, <a
href="mailto:%s">contact us</a>!""") % settings.FEEDBACK_EMAIL))
        self._video_type = video_type
        return video_type.convert_to_video_url()

    def clean(self):
        data = super(CreateVideoUrlForm, self).clean()
        video = data.get('video')
        if video and not can_user_edit_video_urls(video, self.user):
            raise forms.ValidationError(_('You have not permission add video URL for this video'))

        return self.cleaned_data

    def save(self, commit=True):
        obj = super(CreateVideoUrlForm, self).save(False)
        obj.type = self._video_type.abbreviation
        obj.added_by = self.user
        obj.videoid = self._video_type.video_id or ''
        commit and obj.save()
        return obj

    def get_errors(self):
        output = {}
        for key, value in self.errors.items():
            output[key] = '/n'.join([force_unicode(i) for i in value])
        return output

class UserTestResultForm(forms.ModelForm):

    class Meta:
        model = UserTestResult
        exclude = ('browser',)

    def save(self, request):
        obj = super(UserTestResultForm, self).save(False)
        obj.browser = request.META.get('HTTP_USER_AGENT', 'empty HTTP_USER_AGENT')
        obj.save()
        return obj

class VideoForm(forms.Form):
    # url validation is within the clean method
    video_url = forms.URLField(verify_exists=False)

    def __init__(self, user=None, *args, **kwargs):
        if user and not user.is_authenticated():
            user = None
        self.user = user
        super(VideoForm, self).__init__(*args, **kwargs)
        self.fields['video_url'].widget.attrs['class'] = 'main_video_form_field'

    def clean_video_url(self):
        video_url = self.cleaned_data['video_url']

        if video_url:
            try:
                video_type = video_type_registrar.video_type_for_url(video_url)
            except VideoTypeError, e:
                raise forms.ValidationError(e)
            if not video_type:
                for d in video_type_registrar.domains:
                    if d in video_url:
                        raise forms.ValidationError(mark_safe(_(u"""Please try again with a link to a video page.
                        <a href="mailto:%s">Contact us</a> if there's a problem.""") % settings.FEEDBACK_EMAIL))

                raise forms.ValidationError(mark_safe(_(u"""You must link to a video on a compatible site (like YouTube) or directly to a
                    video file that works with HTML5 browsers. For example: http://mysite.com/myvideo.ogg or http://mysite.com/myipadvideo.m4v
                    <a href="mailto:%s">Contact us</a> if there's a problem.""") % settings.FEEDBACK_EMAIL))

            else:
                self._video_type = video_type
                # we need to use the cannonical url as the user provided might need
                # redirection (i.e. youtu.be/fdaf/), and django's validator will
                # choke on redirection (urllib2 for python2.6), see https://unisubs.sifterapp.com/projects/12298/issues/427646/comments
                video_url = video_type.video_url(video_type)

                if not url_exists(video_url) :
                    raise forms.ValidationError(_(u'This URL appears to be a broken link.'))

        return video_url

    def save(self):
        video_url = self.cleaned_data['video_url']
        obj, created = Video.get_or_create_for_url(video_url, self._video_type, self.user)
        self.created = created
        return obj

youtube_user_url_re = re.compile(r'^(http://)?(www.)?youtube.com/user/(?P<username>[a-zA-Z0-9]+)/?.*$')

class AddFromFeedForm(forms.Form, AjaxForm):
    VIDEOS_LIMIT = 10

    youtube_feed_url_pattern =  'https://gdata.youtube.com/feeds/api/users/%s/uploads'
    usernames = UsernameListField(required=False, label=_(u'Youtube usernames'), help_text=_(u'Enter usernames separated by comma.'))
    youtube_user_url = StripRegexField(youtube_user_url_re, required=False, label=_(u'Youtube page link.'),
                                       help_text=_(u'For example: http://www.youtube.com/user/username'))
    feed_url = FeedURLField(required=False, help_text=_(u'Supported: Youtube, Vimeo, or Dailymotion. Only supported sites added.'))
    save_feed = forms.BooleanField(required=False, label=_(u'Save feed'), help_text=_(u'Choose this if you wish to add videos from this feed in the future. Only valid RSS feeds will be saved.'))

    def __init__(self, user, *args, **kwargs):
        if not user.is_authenticated():
            user = None
        self.user = user
        super(AddFromFeedForm, self).__init__(*args, **kwargs)

        self.yt_service = yt_service
        self.urls = []
        self.video_limit_routreach = False

    def clean_feed_url(self):
        url = self.cleaned_data.get('feed_url', '')

        if url:
            self.parse_feed_url(url)

        return url

    def clean_youtube_user_url(self):
        url = self.cleaned_data.get('youtube_user_url', '').strip()

        if url:
            username = youtube_user_url_re.match(url).groupdict()['username']
            url = self.youtube_feed_url_pattern % str(username)
            self.parse_feed_url(url)

        return url

    def clean_usernames(self):
        usernames = self.cleaned_data.get('usernames', [])

        for username in usernames:
            url = self.youtube_feed_url_pattern % str(username)
            self.parse_feed_url(url)

        return usernames

    def parse_feed_url(self, url):
        feed_parser = FeedParser(url)

        if not hasattr(feed_parser.feed, 'version') or not feed_parser.feed.version:
            raise forms.ValidationError(_(u'Sorry, we could not find a valid feed at the URL you provided. Please check the URL and try again.'))

        self.urls.append(url)

    def success_message(self):
        return _(u"The videos are being added in the background. "
                 u"If you are logged in, you will receive a message when it's done")

    def save(self, team=None):
        user_id = self.user.id if self.user else None
        team_id = team.id if team else None
        import_videos_from_feeds.delay(self.urls, user_id, team_id)

class FeedbackForm(forms.Form):
    email = forms.EmailField(required=False)
    message = forms.CharField(widget=forms.Textarea())
    error = forms.CharField(required=False, widget=forms.HiddenInput)
    captcha = ReCaptchaField(label=_(u'captcha'))

    def __init__(self, *args, **kwargs):
        hide_captcha = kwargs.pop('hide_captcha', False)
        super(FeedbackForm, self).__init__(*args, **kwargs)
        if hide_captcha:
            del self.fields['captcha']

    def send(self, request):
        email = self.cleaned_data['email']
        message = self.cleaned_data['message']
        error = self.cleaned_data['error']
        user_agent_data = u'User agent: %s' % request.META.get('HTTP_USER_AGENT')
        timestamp = u'Time: %s' % datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        version = u'Version: %s' % settings.PROJECT_VERSION
        commit = u'Commit: %s' % settings.LAST_COMMIT_GUID
        url = u'URL: %s' % request.META.get('HTTP_REFERER', '')
        user = u'Logged in: %s' % (request.user.is_authenticated() and request.user or u'not logged in')
        message = u'%s\n\n%s\n%s\n%s\n%s\n%s\n%s' % (message, user_agent_data, timestamp, version, commit, url, user)
        if error in ['404', '500']:
            message += u'\nPage type: %s' % error
            feedback_emails = [settings.FEEDBACK_ERROR_EMAIL]
        else:
            feedback_emails = settings.FEEDBACK_EMAILS
        headers = {'Reply-To': email} if email else None
        bcc = getattr(settings, 'EMAIL_BCC_LIST', [])
        if email:
            subject = '%s (from %s)' % (settings.FEEDBACK_SUBJECT, email)
        else:
            subject = settings.FEEDBACK_SUBJECT
        EmailMessage(subject, message, email, \
                         feedback_emails, headers=headers, bcc=bcc).send()

        if email:
            headers = {'Reply-To': settings.FEEDBACK_RESPONSE_EMAIL}
            body = render_to_string(settings.FEEDBACK_RESPONSE_TEMPLATE, {})
            email = EmailMessage(settings.FEEDBACK_RESPONSE_SUBJECT, body, \
                         settings.FEEDBACK_RESPONSE_EMAIL, [email], headers=headers, bcc=bcc)
            email.content_subtype = 'html'
            email.send()

    def get_errors(self):
        from django.utils.encoding import force_unicode
        output = {}
        for key, value in self.errors.items():
            output[key] = '/n'.join([force_unicode(i) for i in value])
        return output

class EmailFriendForm(MathCaptchaForm):
    from_email = forms.EmailField(label='From')
    to_emails = EmailListField(label='To')
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea())

    def send(self):
        subject = self.cleaned_data['subject']
        message = self.cleaned_data['message']
        from_email = self.cleaned_data['from_email']
        to_emails = self.cleaned_data['to_emails']
        send_mail(subject, message, from_email, to_emails)

class ChangeVideoOriginalLanguageForm(forms.Form):
    language_code = forms.ChoiceField(choices=ALL_LANGUAGES)

    def __init__(self, *args, **kwargs):
        super(ChangeVideoOriginalLanguageForm, self).__init__(*args, **kwargs)

        self.fields['language_code'].choices = [('', '--Select language--')] + get_language_choices()
