describe('Test display time filter', function() {
    beforeEach(module('amara.SubtitleEditor.filters'));
    var minuteInMilliseconds = 60 * 1000;
    var hourInMilliseconds = 60 * minuteInMilliseconds;
    describe('displayTime', function() {

        it('Do not pad unless needed',
            inject(function(displayTimeFilter) {
                expect(displayTimeFilter(null)).toBe("--");
                expect(displayTimeFilter(-1)).toBe("--");
                expect(displayTimeFilter("a")).toBe("--");
                // millisenconds only
                expect(displayTimeFilter(123)).toBe("0,12");
                // seconds, should not be padded
                expect(displayTimeFilter(5123)).toBe("5,12");
                // seconds
                expect(displayTimeFilter(55123)).toBe("55,12");
                // with minutes, seconds should be padded
                expect(displayTimeFilter(60512)).toBe("1:00,51");
                // hour overflows correctly
                expect(displayTimeFilter(70* minuteInMilliseconds + 123))
                    .toBe("1:10:00,12");
                expect(displayTimeFilter(5* hourInMilliseconds + 123))
                    .toBe("5:00:00,12");
            }));
    });
});

describe('Drop down shows the right labels', function() {
    beforeEach(module('amara.SubtitleEditor.filters'));
    describe('versionDropDownDisplay', function() {

        var versionData = {
            'version_no':1
        };
        it('Are we showing the right thing?',
            inject(function(versionDropDownDisplayFilter) {
                versionData.visibility = 'Public';
                expect(versionDropDownDisplayFilter(versionData)).
                    toBe('Version 1');
                versionData.visibility = 'Private';
                expect(versionDropDownDisplayFilter(versionData)).
                    toBe('Version 1 (Private)');
                versionData.visibility = 'Deleted';
                expect(versionDropDownDisplayFilter(versionData)).
                    toBe('Version 1 (Deleted)');
            }));
    });
});
