# Technology Stack

## Backend
- **PHP 8.2+** - Modern PHP with latest features
- **Laravel 12** - Full-featured web framework
- **Inertia.js Laravel** - Server-side adapter for SPA-like experiences
- **SQLite** - Default database for development
- **Pest PHP** - Modern testing framework

## Frontend
- **Vue.js 3** - Progressive JavaScript framework
- **TypeScript** - Type-safe JavaScript development
- **Inertia.js Vue3** - Client-side adapter
- **Tailwind CSS 4** - Utility-first CSS framework
- **Vite** - Fast build tool and dev server
- **VueUse** - Vue composition utilities

## Development Tools
- **Laravel Pint** - PHP code style fixer
- **ESLint** - JavaScript/TypeScript linting
- **Prettier** - Code formatting
- **Laravel Sail** - Docker development environment
- **Ziggy** - Laravel route generation for JavaScript

## Common Commands

### Development
```bash
# Start development server (PHP + Queue + Vite)
composer dev

# Start with SSR support
composer dev:ssr

# Frontend development only
npm run dev

# Build for production
npm run build
npm run build:ssr
```

### Testing
```bash
# Run PHP tests
composer test
php artisan test

# Run specific test
php artisan test --filter=TestName
```

### Code Quality
```bash
# Format PHP code
./vendor/bin/pint

# Format frontend code
npm run format

# Lint frontend code
npm run lint

# Check formatting
npm run format:check
```

### Database
```bash
# Run migrations
php artisan migrate

# Fresh migration with seeding
php artisan migrate:fresh --seed

# Create migration
php artisan make:migration create_table_name
```

### Artisan Commands
```bash
# Generate application key
php artisan key:generate

# Clear caches
php artisan config:clear
php artisan cache:clear
php artisan view:clear

# Create controllers, models, etc.
php artisan make:controller ControllerName
php artisan make:model ModelName
```