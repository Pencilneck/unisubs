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

import json
import urllib

import requests
from django.conf import settings
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from gdata.client import Unauthorized

from auth.models import CustomUser as User

from accountlinker.models import ThirdPartyAccount
from localeurl.utils import universal_url

from teams.models import Team
from videos.models import VIDEO_TYPE_YOUTUBE, VideoFeed
from videos.tasks import update_video_feed
from videos.types.youtube import YouTubeApiBridge

from tasks import mirror_existing_youtube_videos

import logging

logger = logging.getLogger("authbelt.views")


def _youtube_request_uri():
    if getattr(settings, 'YOUTUBE_CLIENT_FORCE_HTTPS', True):
        return universal_url("accountlinker:youtube-oauth-callback",
                protocol_override='https')
    else:
        return universal_url("accountlinker:youtube-oauth-callback")


def _generate_youtube_oauth_request_link(state_str=None):
    state_str = state_str or ""
    base =  "https://accounts.google.com/o/oauth2/auth?"
    state = state_str
    
    params = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "redirect_uri":  _youtube_request_uri(),
        "scope": "https://gdata.youtube.com",
        "state": state,
        "response_type": "code",
        "approval_prompt": "force",
        "access_type": "offline",
        
    }
    return "%s%s" % (base, urllib.urlencode(params))


def youtube_oauth_callback(request):
    """
    Stores the oauth tokes. We identify which team this belongs to
    since we've passed the pk on the state param for the authorize request
    """
    import atom
    code = request.GET.get("code", None)
    error = request.GET.get("error", None)
    state = request.GET.get("state", None)

    if error is not None:
        messages.error(request, 'Youtube said: "%s"' % error)
        return redirect('profiles:account')

    if code is None or state is None:
        messages.error(request, 'Error while linking.  Please try again.')
        return redirect('profiles:account')

    state = json.loads(state)

    if 'team' in state:
        team_pk = state['team']
        team = Team.objects.get(pk=team_pk)
    else:
        team = None

    if 'user' in state:
        user_pk = state['user']
        user = User.objects.get(pk=user_pk)
        if request.user.pk != user.pk:
            messages.error(request, _("The user who requested this action"
                " doesn't match the current user."))
            return redirect('/')
    else:
        user = None

    base = "https://accounts.google.com/o/oauth2/token"
    
    params = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "client_secret": settings.YOUTUBE_CLIENT_SECRET,
        "redirect_uri": _youtube_request_uri(),
        "code": code,
        "grant_type": "authorization_code",
        
    }
    
    response = requests.post(base, data=params, headers={
        "Content-Type": "application/x-www-form-urlencoded"
    })

    if response.status_code != 200:
        logger.error("Error on requesting Youtube Oauth token", extra={
                    "data": {
                        "sent_params": params,
                        "original_request": request,
                        "response": response.content
                    },
                })
                    
    content = json.loads(response.content)
    if content.get('error', None):
        logger.error("Error on requesting Youtube Oauth token", extra={
                    "data": {
                        "sent_params": params,
                        "original_request": request,
                        "response": response.content
                    },
                })
        error = content.get('error')
        messages.error(request, 'Youtube said: "%s"' % error)
        return redirect('profiles:account')
    bridge = YouTubeApiBridge(content['access_token'], content['refresh_token'], None)

    try:
        feed = bridge.get_user_profile(username='default')
    except Unauthorized:
        messages.error(request,
            _("We couldn't link your account. Have you <a href="
            "'https://accounts.google.com/ServiceLogin?passive=true&continue=http%3A%2F%2Fwww.youtube.com/create_channel'"
            ">set up a channel</a>?"))
        return redirect(reverse("profiles:account"))

    author = [x for x in feed.get_elements() if type(x) == atom.data.Author][0]
    username = [x for x in feed.get_elements() if x.tag == 'username'][0].text
    
    # make sure we don't store multiple auth tokes for the same account
    account, created = ThirdPartyAccount.objects.get_or_create(
        type=VIDEO_TYPE_YOUTUBE,
        username=username,
        defaults={
            'oauth_refresh_token': content['refresh_token'],
            'oauth_access_token': content['access_token'],
            'full_name': author.name.text
        }
    )

    if not created and not team and user:
        messages.error(request, _("Account already linked."))
        return redirect('/')

    if team:
        team.third_party_accounts.add(account)
        return redirect(
            reverse("teams:third-party-accounts", kwargs={"slug": team.slug}))

    if user:
        user.third_party_accounts.add(account)
        uri = author.uri.text + '/uploads'
        video_feed = VideoFeed.objects.create(url=uri, user=user)
        update_video_feed.delay(video_feed.pk)
        mirror_existing_youtube_videos.delay(user.pk)
        return redirect(reverse("profiles:account"))
