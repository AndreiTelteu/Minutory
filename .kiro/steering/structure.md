# Project Structure

## Root Directory Organization

```
├── app/                    # Laravel application code
├── bootstrap/              # Framework bootstrap files
├── config/                 # Configuration files
├── database/               # Migrations, factories, seeders
├── public/                 # Web server document root
├── resources/              # Frontend assets and views
├── routes/                 # Route definitions
├── storage/                # File storage and logs
├── tests/                  # Test files
└── vendor/                 # Composer dependencies
```

## Backend Structure (app/)

```
app/
├── Http/
│   ├── Controllers/        # Request handlers
│   └── Middleware/         # HTTP middleware
├── Models/                 # Eloquent models
└── Providers/              # Service providers
```

### Conventions
- Controllers use PascalCase and end with `Controller`
- Models use singular PascalCase (e.g., `User`, `BlogPost`)
- Follow Laravel naming conventions for relationships and methods
- Use resource controllers for CRUD operations

## Frontend Structure (resources/)

```
resources/
├── css/
│   └── app.css            # Main stylesheet with Tailwind imports
├── js/
│   ├── lib/               # Shared utilities and components
│   ├── pages/             # Inertia.js page components
│   ├── types/             # TypeScript type definitions
│   ├── app.ts             # Main application entry point
│   └── ssr.ts             # Server-side rendering entry
└── views/
    └── app.blade.php      # Main Blade template
```

### Frontend Conventions
- Vue components use PascalCase filenames
- Pages in `resources/js/pages/` mirror route structure
- Shared components go in `resources/js/lib/`
- TypeScript interfaces use PascalCase with `I` prefix
- Use Composition API with `<script setup>` syntax

## Database Structure

```
database/
├── factories/             # Model factories for testing
├── migrations/            # Database schema migrations
├── seeders/               # Database seeders
└── database.sqlite        # SQLite database file
```

### Database Conventions
- Migration files use timestamp prefixes
- Table names are plural snake_case
- Foreign keys follow `{table}_id` pattern
- Use factories for test data generation

## Configuration Structure

```
config/
├── app.php               # Application configuration
├── database.php          # Database connections
├── inertia.php           # Inertia.js settings
└── ...                   # Other service configurations
```

## Testing Structure

```
tests/
├── Feature/              # Integration tests
├── Unit/                 # Unit tests
├── Pest.php              # Pest configuration
└── TestCase.php          # Base test case
```

### Testing Conventions
- Feature tests for HTTP requests and user workflows
- Unit tests for individual classes and methods
- Use Pest's `it()` syntax for readable test descriptions
- Leverage factories for test data

## Key Files

- **composer.json** - PHP dependencies and scripts
- **package.json** - Node.js dependencies and build scripts
- **vite.config.ts** - Vite build configuration
- **tsconfig.json** - TypeScript configuration
- **.env** - Environment variables (copy from .env.example)
- **artisan** - Laravel command-line interface