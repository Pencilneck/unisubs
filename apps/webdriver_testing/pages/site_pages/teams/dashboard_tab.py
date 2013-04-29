#!/usr/bin/env python
from apps.webdriver_testing.pages.site_pages.teams import ATeamPage
import time

class DashboardTab(ATeamPage):
    """Actions for the dashboard tab of a Team Page.

    """
    _URL = 'teams/%s/'
    _VIDEO = 'ul.listing.videos li'
    _VIDEO_TITLE = 'div.thumb h4 a'
    _VIDEO_LANGS = 'div.langs a'
    _SHOW_LANGS = 'div.langs div span.expand'
    _LANG_LIST = 'div.langs div ul li a'


    #Visible when workflows enabled for users with assigned tasks.
    _TASK_VIDEO = 'ul.tasks li'
    _TASK_VIDEO_TITLE = 'h3 a'
    _TASK_VIDEO_ACTION = 'ul.actions li a'



    _NO_VIDEOS_TEXT = "Sorry, we couldn't find any videos for you." 
    _LANGUAGE_SUGGESTION = 'ul.suggestions li a[data-modal="language_modal"]'
    #User is authenticated and has no languages specified.
    _AUTHED_LANGUAGE_SUGGESTION = 'p.prompt a[data-modal="language_modal"]'

    _BROWSE_SUGGESTION = 'ul.suggestions li a[href*="/videos/"]'
    _ADD_SUGGESTION = 'ul.suggestions li a[href*="/add/video/"]'



    # Suggestion helpers when no videos are present
    def suggestion_present(self, suggestion_type):
        suggest_css = '_'.join(['', suggestion_type.upper(), 'SUGGESTION'])
        self.logger.info('Check if the %s suggestion is present' 
                         % suggestion_type.upper())
        if self.is_element_visible(getattr(self, suggest_css)):
            return True

    def click_suggestion(self, suggestion_type):
        suggest_css = '_'.join(['', suggestion_type.upper(), 'SUGGESTION'])

        self.logger.info('Click the %s suggestion link' % suggestion_type)
        self.click_by_css(suggest_css)
    
    def no_videos_found(self):
        self.logger.info('Check if no videos are found on dashboard')
        if self.is_text_visible(self._NO_VIDEOS_TEXT):
            return True

    def _video_element(self, video):
        """Return the webdriver object for a video based on the title.

        """
        time.sleep(4)  #Make sure all the vids have a chance to load.
        video_els = self.browser.find_elements_by_css_selector(
                      self._VIDEO)

        for el in video_els:
            try:
                title_el = el.find_element_by_css_selector(self._VIDEO_TITLE)
                if video in title_el.text:
                    return el
            except:
                continue
    def _has_languages(self, video):
        try:
            lang_el = video_el.find_element_by_css_selector(
                    self._VIDEO_LANGS)
        except:
            self.logger.info('No create links found for the video %s' %video)
            return None



    def languages_needed(self, video):
        """Return a list of languages displayed as needed for video.

        """
        langs_needed = []
        video_el = self._video_element(video)
        try:
            lang_el = video_el.find_element_by_css_selector(self._VIDEO_LANGS)
            self.logger.info(lang_el.text)
        except:
            self.logger.info('No create links found for the video %s' %video)
            return None

        if 'languages need your help' in lang_el.text:
            show_el = video_el.find_element_by_css_selector(self._SHOW_LANGS)
            show_el.click()
            lang_list = video_el.find_elements_by_css_selector(
                self._LANG_LIST)
            for el in lang_list:
                self.logger.info(el.text)
                langs_needed.append(el.text)
        else:
            self.logger.info(lang_el.text)
            langs_needed.append(lang_el.text)
        self.logger.info('List of languages needed %s' % langs_needed)
        return langs_needed

    def click_lang_task(self, video, language):
        video_el = self._video_element(video)
        langs = video_el.find_elements_by_css_selector(self._VIDEO_LANGS)
        if 'languages need your help' in langs[0].text:
            video_el.find_element_by_css_selector(self._SHOW_LANGS).click()
            els = self.get_elements_list(self._LANG_LIST)
            for el in els:
                if language in el.text:
                    el.click()
        else:
            assert language in langs[0].text
            langs[0].click()

            
    def _dash_task_info(self):
        task_els = self.get_elements_list(self._TASK_VIDEO)
        print len(task_els)

        task_list = []
        for el in task_els:
            try:
                task = dict(
                    title =  el.find_element_by_css_selector(self._TASK_VIDEO_TITLE).text,
                    action = el.find_element_by_css_selector(self._TASK_VIDEO_ACTION).text)
                task_list.append(task)
            except:
                pass
        return task_list

    def dash_task_present(self, task_type, title):
        all_tasks = self._dash_task_info()
        for task in all_tasks:
            if task_type in task['action'] and title in task['title']:
                return True

        
