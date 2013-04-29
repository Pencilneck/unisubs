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

import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import  reverse
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils import simplejson as json
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_unicode
from django.views.generic.list_detail import object_list
from django.views.generic.simple import direct_to_template
from tastypie.models import ApiKey

from auth.models import CustomUser as User
from profiles.forms import (EditUserForm, EditAccountForm, SendMessageForm,
                            EditAvatarForm)
from profiles.rpc import ProfileApiClass
from apps.messages.models import Message
from utils.orm import LoadRelatedQuerySet
from utils.rpc import RpcRouter
from subtitles.models import SubtitleLanguage
from videos.models import (
    Action, VideoUrl, Video, VIDEO_TYPE_YOUTUBE, VideoFeed
)


logger = logging.getLogger(__name__)


rpc_router = RpcRouter('profiles:rpc_router', {
    'ProfileApi': ProfileApiClass()
})

VIDEOS_ON_PAGE = getattr(settings, 'VIDEOS_ON_PAGE', 30)
LINKABLE_ACCOUNTS = ['youtube', 'twitter', 'facebook']


class OptimizedQuerySet(LoadRelatedQuerySet):

    def update_result_cache(self):
        videos = dict((v.id, v) for v in self._result_cache if not hasattr(v, 'langs_cache'))

        if videos:
            for v in videos.values():
                v.langs_cache = []

            langs_qs = SubtitleLanguage.objects.select_related('video').filter(video__id__in=videos.keys())

            for l in langs_qs:
                videos[l.video_id].langs_cache.append(l)


def activity(request, user_id=None):
    if user_id:
        try:
            user = User.objects.get(username=user_id)
        except User.DoesNotExist:
            try:
                user = User.objects.get(id=user_id)
            except (User.DoesNotExist, ValueError):
                raise Http404

    qs = Action.objects.filter(user=user)

    extra_context = {
        'user_info': user,
        'can_edit': user == request.user
    }

    return object_list(request, queryset=qs, allow_empty=True,
                       paginate_by=settings.ACTIVITIES_ONPAGE,
                       template_name='profiles/view.html',
                       template_object_name='action',
                       extra_context=extra_context)


@login_required
def dashboard(request):
    user = request.user

    tasks = user.open_tasks()

    widget_settings = {}
    from apps.widget.rpc import add_general_settings
    add_general_settings(request, widget_settings)

    # For perform links on tasks
    video_pks = [t.team_video.video_id for t in tasks]
    video_urls = dict([(vu.video_id, vu.effective_url) for vu in
                       VideoUrl.objects.filter(video__in=video_pks, primary=True)])

    for t in tasks:
        t.cached_video_url = video_urls.get(t.team_video.video_id)

    context = {
        'user_info': user,
        'team_activity': Action.objects.for_user_team_activity(user)[:8],
        'video_activity': Action.objects.for_user_video_activity(user)[:8],
        'tasks': tasks,
        'widget_settings': widget_settings,
    }

    return direct_to_template(request, 'profiles/dashboard.html', context)


def videos(request, user_id=None):
    if user_id:
        try:
            user = User.objects.get(username=user_id)
        except User.DoesNotExist:
            try:
                user = User.objects.get(id=user_id)
            except (User.DoesNotExist, ValueError):
                raise Http404

    qs = Video.objects.filter(user=user).order_by('-edited')
    q = request.REQUEST.get('q')

    if q:
        qs = qs.filter(Q(title__icontains=q)|Q(description__icontains=q))

    context = {
        'user_info': user,
        'query': q
    }

    qs = qs._clone(OptimizedQuerySet)

    return object_list(request, queryset=qs,
                       paginate_by=VIDEOS_ON_PAGE,
                       template_name='profiles/videos.html',
                       extra_context=context,
                       template_object_name='user_video')


@login_required
def edit(request):
    if request.method == 'POST':
        # the form requires username and email
        # however, letting the user set it here isn't safe
        # (let the account view handle it)
        data = request.POST.copy()
        data['username'] = request.user.username
        data['email'] = request.user.email
        form = EditUserForm(data,
                            instance=request.user,
                            files=request.FILES, label_suffix="")
        if form.is_valid():
            form.save()
            messages.success(request, _('Your profile has been updated.'))
            return redirect('profiles:edit')
    else:
        form = EditUserForm(instance=request.user, label_suffix="")

    context = {
        'form': form,
        'user_info': request.user,
        'edit_profile_page': True
    }
    return direct_to_template(request, 'profiles/edit.html', context)


@login_required
def account(request):
    if request.method == 'POST':
        form = EditAccountForm(request.POST,
                            instance=request.user,
                            files=request.FILES, label_suffix="")
        if form.is_valid():
            form.save()
            messages.success(request, _('Your account has been updated.'))
            return redirect('profiles:account')

    else:
        form = EditAccountForm(instance=request.user, label_suffix="")

    third_party_accounts = request.user.third_party_accounts.all()
    twitters = request.user.twitteraccount_set.all()
    facebooks = request.user.facebookaccount_set.all()

    context = {
        'form': form,
        'user_info': request.user,
        'edit_profile_page': True,
        'third_party': third_party_accounts,
        'twitters': twitters,
        'facebooks': facebooks,
        'hide_prompt': True
    }

    return direct_to_template(request, 'profiles/account.html', context)


@login_required
def send_message(request):
    output = dict(success=False)
    form = SendMessageForm(request.user, request.POST)
    if form.is_valid():
        form.send()
        output['success'] = True
    else:
        output['errors'] = form.get_errors()
    return HttpResponse(json.dumps(output), "text/javascript")


@login_required
def generate_api_key(request):
    key, created = ApiKey.objects.get_or_create(user=request.user)
    if not created:
        key.key = key.generate_key()
        key.save()
    return HttpResponse(json.dumps({"key":key.key}))


@login_required
def edit_avatar(request):
    form = EditAvatarForm(request.POST, instance=request.user, files=request.FILES)
    if form.is_valid():
        form.save()
        result = {
            'status': 'success',
            'message': force_unicode(_('Your photo has been updated.'))
        }
    else:
        errors = []
        [errors.append(force_unicode(e)) for e in form.errors['picture']]
        result = {
            'status': 'error',
            'message': ''.join(errors)
        }
    result['avatar'] = request.user._get_avatar_by_size(240)
    return HttpResponse(json.dumps(result))


@login_required
def remove_avatar(request):
    if request.POST.get('remove'):
        request.user.picture = ''
        request.user.save()
        result = {
            'status': 'success',
            'message': force_unicode(_('Your photo has been removed.')),
            'avatar': request.user._get_avatar_by_size(240)
        }
    return HttpResponse(json.dumps(result))


@login_required
def add_third_party(request):
    account_type = request.GET.get('account_type', None)
    if not account_type:
        raise Http404

    if account_type not in LINKABLE_ACCOUNTS:
        raise Http404

    if account_type == 'youtube':
        from accountlinker.views import _generate_youtube_oauth_request_link
        state = json.dumps({'user': request.user.pk})
        url = _generate_youtube_oauth_request_link(state)

    if account_type == 'twitter':
        request.session['no-login'] = True
        url = reverse('thirdpartyaccounts:twitter_login')

    if account_type == 'facebook':
        request.session['fb-no-login'] = True
        url = reverse('thirdpartyaccounts:facebook_login')

    return redirect(url)


@login_required
def remove_third_party(request, account_id):
    from accountlinker.models import ThirdPartyAccount
    from thirdpartyaccounts.models import TwitterAccount, FacebookAccount

    account_type = request.GET.get('type', 'generic')

    if account_type == 'generic':
        account = get_object_or_404(ThirdPartyAccount, pk=account_id)
        display_type = account.get_type_display()
        uid = account.full_name

        if account not in request.user.third_party_accounts.all():
            raise Http404
    elif account_type == 'twitter':
        account = get_object_or_404(TwitterAccount, pk=account_id)
        display_type = 'Twitter'
        uid = account.username

        if account not in request.user.twitteraccount_set.all():
            raise Http404
    elif account_type == 'facebook':
        account = get_object_or_404(FacebookAccount, pk=account_id)
        display_type = 'Facebook'
        uid = account.uid

        if account not in request.user.facebookaccount_set.all():
            raise Http404

    if request.method == 'POST':
        if account.type == VIDEO_TYPE_YOUTUBE:
            # Delete the corresponding VideoFeed
            username = account.username.replace(' ', '')
            url = "https://gdata.youtube.com/feeds/api/users/%s/uploads" % username
            try:
                feed = VideoFeed.objects.filter(url=url)
                feed.delete()
            except VideoFeed.DoesNotExist:
                logger.error("Feed for youtube account doesn't exist", extra={
                    "youtube_username": username
                })
            # for youtube accounts we might take a while to remove any descriptions
            #  we've added to videos, so we run that in the background.
            # the task will access the tpa, and will delete the account once it's
            # done
            from accountlinker.tasks import remove_youtube_descriptions_for_tpa
            remove_youtube_descriptions_for_tpa.delay(account.pk)
            msg = _("We're tying up loose ends - your account will be removed shortly. Check back after 10 minutes")
        else:
            # anything but yt accounts can be deleted right away
            account.delete()
            msg = _('Account deleted.')
        messages.success(request, msg)
        return redirect('profiles:account')

    context = {
        'user_info': request.user,
        'third_party': account,
        'type': display_type,
        'uid': uid
    }
    return direct_to_template(request, 'profiles/remove-third-party.html',
            context)
