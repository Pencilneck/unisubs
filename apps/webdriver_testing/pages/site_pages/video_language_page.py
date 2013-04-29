#!/usr/bin/env python
# -*- coding: utf-8 -*-
from video_page import VideoPage
import requests

class VideoLanguagePage(VideoPage):
    """
     Video Page contains the common elements in the video page.
    """

    _URL = "videos/{0}/{1}/"  # format(video id, language code)
    _REV_URL = "videos/{0}/{1}/{2}/"
    _VIDEO_TITLE = "li.title"
    _VIDEO_DESCRIPTION  = "li.description"
    _SUB_LINES = "div.translation-text"
    _VIEW_NOTICE = 'p.view-notice'
    _DRAFT_NOTICE = 'p.view-notice.draft'
    _DELETE_SUBTITLE_LANGUAGE = 'a[href*="delete-language"]'

    #UNPUBLISH MODAL
    _VERSION = 'input[value="version"]'
    _LANGUAGE = 'input[value="dependents"]'
    _DELETE = 'input[name="should_delete"]'
    _SUBMIT_UNPUBLISH = 'button.pull-right'

    #SUBTITLES TAB
    _EDIT_SUBTITLES = "a#edit_subtitles_button"
    _DOWNLOAD_SUBS = "span.sort_label strong"
    _DOWNLOAD_OPTION = "div.sort_button ul li" 
    EDIT_INACTIVE_TEXT = 'You do not have permission to edit this version'
    _ROLLBACK = "a#rollback" 

    def open_video_lang_page(self, video_id, lang_code):
        self.logger.info('Opening {0} page for video: {1}'.format(
                         lang_code, video_id))
        self.open_page(self._URL.format(video_id, lang_code))

    def open_lang_revision_page(self, video_id, lang_code, sl_sv):
        self.logger.info('Opening revision {0} page for video: {1}'.format(
                         sl_sv, video_id))
        self.open_page(self._REV_URL.format(video_id, lang_code, sl_sv))

    def edit_subtitles(self):
        self.logger.info('Clicking edit subtitles')
        self.wait_for_element_present(self._EDIT_SUBTITLES, wait_time=10)
        self.click_by_css(self._EDIT_SUBTITLES)

    def displayed_lines(self):
        self.logger.info('Getting display lines of sub text')
        displayed_subtitles = []
        line_elements = self.get_elements_list(self._SUB_LINES)
        for el in line_elements:
            l = el.text
            l = l.replace('\n', ' ')
            displayed_subtitles.append(l)
        return displayed_subtitles


    def download_link(self, output_format):
        """Return the download link for specified format.

        """
        self.logger.info('Locating the download link element for the format')
        self.click_by_css(self._DOWNLOAD_SUBS)
        self.wait_for_element_present(self._DOWNLOAD_OPTION)
        format_els = self.get_elements_list(self._DOWNLOAD_OPTION)
        for el in format_els:
            if el.text == output_format:
                return el.find_element_by_css_selector('a').get_attribute('href')
                break
        else:
            raise ValueError('Did not find the link for %s format' % output_format)

    def check_download_link(self, link):
        self.logger.info('Getting content and headers of dl link')
        r = requests.get(link)
        self.logger.info(r.content)
        return r.headers

    def displays_subtitles(self):
        try:
            self.get_elements_list(self._SUB_LINES)
            return True
        except:
            return None

    def is_draft(self):
        return self.is_element_visible(self._DRAFT_NOTICE)

    def view_notice(self):
        return self.get_text_by_css(self._VIEW_NOTICE)

    def delete_subtitle_language(self, languages=None):
        """Completely delete a subtitle language, and optional dependents.

        """
        self.click_by_css(self._DELETE_SUBTITLE_LANGUAGE)
        self.wait_for_element_visible(self._VERSION)
        delete_option = getattr(self, '_%s' % option)
        self.click_by_css(delete_option)
        if delete:
            self.click_by_css(self._DELETE)
        self.submit_by_css(self._SUBMIT_UNPUBLISH)

    def edit_subtitles_exists(self):
        return self.is_element_present(self._EDIT_SUBTITLES)

    def edit_subtitles_active(self):
        cls_properties = self.get_element_attribute(self._EDIT_SUBTITLES, 'class')
        if 'disabled' in cls_properties:
            return self.get_element_attribute(self._EDIT_SUBTITLES, 'title')
        else:
            return 'active'

    def rollback_exists(self):
        return self.is_element_present(self._ROLLBACK)

    def rollback(self):
        self.click_by_css(self._ROLLBACK)
        self.handle_js_alert('accept')
        return self.success_message_present('Rollback successful')

