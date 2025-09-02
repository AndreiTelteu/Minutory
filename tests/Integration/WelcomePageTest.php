<?php

use function Pest\Laravel\get;

describe('Welcome Page Integration', function () {
    it('displays the welcome page with correct content', function () {
        $response = get('/');
        
        $response->assertStatus(200);
        $response->assertInertia(fn ($page) => 
            $page->component('Dashboard')
                ->has('recentMeetings')
                ->has('stats')
                ->has('topClients')
        );
    });

    it('shows correct navigation links', function () {
        $response = get('/');
        
        $response->assertInertia(fn ($page) => 
            $page->component('Dashboard')
        );
    });

    it('displays stats correctly when no data exists', function () {
        $response = get('/');
        
        $response->assertInertia(fn ($page) => 
            $page->component('Dashboard')
                ->where('stats.total_clients', 0)
                ->where('stats.total_meetings', 0)
                ->where('stats.completed_meetings', 0)
                ->where('stats.processing_meetings', 0)
                ->where('stats.pending_meetings', 0)
                ->where('stats.failed_meetings', 0)
        );
    });

    it('displays empty state for recent meetings', function () {
        $response = get('/');
        
        $response->assertInertia(fn ($page) => 
            $page->component('Dashboard')
                ->where('recentMeetings', [])
        );
    });

    it('displays empty state for top clients', function () {
        $response = get('/');
        
        $response->assertInertia(fn ($page) => 
            $page->component('Dashboard')
                ->where('topClients', [])
        );
    });
});