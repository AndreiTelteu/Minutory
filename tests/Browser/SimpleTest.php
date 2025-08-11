<?php

it('can visit the dashboard', function () {
    $this->visit('/')
         ->assertSee('Dashboard');
});