import assert from 'node:assert/strict';
import test from 'node:test';

import { localDateTimeToOffsetIso, parseMeetingFilename } from '../../resources/js/lib/meetingFilename.ts';
import {
    applyMeetingFilenameSuggestion,
    clearAutomaticMeetingSuggestions,
    createMeetingSuggestionState,
    markSuggestedFieldEdited,
    resetMeetingSuggestionState,
} from '../../resources/js/lib/meetingSuggestionState.ts';

test('parses the required recorder filename', () => {
    assert.deepEqual(parseMeetingFilename('2026-07-10 13-03-47 Synevo Prezentare Modificari Design Rezultate Web Fast 1080p30.mp4'), {
        title: 'Synevo Prezentare Modificari Design Rezultate Web',
        localDateTime: '2026-07-10T13:03:47',
    });
});

test('strips supported terminal recorder profile variants case-insensitively', () => {
    const variants = ['Review Fast 720p60.mp4', 'Review fast 1080P 30 FPS.mov', 'Review FAST 1440p120 fps.webm', 'Review Fast 2160p 24.avi'];

    for (const variant of variants) {
        assert.equal(parseMeetingFilename(variant).title, 'Review');
    }
});

test('does not strip Fast or resolution text outside a terminal recorder profile', () => {
    assert.equal(parseMeetingFilename('Fast 1080p planning notes.mp4').title, 'Fast 1080p planning notes');
    assert.equal(parseMeetingFilename('Planning Fast 1080p.mp4').title, 'Planning Fast 1080p');
    assert.equal(parseMeetingFilename('Planning Fast 480p30.mp4').title, 'Planning Fast 480p30');
    assert.equal(parseMeetingFilename('Planning Fast 1080p30 final.mp4').title, 'Planning Fast 1080p30 final');
});

test('accepts leap dates and rejects impossible calendar dates and times', () => {
    assert.equal(parseMeetingFilename('2024-02-29 23-59-59 Leap call.mp4').localDateTime, '2024-02-29T23:59:59');
    assert.deepEqual(parseMeetingFilename('2023-02-29 12-00-00 Invalid date.mp4'), {
        title: '2023-02-29 12-00-00 Invalid date',
    });
    assert.deepEqual(parseMeetingFilename('2026-07-10 24-00-00 Invalid time.mp4'), {
        title: '2026-07-10 24-00-00 Invalid time',
    });
    assert.deepEqual(parseMeetingFilename('0000-01-01 12-00-00 Invalid year.mp4'), {
        title: '0000-01-01 12-00-00 Invalid year',
    });
});

test('uses the final path component and final extension only', () => {
    assert.deepEqual(parseMeetingFilename('/captures/archive.v2/2026-01-02 03-04-05 Planning.session.final.mp4'), {
        title: 'Planning.session.final',
        localDateTime: '2026-01-02T03:04:05',
    });
    assert.equal(parseMeetingFilename(String.raw`C:\captures\Team\ordinary.call.name.webm`).title, 'ordinary.call.name');
});

test('handles filenames without an extension, ordinary names, whitespace, and an empty residual title', () => {
    assert.deepEqual(parseMeetingFilename('  ordinary   meeting  '), { title: 'ordinary meeting' });
    assert.deepEqual(parseMeetingFilename('2026-07-10 13-03-47 Fast 1080p30.mp4'), {
        title: '',
        localDateTime: '2026-07-10T13:03:47',
    });
    assert.deepEqual(parseMeetingFilename(''), { title: '' });
});

test('preserves manual edits and clears only auto-owned values on file removal', () => {
    const state = createMeetingSuggestionState();
    applyMeetingFilenameSuggestion(state, { title: 'First title', localDateTime: '2026-01-02T03:04:05' });
    markSuggestedFieldEdited(state.title, '');
    applyMeetingFilenameSuggestion(state, { title: 'Second title', localDateTime: '2026-02-03T04:05:06' });

    assert.equal(state.title.value, '');
    assert.equal(state.localDateTime.value, '2026-02-03T04:05:06');

    clearAutomaticMeetingSuggestions(state);
    assert.equal(state.title.value, '');
    assert.equal(state.title.manuallyEdited, true);
    assert.equal(state.localDateTime.value, '');
});

test('resets suggestion ownership explicitly', () => {
    const state = createMeetingSuggestionState();
    markSuggestedFieldEdited(state.title, 'Manual');
    markSuggestedFieldEdited(state.localDateTime, '2026-01-02T03:04:05');
    resetMeetingSuggestionState(state);
    applyMeetingFilenameSuggestion(state, { title: 'Automatic', localDateTime: '2026-02-03T04:05:06' });

    assert.equal(state.title.value, 'Automatic');
    assert.equal(state.localDateTime.value, '2026-02-03T04:05:06');
});

test('creates an offset-bearing ISO value without changing wall-clock fields', () => {
    const value = localDateTimeToOffsetIso('2026-07-10T13:03:47');

    assert.match(value ?? '', /^2026-07-10T13:03:47[+-]\d{2}:\d{2}$/);
    assert.equal(localDateTimeToOffsetIso('2026-02-30T13:03:47'), null);
    assert.equal(localDateTimeToOffsetIso('2026-07-10 13:03:47'), null);
});
