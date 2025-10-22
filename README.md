### Mob Clinic

simple clinic management optimised for mobile

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app mob_clinic
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/mob_clinic
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### Testing

Run unit tests to verify APIs are working correctly:

```bash
# Run all tests
bench --site your-site run-tests --app mob_clinic

# Run specific test module
bench --site your-site run-tests --module mob_clinic.mob_clinic.tests.test_auth
bench --site your-site run-tests --module mob_clinic.mob_clinic.tests.test_patient

# Or use the test runner script
chmod +x run_tests.sh
./run_tests.sh your-site
```

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for detailed testing documentation.

### License

mit
