export const UNAVAILABLE_DATE_TIME = '—';
export const PENDING_LOCAL_DATE_TIME = '…';
export const FALLBACK_BROWSER_TIME_ZONE = 'UTC';

export const resolveBrowserTimeZone = (): string => {
    try {
        const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        return typeof timeZone === 'string' && timeZone.trim() !== '' ? timeZone : FALLBACK_BROWSER_TIME_ZONE;
    } catch {
        return FALLBACK_BROWSER_TIME_ZONE;
    }
};

export const formatBrowserDateTime = (
    value: string | null,
    localizationReady: boolean,
    locale?: string,
    options: Intl.DateTimeFormatOptions = {
        dateStyle: 'medium',
        timeStyle: 'medium',
    },
): string => {
    if (!value) {
        return UNAVAILABLE_DATE_TIME;
    }

    if (!localizationReady) {
        return PENDING_LOCAL_DATE_TIME;
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return UNAVAILABLE_DATE_TIME;
    }

    return new Intl.DateTimeFormat(locale, options).format(date);
};
