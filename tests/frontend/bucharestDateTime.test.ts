import assert from 'node:assert/strict';
import test from 'node:test';

import { formatBrowserDateTime } from '../../resources/js/lib/browserDateTime.ts';
import { localDateTimeToOffsetIso } from '../../resources/js/lib/meetingFilename.ts';

test('runs in an explicitly controlled Europe/Bucharest timezone', () => {
    assert.equal(process.env.TZ, 'Europe/Bucharest');
});

test('rejects a Bucharest DST gap and selects the earlier offset in a fold', () => {
    assert.equal(localDateTimeToOffsetIso('2026-03-29T03:30:00'), null);
    assert.equal(localDateTimeToOffsetIso('2026-10-25T03:30:00'), '2026-10-25T03:30:00+03:00');
});

test('does not remap early years and enforces the 1000 minimum', () => {
    for (const year of ['0001', '0099', '0999']) {
        assert.equal(localDateTimeToOffsetIso(`${year}-01-02T03:04:05`), null);
    }

    assert.match(localDateTimeToOffsetIso('1000-01-02T03:04:05') ?? '', /^1000-01-02T03:04:05[+-]\d{2}:\d{2}$/);
});

test('keeps pre-mount timestamp markup timezone-independent', () => {
    assert.equal(formatBrowserDateTime('2026-07-10T10:03:47+00:00', false, 'en-US'), '…');
});
