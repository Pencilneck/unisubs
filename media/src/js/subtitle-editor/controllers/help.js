// Amara, universalsubtitles.org
//
// Copyright (C) 2013 Participatory Culture Foundation
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as
// published by the Free Software Foundation, either version 3 of the
// License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see
// http://www.gnu.org/licenses/agpl-3.0.html.

(function() {

    var root = this;

    var HelpController = function($scope, SubtitleStorage) {
        /**
         * Responsible for handling the various states of the help panel.
         * @param $scope
         * @param SubtitleStorage
         * @constructor
         */

        $scope.commands = [
            { key: 'shift + space', description: 'play / pause the video' },
            { key: 'shift + tab', description: 'move to the previous subtitle' },
            { key: 'tab', description: 'move to the next subtitle' }
        ];

        $scope.showAdvancedModal = function() {

            $scope.$root.$emit('show-modal', {
                heading: 'Advanced keyboard controls',
                text: 'Full list of keyboard shortcuts to go here.',
                buttons: [{
                    'text': 'Close', 'class': 'yes', 'fn': function() {
                        $scope.$root.$broadcast('hide-modal');
                    }
                }]
            });

        };

    };

    root.HelpController = HelpController;

}).call(this);
