import type { MeetingFilenameSuggestion } from './meetingFilename';

export interface SuggestedFieldState {
    value: string;
    manuallyEdited: boolean;
}

export interface MeetingSuggestionState {
    title: SuggestedFieldState;
    localDateTime: SuggestedFieldState;
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
