(function() {
    'use strict';

    function createClient(getSessionToken) {
        function request(path, options = {}) {
            const headers = new Headers(options.headers || {});
            const token = String(getSessionToken() || '');
            if (token) headers.set('X-Todo-Session', token);
            return fetch(path, { ...options, headers });
        }

        return Object.freeze({ request });
    }

    window.TodoApiClient = Object.freeze({ createClient });
})();