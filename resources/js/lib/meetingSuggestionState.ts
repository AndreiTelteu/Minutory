import type { MeetingFilenameSuggestion } from './meetingFilename';

export interface SuggestedFieldState {
    value: string;
    manuallyEdited: boolean;
}

export interface MeetingSuggestionState {
    title: SuggestedFieldState;
    localDateTime: SuggestedFieldState;
}

export interface MeetingCreateRememberData {
    suggestionState: MeetingSuggestionState;
    clientId: string;
    language: 'ro' | 'en';
}

export interface RememberableMeetingCreateState extends MeetingCreateRememberData {
    __remember: () => MeetingCreateRememberData;
    __restore: (value: unknown) => RememberableMeetingCreateState;
}

export const createMeetingSuggestionState = (): MeetingSuggestionState => ({
    title: { value: '', manuallyEdited: false },
    localDateTime: { value: '', manuallyEdited: false },
});

export const applyMeetingFilenameSuggestion = (state: MeetingSuggestionState, suggestion: MeetingFilenameSuggestion): void => {
    if (!state.title.manuallyEdited) {
        state.title.value = suggestion.title;
    }

    if (!state.localDateTime.manuallyEdited) {
        state.localDateTime.value = suggestion.localDateTime ?? '';
    }
};

export const markSuggestedFieldEdited = (field: SuggestedFieldState, value: string): void => {
    field.value = value;
    field.manuallyEdited = true;
};

export const clearAutomaticMeetingSuggestions = (state: MeetingSuggestionState): void => {
    if (!state.title.manuallyEdited) {
        state.title.value = '';
    }

    if (!state.localDateTime.manuallyEdited) {
        state.localDateTime.value = '';
    }
};

export const resetMeetingSuggestionState = (state: MeetingSuggestionState): void => {
    state.title.value = '';
    state.title.manuallyEdited = false;
    state.localDateTime.value = '';
    state.localDateTime.manuallyEdited = false;
};

const restoreSuggestedField = (value: unknown): SuggestedFieldState => {
    if (!value || typeof value !== 'object') {
        return { value: '', manuallyEdited: false };
    }

    const candidate = value as Partial<SuggestedFieldState>;

    return {
        value: typeof candidate.value === 'string' ? candidate.value : '',
        manuallyEdited: candidate.manuallyEdited === true,
    };
};

export const restoreMeetingCreateRememberData = (value: unknown): MeetingCreateRememberData => {
    if (!value || typeof value !== 'object') {
        return {
            suggestionState: createMeetingSuggestionState(),
            clientId: '',
            language: 'ro',
        };
    }

    const candidate = value as {
        suggestionState?: {
            title?: unknown;
            localDateTime?: unknown;
        };
        clientId?: unknown;
        language?: unknown;
    };

    return {
        suggestionState: {
            title: restoreSuggestedField(candidate.suggestionState?.title),
            localDateTime: restoreSuggestedField(candidate.suggestionState?.localDateTime),
        },
        clientId: typeof candidate.clientId === 'string' ? candidate.clientId : '',
        language: candidate.language === 'en' ? 'en' : 'ro',
    };
};

export const serializeMeetingCreateRememberData = (state: MeetingCreateRememberData): MeetingCreateRememberData => ({
    suggestionState: {
        title: { ...state.suggestionState.title },
        localDateTime: { ...state.suggestionState.localDateTime },
    },
    clientId: state.clientId,
    language: state.language,
});

export const createRememberableMeetingCreateState = (value?: unknown): RememberableMeetingCreateState => {
    const data = restoreMeetingCreateRememberData(value);

    return {
        ...data,
        __remember() {
            return serializeMeetingCreateRememberData(this);
        },
        __restore(restored) {
            const restoredData = restoreMeetingCreateRememberData(restored);
            this.suggestionState = restoredData.suggestionState;
            this.clientId = restoredData.clientId;
            this.language = restoredData.language;

            return this;
        },
    };
};
