import assert from 'node:assert/strict';
import test from 'node:test';

import { formatBrowserDateTime } from '../../resources/js/lib/browserDateTime.ts';

const expectedTimeZone = process.argv[2];
const expectedLocalizedValue = process.argv[3];
const value = '2026-07-10T10:03:47+00:00';

test(`keeps initial timestamp markup stable before mounting in ${expectedTimeZone}`, () => {
    assert.equal(process.env.TZ, expectedTimeZone);
    assert.equal(formatBrowserDateTime(value, false, 'en-US'), '…');
    assert.equal(formatBrowserDateTime(value, true, 'en-US'), expectedLocalizedValue);
});
