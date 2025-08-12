import '../css/app.css';

import { createInertiaApp } from '@inertiajs/vue3';
import { resolvePageComponent } from 'laravel-vite-plugin/inertia-helpers';
import type { DefineComponent } from 'vue';
import { createApp, h } from 'vue';
import { ZiggyVue } from 'ziggy-js';
import { errorHandler } from './lib/errorHandler';

const appName = import.meta.env.VITE_APP_NAME || 'Laravel';

createInertiaApp({
    title: (title) => (title ? `${title} - ${appName}` : appName),
    resolve: (name) => resolvePageComponent(`./pages/${name}.vue`, import.meta.glob<DefineComponent>('./pages/**/*.vue')),
    setup({ el, App, props, plugin }) {
        const app = createApp({ render: () => h(App, props) })
            .use(plugin)
            .use(ZiggyVue);

        // Global error handler
        app.config.errorHandler = (error, instance, info) => {
            console.error('Vue error:', error, info);
            errorHandler.handleError(error, {
                component: instance?.$options.name || 'unknown',
                action: 'vue_error',
                data: { info }
            });
        };

        // Global warning handler (development only)
        if (import.meta.env.DEV) {
            app.config.warnHandler = (msg, instance, trace) => {
                console.warn('Vue warning:', msg, trace);
            };
        }

        app.mount(el);
    },
    progress: {
        color: '#4B5563',
        showSpinner: true,
    },
});
