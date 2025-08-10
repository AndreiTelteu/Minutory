import type { Config } from 'ziggy-js';

export interface Auth {
    user: User;
}

export type AppPageProps<T extends Record<string, unknown> = Record<string, unknown>> = T & {
    name: string;
    quote: { message: string; author: string };
    auth: Auth;
    ziggy: Config & { location: string };
    csrf_token: string;
};

export interface User {
    id: number;
    name: string;
    email: string;
    avatar?: string;
    email_verified_at: string | null;
    created_at: string;
    updated_at: string;
}

export interface Client {
    id: number;
    name: string;
    email: string | null;
    company: string | null;
    phone: string | null;
    meetings_count?: number;
    meetings?: Meeting[];
    created_at: string;
    updated_at: string;
}

export interface Meeting {
    id: number;
    client_id: number;
    title: string;
    video_path: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    duration: number | null;
    uploaded_at: string;
    processing_started_at: string | null;
    processing_completed_at: string | null;
    client?: Client;
    created_at: string;
    updated_at: string;
}
