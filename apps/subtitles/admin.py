# -*- coding: utf-8 -*-
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


from django.contrib import admin
from apps.subtitles.models import (get_lineage, Collaborator, SubtitleLanguage,
                                   SubtitleVersion)


class SubtitleVersionInline(admin.TabularInline):

    def has_delete_permission(self, request, obj=None):
        # subtitle versions should be immutable, don't allow deletion
        return False

    model = SubtitleVersion
    fields = ['version_number']
    max_num = 0

class SubtitleLanguageAdmin(admin.ModelAdmin):
    list_display = ['video_title', 'language_code', 'version_count', 'tip',
                    'unofficial_signoffs',
                    'official_signoffs',
                    'pending_collaborators',
                    'expired_pending_collaborators',
                    'unexpired_pending_collaborators',
                    'is_forked']
    list_filter = ['created', 'language_code']
    
    inlines = [SubtitleVersionInline]
    search_fields = ['video__title', 'video__video_id', 'language_code']
    raw_id_fields = ['video']

    def unofficial_signoffs(self, o):
        return o.unofficial_signoff_count
    unofficial_signoffs.admin_order_field = 'unofficial_signoff_count'

    def official_signoffs(self, o):
        return o.official_signoff_count
    official_signoffs.admin_order_field = 'official_signoff_count'

    def pending_collaborators(self, o):
        return o.pending_signoff_count
    pending_collaborators.short_description = 'pending'
    pending_collaborators.admin_order_field = 'pending_signoff_count'

    def expired_pending_collaborators(self, o):
        return o.pending_signoff_expired_count
    expired_pending_collaborators.short_description = 'expired pending'
    expired_pending_collaborators.admin_order_field = 'pending_signoff_expired_count'

    def unexpired_pending_collaborators(self, o):
        return o.pending_signoff_unexpired_count
    unexpired_pending_collaborators.short_description = 'unexpired pending'
    unexpired_pending_collaborators.admin_order_field = 'pending_signoff_unexpired_count'

    def video_title(self, sl):
        return sl.video.title_display()
    video_title.short_description = 'video'

    def version_count(self, sl):
        return sl.subtitleversion_set.full().count()
    version_count.short_description = 'number of versions'

    def tip(self, sl):
        ver = sl.get_tip(full=True)
        return ver.version_number if ver else None
    tip.short_description = 'tip version'

    def save_model(self, request, obj, form, change):
        from videos.tasks import upload_subtitles_to_original_service
        should_sync_to_youtube = False
        # cache the old object
        old_obj = SubtitleLanguage.objects.get(pk=obj.pk)
        # save it
        super(SubtitleLanguageAdmin, self).save_model(request, obj, form,
                                                      change)
        # refresh new object so that changes are present
        obj = SubtitleLanguage.objects.get(pk=obj.pk)
        if change:
            should_sync_to_youtube = not old_obj.subtitles_complete and obj.subtitles_complete

        if should_sync_to_youtube:
            tip = obj.get_tip()
            # don't run on a async:
            upload_subtitles_to_original_service.run(tip.pk)


class SubtitleVersionAdmin(admin.ModelAdmin):
    list_display = ['video_title', 'id', 'language', 'version_num',
                    'visibility', 'visibility_override', 'parent_ids',
                    'subtitle_count', 'created']
    raw_id_fields = ['video', 'subtitle_language', 'parents', 'author']
    list_filter = ['created', 'visibility', 'visibility_override',
                   'language_code']
    list_editable = ['visibility', 'visibility_override']
    search_fields = ['video__video_id', 'video__title', 'title',
                     'language_code', 'description', 'note']

    # Unfortunately Django uses .all() on related managers instead of
    # .get_query_set().  We've disabled .all() on SubtitleVersion managers so we
    # can't let Django do this.  This means we can't edit parents in the admin,
    # but you should never be doing that anyway.
    exclude = ['parents', 'serialized_subtitles']

    # don't allow deletion
    actions = []

    def has_delete_permission(self, request, obj=None):
        # subtitle versions should be immutable, don't allow deletion
        return False

    def version_num(self, sv):
        return '#' + str(sv.version_number)
    version_num.short_description = 'version #'

    def video_title(self, sv):
        return sv.video.title_display()
    video_title.short_description = 'video'

    def language(self, sv):
        return sv.subtitle_language.get_language_code_display()

    def parent_ids(self, sv):
        pids = map(str, sv.parents.full().values_list('id', flat=True))
        return ', '.join(pids) if pids else None

    # Hack to generate lineages properly when modifying versions in the admin
    # interface.  Maybe we should just disallow this entirely once the version
    # models are hooked up everywhere else?
    def response_change(self, request, obj):
        response = super(SubtitleVersionAdmin, self).response_change(request, obj)
        obj.lineage = get_lineage(obj.parents.full())
        obj.save()
        return response

    def response_add(self, request, obj, *args, **kwargs):
        response = super(SubtitleVersionAdmin, self).response_add(request, obj)
        obj.lineage = get_lineage(obj.parents.full())
        obj.save()
        return response


class CollaboratorAdmin(admin.ModelAdmin):
    list_display = ['display_video', 'display_language', 'user', 'signoff',
                    'signoff_is_official', 'expired', 'expiration_start']
    raw_id_fields = ['subtitle_language', 'user']
    list_filter = ['signoff', 'signoff_is_official', 'expired', 'created']
    search_fields = ['subtitle_language__video__video_id',
                     'subtitle_language__video__title',
                     'subtitle_language__language_code',
                     'user__username', 'user__email']

    def display_video(self, o):
        return o.subtitle_language.video.title_display()
    display_video.short_description = 'video'
    display_video.admin_order_field = 'subtitle_language__video'

    def display_language(self, o):
        return o.subtitle_language.get_language_code_display()
    display_language.short_description = 'language'
    display_language.admin_order_field = 'subtitle_language__language_code'


# -----------------------------------------------------------------------------
admin.site.register(SubtitleLanguage, SubtitleLanguageAdmin)
admin.site.register(SubtitleVersion, SubtitleVersionAdmin)
admin.site.register(Collaborator, CollaboratorAdmin)
