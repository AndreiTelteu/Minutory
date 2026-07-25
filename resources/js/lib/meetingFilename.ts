export interface MeetingFilenameSuggestion {
    title: string;
    localDateTime?: string;
}

const LEADING_TIMESTAMP = /^(\d{4})-(\d{2})-(\d{2})[ ](\d{2})-(\d{2})-(\d{2})(?:\s+|$)/;
const RECORDER_FPS = String.raw`(?:23\.976|24|25|29\.97|30|48|50|59\.94|60|90|120|144|240)`;
const TERMINAL_RECORDER_PROFILE = new RegExp(String.raw`(?:^|\s+)Fast\s+(?:720|1080|1440|2160)p\s*${RECORDER_FPS}(?:\s+FPS)?$`, 'i');

const isLeapYear = (year: number): boolean => year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);

const isValidLocalDateTime = (year: number, month: number, day: number, hour: number, minute: number, second: number): boolean => {
    if (year < 1000 || year > 9999 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) {
        return false;
    }

    const daysInMonth = [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

    return day >= 1 && day <= daysInMonth[month - 1];
};

const basenameWithoutExtension = (path: string): string => {
    const basename = path.split(/[\\/]/).at(-1) ?? '';
    const extensionIndex = basename.lastIndexOf('.');

    return extensionIndex > 0 ? basename.slice(0, extensionIndex) : basename;
};

const normalizeWhitespace = (value: string): string => value.replace(/\s+/g, ' ').trim();

export const parseMeetingFilename = (path: string): MeetingFilenameSuggestion => {
    let title = normalizeWhitespace(basenameWithoutExtension(path));
    let localDateTime: string | undefined;
    const timestamp = title.match(LEADING_TIMESTAMP);

    if (timestamp) {
        const [, yearValue, monthValue, dayValue, hourValue, minuteValue, secondValue] = timestamp;
        const parts = [yearValue, monthValue, dayValue, hourValue, minuteValue, secondValue].map(Number);

        if (isValidLocalDateTime(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])) {
            localDateTime = `${yearValue}-${monthValue}-${dayValue}T${hourValue}:${minuteValue}:${secondValue}`;
            title = title.slice(timestamp[0].length);
        }
    }

    title = normalizeWhitespace(title.replace(TERMINAL_RECORDER_PROFILE, ''));

    return {
        title,
        ...(localDateTime ? { localDateTime } : {}),
    };
};

export const localDateTimeToOffsetIso = (value: string): string | null => {
    const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/);

    if (!match) {
        return null;
    }

    const [, yearValue, monthValue, dayValue, hourValue, minuteValue, secondValue = '00'] = match;
    const parts = [yearValue, monthValue, dayValue, hourValue, minuteValue, secondValue].map(Number);

    if (!isValidLocalDateTime(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])) {
        return null;
    }

    const localDate = new Date(0);
    localDate.setHours(0, 0, 0, 0);
    localDate.setFullYear(parts[0], parts[1] - 1, parts[2]);

    // Date's "compatible" disambiguation selects the earlier offset during a
    // fall-back fold. Spring-forward gaps normalize forward, so the component
    // round-trip below deliberately rejects those nonexistent wall times.
    localDate.setHours(parts[3], parts[4], parts[5], 0);

    if (
        localDate.getFullYear() !== parts[0] ||
        localDate.getMonth() !== parts[1] - 1 ||
        localDate.getDate() !== parts[2] ||
        localDate.getHours() !== parts[3] ||
        localDate.getMinutes() !== parts[4] ||
        localDate.getSeconds() !== parts[5]
    ) {
        return null;
    }

    const offsetMinutes = -localDate.getTimezoneOffset();
    const sign = offsetMinutes >= 0 ? '+' : '-';
    const absoluteOffset = Math.abs(offsetMinutes);
    const offsetHours = String(Math.floor(absoluteOffset / 60)).padStart(2, '0');
    const offsetRemainder = String(absoluteOffset % 60).padStart(2, '0');

    return `${yearValue}-${monthValue}-${dayValue}T${hourValue}:${minuteValue}:${secondValue}${sign}${offsetHours}:${offsetRemainder}`;
};
